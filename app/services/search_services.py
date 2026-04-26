from __future__ import annotations

import logging
from typing import Any

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


def shared_search_pipeline(query: str, country: str, limit: int) -> dict[str, Any]:
    meta = _empty_meta()
    try:
        results, raw_meta = search_companies_real_with_meta(query, country, limit)
        if isinstance(raw_meta, dict):
            meta.update({k: raw_meta.get(k, meta.get(k)) for k in meta.keys()})
    except Exception as exc:
        logger.exception("shared_search_pipeline failed: %s", str(exc)[:240])
        results = []

    cleaned = []
    for item in (results or []):
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
        "results": cleaned[: max(1, min(int(limit or 10), 50))],
        "message": "" if cleaned else "Nessuna azienda trovata con criteri attuali",
        "meta": meta,
    }


def normal_search_service(query: str, country: str, limit: int) -> dict[str, Any]:
    out = shared_search_pipeline(query, country, limit)
    out["mode"] = "normal"
    out["count"] = len(out["results"])
    return out


def premium_search_service(query: str, country: str, limit: int) -> dict[str, Any]:
    try:
        base = shared_search_pipeline(query, country, limit)
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
        fallback = normal_search_service(query, country, limit)
        fallback["mode"] = "premium"
        fallback["message"] = fallback.get("message") or "Fallback premium su ricerca normale"
        return fallback
