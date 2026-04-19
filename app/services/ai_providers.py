"""Discovery URL via DuckDuckGo (HTTP + risultati reali), multi-query e logging."""
from __future__ import annotations

import asyncio
import logging
import re
from urllib.parse import urlparse

from duckduckgo_search import DDGS

from app.core.config import settings
from app.services.country_context import CountryContext
from app.services.data_quality import is_blocked_or_junk_domain, normalize_domain, normalize_website_url
from app.services.search_queries import build_search_queries

logger = logging.getLogger(__name__)

_DDGS_BACKENDS: tuple[str, ...] = ("lite", "html", "api")


def _valid_href(url: str) -> bool:
    try:
        d = urlparse(url).netloc.lower().replace("www.", "")
    except Exception:
        return False
    if not d or is_blocked_or_junk_domain(d):
        return False
    return True


def guess_brand_urls(seed: str, max_urls: int) -> list[str]:
    s = (seed or "").strip()
    if not s or " " in s or len(s) > 48:
        return []
    if not re.match(r"^[A-Za-z0-9][A-Za-z0-9\-]{0,46}[A-Za-z0-9]$", s):
        return []
    low = s.lower()
    raw = [
        f"https://www.{low}.com/",
        f"https://{low}.com/",
        f"https://www.{low}.io/",
        f"https://{low}.ai/",
    ]
    out: list[str] = []
    seen: set[str] = set()
    for u in raw:
        nu = normalize_website_url(u)
        if not nu:
            continue
        dom = normalize_domain(nu)
        if not dom or dom in seen or is_blocked_or_junk_domain(dom):
            continue
        seen.add(dom)
        out.append(nu.rstrip("/") + "/")
        if len(out) >= max_urls:
            break
    if out:
        logger.info("guess_brand_urls: %s -> %s", s, out)
    return out


def collect_search_urls_sync(
    seed: str,
    sector: str,
    country_ctx: CountryContext | None,
    *,
    min_urls: int,
    hard_cap: int,
    relaxed: bool,
) -> tuple[list[str], dict]:
    """
    Esegue tutte le query generate, prova backend DDGS in sequenza, dedup su dominio.
    Ritorna (urls, meta_debug).
    """
    queries = build_search_queries(seed, sector, country_ctx, relaxed=relaxed)
    region = country_ctx.ddgs_region if country_ctx else "wt-wt"
    meta: dict = {
        "queries": queries,
        "queries_run": 0,
        "ddgs_raw_hits": 0,
        "unique_urls": 0,
        "backend_last": "none",
        "region": region,
        "relaxed": relaxed,
    }
    logger.info(
        "search_start seed=%r sector=%r country=%s queries=%s relaxed=%s min_urls=%s cap=%s",
        seed[:80],
        sector[:40],
        country_ctx.iso2 if country_ctx else None,
        len(queries),
        relaxed,
        min_urls,
        hard_cap,
    )
    for q in queries[:25]:
        logger.debug("search_query: %s", q[:200])

    seen: set[str] = set()
    all_urls: list[str] = []

    for backend in _DDGS_BACKENDS:
        for q in queries:
            if len(all_urls) >= hard_cap:
                break
            meta["queries_run"] += 1
            try:
                with DDGS() as ddgs:
                    items = list(ddgs.text(q, max_results=28, backend=backend, region=region))
            except Exception as exc:
                logger.warning("DDGS fail backend=%s q=%s | %s", backend, q[:100], str(exc)[:200])
                continue
            meta["ddgs_raw_hits"] += len(items)
            for item in items:
                url = item.get("href") or item.get("url") or ""
                if not _valid_href(url):
                    continue
                dom = normalize_domain(url)
                if not dom or dom in seen:
                    continue
                seen.add(dom)
                all_urls.append(f"https://{dom}")
            if len(all_urls) >= hard_cap:
                break
        meta["backend_last"] = backend
        if len(all_urls) >= hard_cap:
            meta["unique_urls"] = len(all_urls)
            logger.info("search_collect_ok unique=%s (cap) backend=%s", len(all_urls), backend)
            return all_urls[:hard_cap], meta
        if len(all_urls) >= min_urls:
            logger.info(
                "search_collect_ok unique=%s backend=%s queries_run=%s raw_hits=%s",
                len(all_urls),
                backend,
                meta["queries_run"],
                meta["ddgs_raw_hits"],
            )
            meta["unique_urls"] = len(all_urls)
            return all_urls[:hard_cap], meta

    logger.warning(
        "search_collect_partial unique=%s backend=%s queries_run=%s raw_hits=%s",
        len(all_urls),
        meta["backend_last"],
        meta["queries_run"],
        meta["ddgs_raw_hits"],
    )
    meta["unique_urls"] = len(all_urls)
    return all_urls[:hard_cap], meta


async def collect_search_urls(
    seed: str,
    sector: str,
    country_ctx: CountryContext | None,
    *,
    min_urls: int,
    hard_cap: int,
    relaxed: bool,
) -> tuple[list[str], dict]:
    timeout = max(15, int(settings.ddgs_timeout_seconds) + (10 if relaxed else 0))
    try:
        return await asyncio.wait_for(
            asyncio.to_thread(collect_search_urls_sync, seed, sector, country_ctx, min_urls=min_urls, hard_cap=hard_cap, relaxed=relaxed),
            timeout=timeout,
        )
    except asyncio.TimeoutError:
        logger.error("search_collect timeout %ss relaxed=%s", timeout, relaxed)
        return [], {"error": "timeout", "queries": [], "queries_run": 0, "ddgs_raw_hits": 0, "unique_urls": 0, "backend_last": "none", "region": country_ctx.ddgs_region if country_ctx else "wt-wt", "relaxed": relaxed}
    except Exception as exc:
        logger.exception("search_collect error: %s", str(exc)[:250])
        return [], {"error": str(exc)[:120], "queries": [], "queries_run": 0, "ddgs_raw_hits": 0, "unique_urls": 0, "backend_last": "none", "region": country_ctx.ddgs_region if country_ctx else "wt-wt", "relaxed": relaxed}


# Compat orchestrator vecchi import (non usati dal nuovo flusso)
async def discover_urls_primary(seed: str, country: str, sector: str, max_urls: int) -> tuple[list[str], str]:
    from app.services.country_context import resolve_country

    ctx = resolve_country(country)
    urls, m = await collect_search_urls(seed, sector, ctx, min_urls=max(3, max_urls // 2), hard_cap=max_urls * 3, relaxed=False)
    return urls, str(m.get("backend_last") or "none")


async def discover_urls_fallback(seed: str, country: str, sector: str, max_urls: int) -> tuple[list[str], str]:
    from app.services.country_context import resolve_country

    ctx = resolve_country(country)
    urls, m = await collect_search_urls(seed, sector, ctx, min_urls=3, hard_cap=max_urls * 2, relaxed=True)
    return urls, str(m.get("backend_last") or "none")
