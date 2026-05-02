from __future__ import annotations

import logging
import re
from typing import Any
from urllib.parse import urlparse

from app.core.config import settings
from app.providers.apollo_provider import ApolloProvider
from company_search_real import search_companies_real_with_meta

logger = logging.getLogger(__name__)


def _empty_meta() -> dict[str, Any]:
    return {
        "queries_used": [],
        "raw_results_count": 0,
        "valid_results_count": 0,
        "discarded_results_count": 0,
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


def _internal_rows(query: str, country: str, limit: int) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    try:
        rows, meta = search_companies_real_with_meta(query, country, limit)
        return rows or [], meta or _empty_meta()
    except Exception as exc:
        logger.exception("internal search fallback failed: %s", str(exc)[:200])
        return [], _empty_meta()


def shared_search_pipeline(query: str, country: str, sector: str = "", limit: int = 10) -> dict[str, Any]:
    meta = _empty_meta()
    requested_limit = max(1, min(int(limit or 10), 50))
    apollo_key = getattr(settings, "apollo_api_key", "") or ""
    combined: list[dict[str, Any]] = []

    if apollo_key:
        try:
            provider = ApolloProvider(api_key=apollo_key, timeout_seconds=5)
            apollo_rows_raw, apollo_meta = provider.search_organizations(query=query, country=country, sector=sector, limit=requested_limit)
            meta.update({k: apollo_meta.get(k, meta.get(k)) for k in apollo_meta.keys() if k in meta or k.startswith("apollo_")})
            normalized_apollo = []
            for row in apollo_rows_raw:
                norm = _normalize_apollo_row(row, query=query, country=country, sector=sector)
                if norm:
                    normalized_apollo.append(norm)
            combined.extend(normalized_apollo)
        except Exception as exc:
            logger.warning("Apollo path failed, switching to internal fallback: %s", str(exc)[:200])

    if len(combined) < requested_limit:
        internal_rows, internal_meta = _internal_rows(query=query, country=country, limit=requested_limit)
        combined.extend(internal_rows)
        meta["queries_used"] = internal_meta.get("queries_used", [])
        meta["raw_results_count"] = int(meta.get("raw_results_count", 0) or 0) + int(internal_meta.get("raw_results_count", 0) or 0)
        meta["discarded_results_count"] = int(internal_meta.get("discarded_results_count", 0) or 0)

    deduped = _dedupe_rows(combined)[:requested_limit]
    cleaned = []
    for item in deduped:
        if not item.get("name"):
            continue
        if not (item.get("website") or item.get("source_url")):
            continue
        if country and (item.get("country") or "").upper() == "GLOBAL":
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

    meta["valid_results_count"] = len(cleaned)
    return {
        "results": cleaned,
        "message": "" if cleaned else "Nessuna azienda trovata con criteri attuali",
        "meta": meta,
    }


def normal_search_service(query: str, country: str, sector: str = "", limit: int = 10) -> dict[str, Any]:
    out = shared_search_pipeline(query=query, country=country, sector=sector, limit=limit)
    out["results"] = out.get("results", [])[: min(int(limit or 10), 50)]
    out["mode"] = "normal"
    out["count"] = len(out["results"])
    return out


def premium_search_service(query: str, country: str, sector: str = "", limit: int = 10) -> dict[str, Any]:
    try:
        base = shared_search_pipeline(query=query, country=country, sector=sector, limit=limit)
        premium_rows = [r for r in base["results"] if r.get("score") in {"HIGH", "MEDIUM"}]
        premium_rows = premium_rows[: min(10, max(1, int(limit or 10)))]
        return {
            "mode": "premium",
            "count": len(premium_rows),
            "results": premium_rows,
            "message": "" if premium_rows else "Nessuna azienda trovata con criteri attuali",
            "meta": base.get("meta", _empty_meta()),
        }
    except Exception as exc:
        logger.exception("premium_search_service failed, fallback to normal: %s", str(exc)[:240])
        fallback = normal_search_service(query=query, country=country, sector=sector, limit=limit)
        fallback["mode"] = "premium"
        fallback["message"] = fallback.get("message") or "Fallback premium su ricerca normale"
        return fallback
