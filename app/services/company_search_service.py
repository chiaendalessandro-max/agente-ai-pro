from __future__ import annotations

import logging
import re
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import Any
from urllib.parse import urlparse

from app.core.config import settings
from app.providers.apollo_provider import ApolloProvider
from company_search_real import search_companies_real_with_meta
from search_query_multilang import build_apollo_query_variants, detect_query_language

logger = logging.getLogger(__name__)

EMPTY_MSG = "Nessun risultato disponibile"


def _empty_meta() -> dict[str, Any]:
    return {
        "queries_used": [],
        "raw_results_count": 0,
        "valid_results_count": 0,
        "discarded_results_count": 0,
        "detected_language": "",
        "apollo_queries_submitted": [],
        "apollo_raw_merged_count": 0,
        "apollo_status": "",
    }


def _score_band(score_value: int) -> str:
    if score_value >= 70:
        return "HIGH"
    if score_value >= 40:
        return "MEDIUM"
    return "LOW"


def _why_this_company(item: dict[str, Any]) -> str:
    parts = []
    if item.get("sector"):
        parts.append(f"settore coerente: {item.get('sector')}")
    if item.get("contact_email") or item.get("contact_phone"):
        parts.append("contatti aziendali disponibili")
    if item.get("website"):
        parts.append("sito verificabile")
    if not parts:
        return "Profilo aziendale verificabile e coerente con la ricerca."
    return (", ".join(parts)).capitalize() + "."


def _client_probability(item: dict[str, Any]) -> str:
    score = int(item.get("score") or 0)
    has_contacts = bool(item.get("contact_email") or item.get("contact_phone"))
    if score >= 70 and has_contacts:
        return "HIGH"
    if score >= 45 or has_contacts:
        return "MEDIUM"
    return "LOW"


def _domain(url: str) -> str:
    try:
        return (urlparse(url or "").netloc or "").lower().replace("www.", "")
    except Exception:
        return ""


def _normalize_apollo_row(row: dict[str, Any], query: str, country: str, sector: str) -> dict[str, Any] | None:
    name = (row.get("name") or row.get("organization_name") or "").strip()
    website = (row.get("website_url") or row.get("website") or "").strip()
    linkedin = (row.get("linkedin_url") or "").strip()
    source_url = website or linkedin
    if not source_url and row.get("id"):
        source_url = f"apollo://organization/{row.get('id')}"
    if not name or not source_url:
        return None
    if website and not website.startswith(("http://", "https://")):
        website = f"https://{website}"
    if not website:
        website = source_url if source_url.startswith(("http://", "https://")) else ""

    score = 65
    if website:
        score += 10
    if row.get("phone"):
        score += 10
    if row.get("linkedin_url"):
        score += 5
    score = max(1, min(score, 100))

    return {
        "name": name,
        "domain": _domain(website or source_url),
        "website": website,
        "source_url": source_url,
        "country": country or row.get("country") or "",
        "sector": sector or query,
        "description": (row.get("short_description") or row.get("description") or "")[:280],
        "contact_email": "",
        "contact_phone": (row.get("phone") or "").strip(),
        "score": score,
        "classification": "HIGH VALUE" if score >= 70 else "MEDIUM",
    }


