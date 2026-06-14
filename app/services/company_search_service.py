"""Company Search interna a livelli (no provider a pagamento).

Pipeline (livelli del piano tecnico):
  L1 Query Engine     -> search_language_router (file lingua) + normalizzazione paese
  L2 Search Collector -> company_search_real (fetch web pubblico + estrazione URL)
  L3 Company Validator-> company_search_real (_phase_e_validate: scarta directory/articoli)
  L4 Data Extractor   -> company_search_real (_phase_f_enrich: email/telefono pubblici)
  L5 Revenue Resolver -> disattivato per ora: revenue = "not found" (mai inventato)
  L6 AI Analysis      -> opzionale e non bloccante (disattivata in produzione, niente Ollama)

Output: modello risultato del piano (company_name, website, country, sector, email,
phone, revenue, source_url, confidence_score, validation_status).
"""
from __future__ import annotations

import logging
from typing import Any

from search_country import normalize_country
from search_language_router import build_search_params, normalize_search_language

logger = logging.getLogger(__name__)

EMPTY_MSG = "Nessun risultato disponibile"
REVENUE_NOT_FOUND = "not found"

# Soglie premium: validazione più severa e priorità ai contatti.
_PREMIUM_MIN_CONFIDENCE = 60
_PREMIUM_MAX_RESULTS = 10


def _empty_meta() -> dict[str, Any]:
    return {
        "queries_used": [],
        "raw_results_count": 0,
        "valid_results_count": 0,
        "discarded_results_count": 0,
        "search_language": "",
        "engine": "internal",
    }


def _confidence(row: dict[str, Any]) -> int:
    try:
        return max(0, min(100, int(row.get("score") or 0)))
    except (TypeError, ValueError):
        return 0


def _to_result_model(row: dict[str, Any], requested_country: str, *, status: str = "verified") -> dict[str, Any]:
    website = (row.get("website") or "").strip()
    source_url = (row.get("source_url") or website).strip()
    return {
        "company_name": (row.get("name") or row.get("company_name") or "").strip(),
        "website": website,
        "country": (row.get("country") or requested_country or "").strip(),
        "sector": (row.get("sector") or "").strip(),
        "email": (row.get("contact_email") or row.get("email") or "").strip(),
        "phone": (row.get("contact_phone") or row.get("phone") or "").strip(),
        "revenue": REVENUE_NOT_FOUND,
        "source_url": source_url,
        "confidence_score": _confidence(row),
        "validation_status": status,
    }


def _run_internal(query: str, country: str, limit: int, *, mode: str) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    """L2-L4: import pigro perché il motore carica dipendenze pesanti (scraping)."""
    try:
        from company_search_real import search_companies_real_with_meta

        rows, meta = search_companies_real_with_meta(
            query, country, limit, mode=mode, minimal_internal=True
        )
        return rows or [], meta or {}
    except Exception as exc:
        logger.exception("internal engine failed: %s", str(exc)[:240])
        return [], {}


def _apply_premium(models: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """L_premium: validazione più severa, priorità a email/telefono/revenue, max 10."""
    with_contacts = [
        m for m in models
        if m["confidence_score"] >= _PREMIUM_MIN_CONFIDENCE and (m["email"] or m["phone"])
    ]
    high_conf = [m for m in models if m["confidence_score"] >= _PREMIUM_MIN_CONFIDENCE]
    pool = with_contacts or high_conf or models
    pool = sorted(
        pool,
        key=lambda m: (
            bool(m["email"] or m["phone"]),
            m["revenue"] != REVENUE_NOT_FOUND,
            m["confidence_score"],
        ),
        reverse=True,
    )
    for m in pool:
        m["validation_status"] = "verified"
    return pool[:_PREMIUM_MAX_RESULTS]


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
    mode_norm = "premium" if str(mode or "normal").strip().lower() == "premium" else "normal"

    country_norm = normalize_country(country)
    try:
        lang_used, org_query, main_kw = build_search_params(
            normalize_search_language(language), query, country_norm, sector or "", mode=mode_norm
        )
        meta["search_language"] = lang_used
        seed_query = org_query or query
        rows, raw_meta = _run_internal(seed_query, country_norm, requested_limit, mode=mode_norm)
        meta["queries_used"] = list(raw_meta.get("queries_used", []) or [])
        if main_kw:
            meta["queries_used"].append(f"keyword:{main_kw}")
        meta["raw_results_count"] = int(raw_meta.get("raw_results_count", 0) or 0)
        meta["discarded_results_count"] = int(raw_meta.get("discarded_results_count", 0) or 0)
    except Exception as exc:
        logger.exception("company search pipeline failed: %s", str(exc)[:240])
        rows = []

    models: list[dict[str, Any]] = []
    for r in rows:
        m = _to_result_model(r, country_norm)
        if not m["company_name"]:
            continue
        if not (m["website"] or m["source_url"]):
            continue
        models.append(m)

    if mode_norm == "premium":
        models = _apply_premium(models)

    models = models[:requested_limit]
    meta["valid_results_count"] = len(models)

    logger.info(
        "[company-search] mode=%s lang=%r queries=%r raw=%s valid=%s",
        mode_norm,
        meta.get("search_language"),
        meta.get("queries_used"),
        meta.get("raw_results_count"),
        len(models),
    )
    return {
        "results": models,
        "message": "" if models else EMPTY_MSG,
        "meta": meta,
    }


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
            query=query, country=country, sector=sector, limit=limit, mode="premium", language=language
        )
        rows = base["results"][:_PREMIUM_MAX_RESULTS]
        return {
            "mode": "premium",
            "count": len(rows),
            "results": rows,
            "message": "" if rows else EMPTY_MSG,
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
