from __future__ import annotations

import logging
import re
from typing import Any
from urllib.parse import urlparse

from app.core.config import settings
from app.providers.apollo_provider import ApolloProvider
from search_country import normalize_country_for_apollo
from search_language_router import build_apollo_search_params, normalize_search_language

logger = logging.getLogger(__name__)

EMPTY_MSG = "Nessun risultato disponibile"
APOLLO_NOT_CONFIGURED_MSG = "Apollo non configurato"


def _empty_meta() -> dict[str, Any]:
    return {
        "queries_used": [],
        "raw_results_count": 0,
        "valid_results_count": 0,
        "discarded_results_count": 0,
        "search_language": "",
        "search_provider": "",
        "apollo_queries_submitted": [],
        "apollo_raw_merged_count": 0,
        "apollo_status": "",
    }


def _resolve_search_provider() -> str:
    raw = (getattr(settings, "search_provider", "") or "apollo").strip().lower()
    if raw not in {"apollo", "internal", "hybrid"}:
        return "apollo"
    return raw


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

    row_country = (row.get("country") or row.get("organization_country") or "").strip()
    return {
        "name": name,
        "domain": _domain(website or source_url),
        "website": website,
        "source_url": source_url,
        "country": row_country or country or "",
        "sector": sector or query,
        "description": (row.get("short_description") or row.get("description") or "")[:280],
        "contact_email": "",
        "contact_phone": (row.get("phone") or "").strip(),
        "score": score,
        "classification": "HIGH VALUE" if score >= 70 else "MEDIUM",
        "source": "apollo",
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


def _internal_rows(query: str, country: str, limit: int, *, mode: str) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    try:
        from company_search_real import search_companies_real_with_meta

        rows, meta = search_companies_real_with_meta(
            query, country, limit, mode=mode, minimal_internal=True
        )
        return rows or [], meta or _empty_meta()
    except Exception as exc:
        logger.exception("internal search fallback failed: %s", str(exc)[:200])
        return [], _empty_meta()


def _format_internal_row(item: dict[str, Any]) -> dict[str, Any] | None:
    name = item.get("name") or item.get("company_name")
    if not name:
        return None
    website = item.get("website") or ""
    source_url = item.get("source_url") or website
    if not (website or source_url):
        return None
    score_value = int(item.get("score") or 0)
    if isinstance(item.get("score"), str):
        band = item.get("score")
    else:
        band = _score_band(score_value)
    return {
        "company_name": name,
        "website": website,
        "source_url": source_url,
        "country": item.get("country") or "",
        "score": band if isinstance(band, str) else _score_band(score_value),
        "classification": item.get("classification", "LOW"),
        "contact_email": item.get("contact_email", ""),
        "contact_phone": item.get("contact_phone", ""),
        "why_this_company": _why_this_company(item),
        "client_probability": _client_probability(item),
        "source": "internal",
    }


def _apollo_search(
    query: str,
    country: str,
    sector: str,
    limit: int,
    *,
    mode: str,
    language: str,
    meta: dict[str, Any],
) -> list[dict[str, Any]]:
    apollo_key = (getattr(settings, "apollo_api_key", "") or "").strip()
    if not apollo_key:
        meta["apollo_status"] = "not_configured"
        return []

    lang_code = normalize_search_language(language)
    country_norm = normalize_country_for_apollo(country)
    lang_used, org_query, main_kw = build_apollo_search_params(
        lang_code, query, country_norm, sector or "", mode=mode
    )
    meta["search_language"] = lang_used
    meta["queries_used"] = [org_query]
    meta["apollo_queries_submitted"] = [org_query]
    if main_kw:
        meta["queries_used"].append(f"keyword:{main_kw}")

    provider = ApolloProvider(api_key=apollo_key, timeout_seconds=5)
    try:
        raw_rows, apollo_meta = provider.search_organizations(
            org_query,
            country_norm,
            main_kw,
            limit,
            max_pages=2,
        )
    except Exception as exc:
        logger.warning("Apollo search failed: %s", str(exc)[:240])
        meta["apollo_status"] = "request_error"
        meta["apollo_raw_merged_count"] = 0
        meta["raw_results_count"] = 0
        return []

    for mk, mv in (apollo_meta or {}).items():
        if str(mk).startswith("apollo_"):
            meta[mk] = mv
    meta["apollo_raw_merged_count"] = len(raw_rows)
    meta["raw_results_count"] = len(raw_rows)
    if not meta.get("apollo_status"):
        meta["apollo_status"] = apollo_meta.get("apollo_status", "ok")

    combined: list[dict[str, Any]] = []
    for row in raw_rows:
        norm = _normalize_apollo_row(row, query=query, country=country_norm, sector=sector or "")
        if norm:
            combined.append(norm)
    return combined


def _finalize_rows(
    combined: list[dict[str, Any]],
    country: str,
    requested_limit: int,
    meta: dict[str, Any],
    *,
    source: str,
) -> dict[str, Any]:
    deduped = _dedupe_rows(combined)[:requested_limit]
    cleaned: list[dict[str, Any]] = []
    discarded = 0
    for item in deduped:
        if source == "apollo":
            if not item.get("name"):
                discarded += 1
                continue
            if not (item.get("website") or item.get("source_url")):
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
                    "source": "apollo",
                }
            )
        else:
            row = _format_internal_row(item)
            if not row:
                discarded += 1
                continue
            cleaned.append(row)

    meta["discarded_results_count"] = int(meta.get("discarded_results_count", 0) or 0) + discarded
    meta["valid_results_count"] = len(cleaned)
    return {
        "results": cleaned,
        "message": "" if cleaned else EMPTY_MSG,
        "meta": meta,
    }