def _dedupe_rows(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    seen = set()
    out = []
    for item in rows:
        key = (item.get("domain") or "").strip().lower()
        if not key:
            key = re.sub(r"[^a-z0-9]+", "", (item.get("name") or "").lower())
        if not key or key in seen:
            continue
        seen.add(key)
        out.append(item)
    return out


def _apollo_org_key(row: dict[str, Any]) -> str:
    rid = row.get("id")
    if rid is not None and str(rid).strip():
        return f"id:{str(rid).strip()}"
    w = (row.get("website_url") or row.get("website") or "").strip()
    if w:
        return f"d:{_domain(w)}"
    return ""


def _merge_apollo_raw(acc: list[dict[str, Any]], new_rows: list[Any]) -> None:
    seen: set[str] = set()
    for r in acc:
        k = _apollo_org_key(r)
        if k:
            seen.add(k)
    for r in new_rows:
        if not isinstance(r, dict):
            continue
        k = _apollo_org_key(r)
        if k:
            if k in seen:
                continue
            seen.add(k)
        acc.append(r)


def _rows_after_basic_filters(items: list[dict[str, Any]], country: str, requested_limit: int) -> list[dict[str, Any]]:
    deduped = _dedupe_rows(items)[:requested_limit]
    out: list[dict[str, Any]] = []
    for item in deduped:
        if not item.get("name"):
            continue
        if not (item.get("website") or item.get("source_url")):
            continue
        if country and (item.get("country") or "").upper() == "GLOBAL":
            continue
        out.append(item)
    return out


def _internal_rows(query: str, country: str, limit: int, *, mode: str) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    try:
        rows, meta = search_companies_real_with_meta(
            query, country, limit, mode=mode, minimal_internal=True
        )
        return rows or [], meta or _empty_meta()
    except Exception as exc:
        logger.exception("internal search fallback failed: %s", str(exc)[:200])
        return [], _empty_meta()


def shared_search_pipeline(query: str, country: str, sector: str = "", limit: int = 10, *, mode: str = "normal") -> dict[str, Any]:
    meta = _empty_meta()
    requested_limit = max(1, min(int(limit or 10), 50))
    mode_norm = (mode or "normal").strip().lower()
    if mode_norm not in {"normal", "premium"}:
        mode_norm = "normal"
    early_valid = 5 if mode_norm == "premium" else 10
    apollo_key = (getattr(settings, "apollo_api_key", "") or "").strip()
    combined: list[dict[str, Any]] = []

    if not apollo_key:
        meta["apollo_status"] = "disabled"
        meta["detected_language"] = detect_query_language(f"{query} {sector}")
        internal_rows, internal_meta = _internal_rows(query=query, country=country, limit=requested_limit, mode=mode_norm)
        combined.extend(internal_rows)
        meta["queries_used"] = internal_meta.get("queries_used", [])
        meta["raw_results_count"] = int(internal_meta.get("raw_results_count", 0) or 0)
        meta["discarded_results_count"] = int(internal_meta.get("discarded_results_count", 0) or 0)
    else:
        provider = ApolloProvider(api_key=apollo_key, timeout_seconds=3)
        detected_lang, q_variants = build_apollo_query_variants(query, country, sector or "")
        meta["detected_language"] = detected_lang
        meta["queries_used"] = list(q_variants)
        meta["apollo_queries_submitted"] = list(q_variants)
        raw_merged: list[dict[str, Any]] = []
        last_worker_status = "ok"

        try:
            for i in range(0, len(q_variants), 5):
                batch = q_variants[i : i + 5]
                with ThreadPoolExecutor(max_workers=5) as ex:
                    future_map = {
                        ex.submit(
                            provider.search_organizations,
                            qv,
                            country,
                            sector or "",
                            min(25, requested_limit),
                            max_pages=1,
                        ): qv
                        for qv in batch
                    }
                    for fut in as_completed(list(future_map.keys())):
                        qv = future_map[fut]
                        try:
                            rows, m = fut.result(timeout=0)
                        except Exception as exc:
                            logger.warning("Apollo worker failed q=%r: %s", qv[:80], str(exc)[:160])
                            last_worker_status = "request_error"
                            continue
                        st = (m or {}).get("apollo_status") or "ok"
                        if st != "ok":
                            last_worker_status = st
                        for mk, mv in (m or {}).items():
                            if str(mk).startswith("apollo_"):
                                meta[mk] = mv
                        _merge_apollo_raw(raw_merged, rows)

                normalized_partial: list[dict[str, Any]] = []
                for row in raw_merged:
                    n = _normalize_apollo_row(row, query=query, country=country, sector=sector or "")
                    if n:
                        normalized_partial.append(n)
                if len(_rows_after_basic_filters(normalized_partial, country, requested_limit)) >= early_valid:
                    break

            meta["apollo_raw_merged_count"] = len(raw_merged)
            meta["raw_results_count"] = len(raw_merged)
            meta["apollo_status"] = "ok" if raw_merged else last_worker_status

            for row in raw_merged:
                n = _normalize_apollo_row(row, query=query, country=country, sector=sector or "")
                if n:
                    combined.append(n)
        except Exception as exc:
            logger.warning("Apollo orchestration failed: %s", str(exc)[:240])
            meta["apollo_status"] = "orchestration_error"
            meta["raw_results_count"] = 0
            meta["apollo_raw_merged_count"] = 0
            combined = []

    deduped = _dedupe_rows(combined)[:requested_limit]
    cleaned: list[dict[str, Any]] = []
    discarded = 0
    for item in deduped:
        if not item.get("name"):
            discarded += 1
            continue
        if not (item.get("website") or item.get("source_url")):
            discarded += 1
            continue
        if country and (item.get("country") or "").upper() == "GLOBAL":
            discarded += 1
            continue
        score_value = int(item.get("score") or 0)
        cleaned.append(
            {
                "company_name": item.get("name"),
                "website": item.get("website"),
                "source_url": item.get("source_url") or item.get("website"),
                "country": item.get("country"),
                "score": _score_band(score_value),
                "classification": item.get("classification", "LOW"),
                "contact_email": item.get("contact_email", ""),
                "contact_phone": item.get("contact_phone", ""),
                "why_this_company": _why_this_company(item),
                "client_probability": _client_probability(item),
            }
        )

    meta["discarded_results_count"] = int(meta.get("discarded_results_count", 0) or 0) + discarded
    meta["valid_results_count"] = len(cleaned)

    logger.info(
        "[company-search] lang=%r queries=%r apollo_raw=%s valid=%s discarded_extra=%s apollo_status=%r",
        meta.get("detected_language"),
        meta.get("queries_used"),
        meta.get("apollo_raw_merged_count"),
        len(cleaned),
        discarded,
        meta.get("apollo_status"),
    )

    return {
        "results": cleaned,
        "message": "" if cleaned else EMPTY_MSG,
        "meta": meta,
    }


def normal_search_service(query: str, country: str, sector: str = "", limit: int = 10) -> dict[str, Any]:
    out = shared_search_pipeline(query=query, country=country, sector=sector, limit=limit, mode="normal")
    out["results"] = out.get("results", [])[: min(int(limit or 10), 50)]
    out["mode"] = "normal"
    out["count"] = len(out["results"])
    return out


def premium_search_service(query: str, country: str, sector: str = "", limit: int = 10) -> dict[str, Any]:
    try:
        base = shared_search_pipeline(query=query, country=country, sector=sector, limit=limit, mode="premium")
        premium_rows = [r for r in base["results"] if r.get("score") in {"HIGH", "MEDIUM"}]
        premium_rows = premium_rows[: min(10, max(1, int(limit or 10)))]
        return {
            "mode": "premium",
            "count": len(premium_rows),
            "results": premium_rows,
            "message": "" if premium_rows else EMPTY_MSG,
            "meta": base.get("meta", _empty_meta()),
        }
    except Exception as exc:
        logger.exception("premium_search_service failed, fallback to normal: %s", str(exc)[:240])
        fallback = normal_search_service(query=query, country=country, sector=sector, limit=limit)
        fallback["mode"] = "premium"
        fallback["message"] = fallback.get("message") or EMPTY_MSG
        return fallback
