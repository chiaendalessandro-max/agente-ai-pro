"""Provider ricerca / discovery: primario (DuckDuckGo) e fallback degradata."""
from __future__ import annotations

import asyncio
import logging
import re
from urllib.parse import urlparse

from duckduckgo_search import DDGS

from app.core.config import settings
from app.services.data_quality import is_blocked_or_junk_domain, normalize_domain, normalize_website_url

logger = logging.getLogger(__name__)

# Su server cloud (Render) il backend "auto"/"api" spesso restituisce []: provare in ordine.
_DDGS_BACKENDS: tuple[str, ...] = ("lite", "html", "api")


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


def _ddgs_collect_urls_sync(queries: list[str], max_urls: int) -> tuple[list[str], str]:
    """Ritorna (urls, backend_usato)."""
    for backend in _DDGS_BACKENDS:
        seen: set[str] = set()
        websites: list[str] = []
        with DDGS() as ddgs:
            for q in queries:
                if len(websites) >= max_urls:
                    break
                try:
                    for item in ddgs.text(q, max_results=15, backend=backend, region="wt-wt"):
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
                    logger.warning("DDGS query failed backend=%s q=%s | %s", backend, q[:80], str(exc)[:200])
                    continue
        if websites:
            logger.info("DDGS collected %s urls backend=%s", len(websites), backend)
            return websites[:max_urls], backend
    logger.warning("DDGS: zero URL da tutte le query (backend provati: %s)", ",".join(_DDGS_BACKENDS))
    return [], "none"


def guess_brand_urls(seed: str, max_urls: int) -> list[str]:
    """
    Se la query è un singolo token tipo brand (es. OpenAI), prova URL corporate comuni.
    Utile quando DDGS non risponde sugli IP datacenter.
    """
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


async def discover_urls_primary(seed: str, country: str, sector: str, max_urls: int) -> tuple[list[str], str]:
    queries = build_queries(seed, country, sector)
    timeout = max(5, int(getattr(settings, "ddgs_timeout_seconds", 25)))
    try:
        urls, backend = await asyncio.wait_for(
            asyncio.to_thread(_ddgs_collect_urls_sync, queries, max_urls),
            timeout=timeout,
        )
        return urls, backend
    except asyncio.TimeoutError:
        logger.error("DDGS primary timeout after %ss", timeout)
        return [], "timeout"
    except Exception as exc:
        logger.exception("DDGS primary failed: %s", str(exc)[:250])
        return [], "error"


async def discover_urls_fallback(seed: str, country: str, sector: str, max_urls: int) -> tuple[list[str], str]:
    """Query singola ridotta: meno carico, più probabilità di risposta parziale."""
    base = f"{seed.strip()} {sector.strip()} {country.strip()}".strip()
    q = f"{base} company official site".strip()[:300]
    timeout = max(5, int(getattr(settings, "ddgs_timeout_seconds", 25)))

    def _one() -> tuple[list[str], str]:
        for backend in _DDGS_BACKENDS:
            out: list[str] = []
            seen: set[str] = set()
            with DDGS() as ddgs:
                try:
                    for item in ddgs.text(q, max_results=max_urls + 8, backend=backend, region="wt-wt"):
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
                    logger.warning("DDGS fallback failed backend=%s: %s", backend, str(exc)[:200])
                    continue
            if out:
                return out[:max_urls], backend
        return [], "none"

    try:
        return await asyncio.wait_for(asyncio.to_thread(_one), timeout=timeout)
    except asyncio.TimeoutError:
        logger.error("DDGS fallback timeout")
        return [], "timeout"
    except Exception as exc:
        logger.exception("DDGS fallback failed: %s", str(exc)[:250])
        return [], "error"
