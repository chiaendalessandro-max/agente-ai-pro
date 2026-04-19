"""Provider ricerca / discovery: primario (DuckDuckGo) e fallback degradata."""
from __future__ import annotations

import asyncio
import logging
from urllib.parse import urlparse

from duckduckgo_search import DDGS

from app.core.config import settings
from app.services.data_quality import is_blocked_or_junk_domain, normalize_domain

logger = logging.getLogger(__name__)


def build_queries(seed: str, country: str = "", sector: str = "") -> list[str]:
    base = f"{seed.strip()} {sector.strip()}".strip()
    c = country.strip()
    return [
        f"{base} official website {c}".strip(),
        f"{base} enterprise solutions global".strip(),
        f"{base} corporate services".strip(),
        f"{base} site officiel entreprise".strip(),
        f"{base} sitio oficial empresa".strip(),
        f"{base} unternehmen offizielle website".strip(),
        f"{base} contatti azienda".strip(),
    ]


def _valid_href(url: str) -> bool:
    try:
        d = urlparse(url).netloc.lower().replace("www.", "")
    except Exception:
        return False
    if not d or is_blocked_or_junk_domain(d):
        return False
    return True


def _ddgs_collect_urls_sync(queries: list[str], max_urls: int) -> list[str]:
    seen: set[str] = set()
    websites: list[str] = []
    with DDGS() as ddgs:
        for q in queries:
            if len(websites) >= max_urls:
                break
            try:
                for item in ddgs.text(q, max_results=12):
                    url = item.get("href") or item.get("url") or ""
                    if not _valid_href(url):
                        continue
                    domain = normalize_domain(url)
                    if not domain or domain in seen:
                        continue
                    seen.add(domain)
                    websites.append(f"https://{domain}")
                    if len(websites) >= max_urls:
                        break
            except Exception as exc:
                logger.warning("DDGS query failed: %s | %s", q[:80], str(exc)[:200])
                continue
    return websites


async def discover_urls_primary(seed: str, country: str, sector: str, max_urls: int) -> list[str]:
    queries = build_queries(seed, country, sector)
    timeout = max(5, int(getattr(settings, "ddgs_timeout_seconds", 25)))
    try:
        return await asyncio.wait_for(
            asyncio.to_thread(_ddgs_collect_urls_sync, queries, max_urls),
            timeout=timeout,
        )
    except asyncio.TimeoutError:
        logger.error("DDGS primary timeout after %ss", timeout)
        return []
    except Exception as exc:
        logger.exception("DDGS primary failed: %s", str(exc)[:250])
        return []


async def discover_urls_fallback(seed: str, country: str, sector: str, max_urls: int) -> list[str]:
    """Query singola ridotta: meno carico, più probabilità di risposta parziale."""
    base = f"{seed.strip()} {sector.strip()} {country.strip()}".strip()
    q = f"{base} company official site".strip()[:300]
    timeout = max(5, int(getattr(settings, "ddgs_timeout_seconds", 25)))

    def _one() -> list[str]:
        out: list[str] = []
        seen: set[str] = set()
        with DDGS() as ddgs:
            try:
                for item in ddgs.text(q, max_results=max_urls + 5):
                    url = item.get("href") or item.get("url") or ""
                    if not _valid_href(url):
                        continue
                    dom = normalize_domain(url)
                    if dom in seen:
                        continue
                    seen.add(dom)
                    out.append(f"https://{dom}")
                    if len(out) >= max_urls:
                        break
            except Exception as exc:
                logger.warning("DDGS fallback query failed: %s", str(exc)[:200])
        return out

    try:
        return await asyncio.wait_for(asyncio.to_thread(_one), timeout=timeout)
    except asyncio.TimeoutError:
        logger.error("DDGS fallback timeout")
        return []
    except Exception as exc:
        logger.exception("DDGS fallback failed: %s", str(exc)[:250])
        return []