def shared_search_pipeline(
    query: str,
    country: str,
    sector: str = "",
    limit: int = 10,
    *,
    mode: str = "normal",
    language: str = "en",
) -> dict[str, Any]:
    meta = _empty_meta()
    requested_limit = max(1, min(int(limit or 10), 50))
    mode_norm = (mode or "normal").strip().lower()
    if mode_norm not in {"normal", "premium"}:
        mode_norm = "normal"

    provider_mode = _resolve_search_provider()
    meta["search_provider"] = provider_mode
    apollo_key = (getattr(settings, "apollo_api_key", "") or "").strip()
    combined: list[dict[str, Any]] = []

    if provider_mode == "apollo":
        if not apollo_key:
            meta["apollo_status"] = "not_configured"
            meta["search_language"] = normalize_search_language(language)
            return {
                "results": [],
                "message": APOLLO_NOT_CONFIGURED_MSG,
                "meta": meta,
            }
        combined = _apollo_search(
            query, country, sector or "", requested_limit, mode=mode_norm, language=language, meta=meta
        )
        out = _finalize_rows(combined, country, requested_limit, meta, source="apollo")
    elif provider_mode == "internal":
        meta["search_language"] = normalize_search_language(language)
        internal_rows, internal_meta = _internal_rows(query=query, country=country, limit=requested_limit, mode=mode_norm)
        meta["queries_used"] = internal_meta.get("queries_used", [])
        meta["raw_results_count"] = int(internal_meta.get("raw_results_count", 0) or 0)
        meta["discarded_results_count"] = int(internal_meta.get("discarded_results_count", 0) or 0)
        out = _finalize_rows(internal_rows, country, requested_limit, meta, source="internal")
    else:
        if apollo_key:
            combined = _apollo_search(
                query, country, sector or "", requested_limit, mode=mode_norm, language=language, meta=meta
            )
        if not combined:
            internal_rows, internal_meta = _internal_rows(
                query=query, country=country, limit=requested_limit, mode=mode_norm
            )
            if not meta.get("queries_used"):
                meta["queries_used"] = internal_meta.get("queries_used", [])
            meta["raw_results_count"] = int(meta.get("raw_results_count", 0) or 0) + int(
                internal_meta.get("raw_results_count", 0) or 0
            )
            meta["discarded_results_count"] = int(meta.get("discarded_results_count", 0) or 0) + int(
                internal_meta.get("discarded_results_count", 0) or 0
            )
            combined = internal_rows
            out = _finalize_rows(combined, country, requested_limit, meta, source="internal")
        else:
            out = _finalize_rows(combined, country, requested_limit, meta, source="apollo")

    logger.info(
        "[company-search] provider=%r lang=%r queries=%r apollo_raw=%s valid=%s apollo_status=%r",
        provider_mode,
        meta.get("search_language"),
        meta.get("queries_used"),
        meta.get("apollo_raw_merged_count"),
        meta.get("valid_results_count"),
        meta.get("apollo_status"),
    )
    return out


def normal_search_service(
    query: str, country: str, sector: str = "", limit: int = 10, language: str = "en"
) -> dict[str, Any]:
    out = shared_search_pipeline(
        query=query, country=country, sector=sector, limit=limit, mode="normal", language=language
    )
    out["results"] = out.get("results", [])[: min(int(limit or 10), 50)]
    out["mode"] = "normal"
    out["count"] = len(out["results"])
    return out


def premium_search_service(
    query: str, country: str, sector: str = "", limit: int = 10, language: str = "en"
) -> dict[str, Any]:
    try:
        base = shared_search_pipeline(
            query=query,
            country=country,
            sector=sector,
            limit=limit,
            mode="premium",
            language=language,
        )
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
        logger.exception("premium_search_service failed: %s", str(exc)[:240])
        return {
            "mode": "premium",
            "count": 0,
            "results": [],
            "message": EMPTY_MSG,
            "meta": _empty_meta(),
        }
