"""Orchestrazione discovery: multi-query DDGS, filtro paese, confidence, riempimento risultati."""
from __future__ import annotations

import asyncio
import logging

from app.core.config import settings
from app.services.ai_providers import collect_search_urls, guess_brand_urls
from app.services.analyzer_service import safe_analyze_company
from app.services.confidence_score import compute_lead_confidence
from app.services.country_context import resolve_country
from app.services.data_quality import dedupe_leads_by_domain, normalize_domain, normalize_lead_dict
from app.services.scoring_service import score_lead

logger = logging.getLogger(__name__)


def _merge_urls(
    base: list[str],
    extra: list[str],
    sources: dict[str, str],
    source_tag: str,
) -> list[str]:
    seen = {normalize_domain(u) for u in base}
    out = list(base)
    for u in extra:
        d = normalize_domain(u)
        if not d or d in seen:
            continue
        seen.add(d)
        out.append(u)
        sources[d] = source_tag
    return out


async def _analyze_one(
    site: str,
    seed: str,
    *,
    filter_country_iso2: str | None,
    discovery_source: str,
) -> dict | None:
    analyzed = await safe_analyze_company(site, filter_country_iso2=filter_country_iso2)
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
    normalized = normalize_lead_dict(analyzed, seed)
    return normalized


async def run_global_search(
    seed: str,
    country: str,
    sector: str,
    limit: int,
    min_confidence: float = 0.32,
) -> dict:
    limit = max(1, min(50, int(limit)))
    min_confidence = max(0.08, min(0.95, float(min_confidence)))
    ctx = resolve_country(country)

    hard_cap = min(140, max(limit * 10, 45))
    min_urls = max(limit * 4, 24)

    meta: dict = {
        "country_resolved": ctx.iso2 if ctx else None,
        "discovery_passes": [],
        "urls_before_analyze": 0,
        "analyzed_ok": 0,
        "confidence_threshold": min_confidence,
        "brand_guess_urls": 0,
    }

    url_sources: dict[str, str] = {}
    urls: list[str] = []

    u1, d1 = await collect_search_urls(seed, sector, ctx, min_urls=min_urls, hard_cap=hard_cap, relaxed=False)
    meta["discovery_passes"].append(
        {"phase": "primary", **{k: d1[k] for k in ("queries_run", "ddgs_raw_hits", "unique_urls", "backend_last", "region") if k in d1}}
    )
    for u in u1:
        url_sources.setdefault(normalize_domain(u), "ddgs")
    urls = list(u1)

    if len(urls) < min_urls:
        u2, d2 = await collect_search_urls(seed, sector, ctx, min_urls=min_urls - len(urls), hard_cap=hard_cap, relaxed=True)
        meta["discovery_passes"].append(
            {"phase": "relaxed", **{k: d2[k] for k in ("queries_run", "ddgs_raw_hits", "unique_urls", "backend_last", "region") if k in d2}}
        )
        urls = _merge_urls(urls, u2, url_sources, "expanded")

    if len(urls) < max(limit, 8):
        guessed = guess_brand_urls(seed, min(6, limit))
        meta["brand_guess_urls"] = len(guessed)
        urls = _merge_urls(urls, guessed, url_sources, "brand_guess")

    urls = urls[:hard_cap]
    meta["urls_before_analyze"] = len(urls)
    filt_iso = ctx.iso2 if ctx else None

    sem = asyncio.Semaphore(max(1, min(8, int(settings.analyze_concurrency))))

    async def _worker(site: str) -> dict | None:
        async with sem:
            try:
                dom = normalize_domain(site)
                src = url_sources.get(dom, "ddgs")
                return await asyncio.wait_for(
                    _analyze_one(site, seed, filter_country_iso2=filt_iso, discovery_source=src),
                    timeout=max(12, int(settings.request_timeout_seconds) + 8),
                )
            except asyncio.TimeoutError:
                logger.warning("analyze timeout: %s", site[:120])
                return None
            except Exception as exc:
                logger.warning("analyze failed: %s | %s", site[:120], str(exc)[:200])
                return None

    parts = await asyncio.gather(*[_worker(u) for u in urls], return_exceptions=False)
    raw_leads: list[dict] = [p for p in parts if isinstance(p, dict)]
    meta["analyzed_ok"] = len(raw_leads)

    enriched: list[dict] = []
    for lead in raw_leads:
        dom = normalize_domain(lead.get("domain") or lead.get("website") or "")
        src = url_sources.get(dom, "ddgs")
        conf = compute_lead_confidence(lead, country_ctx=ctx, discovery_source=src)
        lead["confidence"] = conf
        lead["discovery_source"] = src
        enriched.append(lead)

    threshold = min_confidence
    passing = [L for L in enriched if float(L.get("confidence") or 0) >= threshold]
    eff = threshold
    if len(passing) < limit:
        lowered = max(0.1, min_confidence * 0.52)
        passing2 = [L for L in enriched if float(L.get("confidence") or 0) >= lowered]
        if len(passing2) > len(passing):
            passing = passing2
            eff = lowered
    meta["confidence_threshold_effective"] = eff

    if not passing:
        passing = sorted(enriched, key=lambda x: float(x.get("confidence") or 0), reverse=True)[: max(1, min(3, limit))]

    passing = dedupe_leads_by_domain(passing)
    passing.sort(key=lambda x: float(x.get("confidence") or 0) * (1 + int(x.get("score") or 0) / 100.0), reverse=True)
    results = passing[:limit]

    meta["results_returned"] = len(results)
    meta["provider_path"] = ">".join(p.get("phase", "?") for p in meta["discovery_passes"]) or "discovery"
    logger.info(
        "search_done seed=%r country=%s urls=%s analyzed=%s returned=%s eff_threshold=%s",
        seed[:60],
        meta.get("country_resolved"),
        meta.get("urls_before_analyze"),
        meta.get("analyzed_ok"),
        len(results),
        meta.get("confidence_threshold_effective", threshold),
    )
    return {"results": results, "meta": meta}
