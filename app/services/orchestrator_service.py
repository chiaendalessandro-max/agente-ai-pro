"""Orchestrazione discovery lead: provider, fallback, analisi parallela, output normalizzato."""
from __future__ import annotations

import asyncio
import logging

from app.core.config import settings
from app.services.ai_providers import discover_urls_fallback, discover_urls_primary, guess_brand_urls
from app.services.analyzer_service import safe_analyze_company
from app.services.data_quality import dedupe_leads_by_domain, normalize_lead_dict
from app.services.scoring_service import score_lead

logger = logging.getLogger(__name__)


async def _analyze_and_score_one(site: str, seed: str) -> dict | None:
    analyzed = await safe_analyze_company(site)
    if not analyzed:
        return None
    try:
        score, classification = score_lead(
            {
                "website": analyzed.get("website", ""),
                "description": analyzed.get("description", ""),
                "sector": analyzed.get("sector", ""),
                "size_estimate": analyzed.get("size_estimate", ""),
                "international_presence": int(analyzed.get("international_presence") or 0),
                "has_corporate_email": bool(analyzed.get("contact_email")),
                "has_phone": bool(analyzed.get("contact_phone")),
            }
        )
    except Exception as exc:
        logger.warning("score_lead failed for %s: %s", site, str(exc)[:200])
        score, classification = 0, "LOW"
    analyzed["score"] = score
    analyzed["classification"] = classification
    analyzed["source_query"] = seed
    return normalize_lead_dict(analyzed, seed)


async def run_global_search(seed: str, country: str, sector: str, limit: int) -> dict:
    """
    Non solleva eccezioni verso l'API: restituisce sempre struttura coerente.
    """
    limit = max(1, min(50, int(limit)))
    meta: dict = {
        "primary_urls": 0,
        "fallback_urls": 0,
        "provider_path": "primary",
        "ddgs_primary_backend": "",
        "ddgs_fallback_backend": "",
        "brand_guess_urls": 0,
    }
    urls, backend_p = await discover_urls_primary(seed, country, sector, limit)
    meta["primary_urls"] = len(urls)
    meta["ddgs_primary_backend"] = backend_p

    if len(urls) < min(3, limit):
        extra, backend_f = await discover_urls_fallback(seed, country, sector, limit)
        meta["fallback_urls"] = len(extra)
        meta["ddgs_fallback_backend"] = backend_f
        seen = {u.rstrip("/").lower() for u in urls}
        for u in extra:
            k = u.rstrip("/").lower()
            if k not in seen:
                seen.add(k)
                urls.append(u)
        meta["provider_path"] = "primary+fallback" if extra else "primary"

    if not urls:
        guessed = guess_brand_urls(seed, limit)
        meta["brand_guess_urls"] = len(guessed)
        urls = guessed
        meta["provider_path"] = "brand_url_guess"
    elif urls and len(urls) < limit:
        guessed = guess_brand_urls(seed, limit)
        seen = {u.rstrip("/").lower() for u in urls}
        added = 0
        for u in guessed:
            k = u.rstrip("/").lower()
            if k not in seen:
                seen.add(k)
                urls.append(u)
                added += 1
                if len(urls) >= limit:
                    break
        if added:
            meta["brand_guess_urls"] = added
            meta["provider_path"] = (meta.get("provider_path") or "primary") + "+brand_hint"

    urls = urls[:limit]
    sem = asyncio.Semaphore(max(1, min(8, int(settings.analyze_concurrency))))

    async def _one(site: str) -> dict | None:
        async with sem:
            try:
                return await asyncio.wait_for(
                    _analyze_and_score_one(site, seed),
                    timeout=max(8, int(settings.request_timeout_seconds) + 5),
                )
            except asyncio.TimeoutError:
                logger.warning("analyze timeout: %s", site[:120])
                return None
            except Exception as exc:
                logger.warning("analyze failed: %s | %s", site[:120], str(exc)[:200])
                return None

    tasks = [_one(site) for site in urls]
    parts = await asyncio.gather(*tasks, return_exceptions=False)
    leads: list[dict] = [p for p in parts if isinstance(p, dict)]
    leads = dedupe_leads_by_domain(leads)
    leads.sort(key=lambda x: int(x.get("score") or 0), reverse=True)
    return {"results": leads, "meta": meta}
