import logging
import re
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from concurrent.futures import TimeoutError as FuturesTimeout
from urllib.parse import quote_plus, urlparse

import requests
from bs4 import BeautifulSoup
from duckduckgo_search import DDGS
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

from ai_company_helper import ai_enrich_company, ai_expand_search_queries, is_ollama_available

logger = logging.getLogger(__name__)

COUNTRY_CONFIG = {
    "italia": {"lang": "it", "tld": ".it", "region": "it-it", "aliases": ("italia", "italy", "italian")},
    "italy": {"lang": "it", "tld": ".it", "region": "it-it", "aliases": ("italia", "italy", "italian")},
    "france": {"lang": "fr", "tld": ".fr", "region": "fr-fr", "aliases": ("france", "french")},
    "germany": {"lang": "de", "tld": ".de", "region": "de-de", "aliases": ("germany", "deutschland", "german")},
    "spain": {"lang": "es", "tld": ".es", "region": "es-es", "aliases": ("spain", "espana", "spanish")},
    "uk": {"lang": "en", "tld": ".co.uk", "region": "uk-en", "aliases": ("uk", "united kingdom", "british")},
    "usa": {"lang": "en", "tld": ".com", "region": "us-en", "aliases": ("usa", "united states", "american")},
}

BLACKLIST_DOMAINS = (
    "google.", "bing.", "yahoo.", "duckduckgo.com", "wikipedia.", "youtube.", "facebook.", "twitter.", "x.com",
    "instagram.", "reddit.", "amazon.", "linkedin.com/in/", "tiktok.", "pinterest.", "tripadvisor.", "medium.com",
    "blog.", "/blog", "news.", "forbes.com", "bloomberg.com", "reuters.com", "nytimes.com", "wsj.com", "ft.com",
)

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/125.0 Safari/537.36",
    "Accept-Language": "it-IT,it;q=0.9,en-US;q=0.8,en;q=0.7",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
}

_SESSION = requests.Session()
_SESSION.mount("http://", HTTPAdapter(max_retries=Retry(total=2, backoff_factor=0.3, status_forcelist=[429, 500, 502, 503, 504])))
_SESSION.mount("https://", HTTPAdapter(max_retries=Retry(total=2, backoff_factor=0.3, status_forcelist=[429, 500, 502, 503, 504])))

_SEARCH_CACHE: dict[str, tuple[float, tuple[list[dict], dict]]] = {}
_SEARCH_CACHE_TTL_SECONDS = 180


def _norm_domain(url: str) -> str:
    try:
        return (urlparse(url).netloc or "").lower().replace("www.", "")
    except Exception:
        return ""


def _safe_get(url: str, timeout: int = 4) -> str:
    r = _SESSION.get(url, headers=HEADERS, timeout=timeout, allow_redirects=True)
    r.raise_for_status()
    return r.text


def _country_ctx(country: str) -> dict:
    return COUNTRY_CONFIG.get((country or "").strip().lower(), {"lang": "en", "tld": "", "region": "wt-wt", "aliases": ((country or "").lower(),)})


def _phase_a_query_builder(query: str, country: str, expanded: bool = False) -> list[str]:
    ctx = _country_ctx(country)
    q = (query or "").strip()
    aliases = list(ctx.get("aliases") or [country or ""])
    country_en = aliases[1] if len(aliases) > 1 else (country or "")
    country_local = aliases[0] if aliases else (country or "")
    base = [
        f"{q} companies {country_en}",
        f"{q} firms {country_en}",
        f"{q} services {country_en}",
        f"{q} official website {country_en}",
        f"{q} corporate {country_en}",
        f"aziende {q} {country_local}",
        f"elenco aziende {q} {country_local}",
        f"{q} operatori {country_local}",
    ]
    if expanded:
        base.extend(
            [
                f"{q} b2b companies europe",
                f"{q} enterprise providers {country_en}",
                f"{q} suppliers {country_local}",
                f"{q} professional services europe",
            ]
        )
    out = []
    seen = set()
    for x in base:
        k = re.sub(r"\s+", " ", x).strip().lower()
        if k and k not in seen:
            seen.add(k)
            out.append(k)
    return out[:10]


def _fetch_bing(query: str) -> list[dict]:
    out = []
    try:
        html = _safe_get(f"https://www.bing.com/search?q={quote_plus(query)}&count=20&setlang=en", timeout=4)
        soup = BeautifulSoup(html, "lxml")
        for li in soup.select("li.b_algo"):
            a = li.select_one("h2 a")
            p = li.select_one("p, .b_caption p")
            if a and a.get("href"):
                out.append({"title": a.get_text(" ", strip=True), "url": a.get("href", ""), "snippet": p.get_text(" ", strip=True) if p else "", "source": "bing"})
    except Exception as e:
        logger.warning("[FETCH] bing_fail query=%r err=%s", query[:80], str(e)[:120])
    return out


def _fetch_ddg_html(query: str) -> list[dict]:
    out = []
    try:
        html = _safe_get(f"https://html.duckduckgo.com/html/?q={quote_plus(query)}", timeout=4)
        soup = BeautifulSoup(html, "lxml")
        for row in soup.select(".result"):
            a = row.select_one(".result__a")
            s = row.select_one(".result__snippet")
            if a and a.get("href"):
                out.append({"title": a.get_text(" ", strip=True), "url": a.get("href", ""), "snippet": s.get_text(" ", strip=True) if s else "", "source": "ddg_html"})
    except Exception as e:
        logger.warning("[FETCH] ddg_html_fail query=%r err=%s", query[:80], str(e)[:120])
    return out


def _fetch_ddgs(query: str, region: str) -> list[dict]:
    out = []
    for backend in ("lite", "html", "api"):
        try:
            with DDGS() as ddgs:
                rows = list(ddgs.text(query, max_results=25, backend=backend, region=region))
            for r in rows:
                out.append({"title": (r.get("title") or "").strip(), "url": r.get("href") or r.get("url") or "", "snippet": (r.get("body") or "").strip(), "source": f"ddgs_{backend}"})
            if rows:
                break
        except Exception:
            continue
    return out


def _phase_b_fetch(queries: list[str], country: str) -> list[dict]:
    ctx = _country_ctx(country)
    region = ctx.get("region", "wt-wt")
    raw: list[dict] = []

    def _fetch_one(q: str) -> list[dict]:
        local: list[dict] = []
        try:
            local.extend(_fetch_ddgs(q, region))
            local.extend(_fetch_bing(q))
            local.extend(_fetch_ddg_html(q))
        except Exception as exc:
            logger.warning("[FETCH] batch_fail query=%r err=%s", q[:80], str(exc)[:120])
        return local

    workers = min(8, max(1, len(queries)))
    if not queries:
        return raw
    with ThreadPoolExecutor(max_workers=workers) as ex:
        futures = [ex.submit(_fetch_one, q) for q in queries]
        for fut in as_completed(futures):
            try:
                raw.extend(fut.result())
            except Exception as exc:
                logger.warning("[FETCH] future_failed err=%s", str(exc)[:120])
    return raw


def _is_company_like_domain(url: str) -> bool:
    d = _norm_domain(url)
    if not d or "." not in d:
        return False
    u = (url or "").lower()
    if any(b in d or b in u for b in BLACKLIST_DOMAINS):
        return False
    if any(k in u for k in ("/article", "/news", "/blog", "/post", "/story")):
        return False
    return True


def _phase_c_extract(raw_rows: list[dict]) -> list[dict]:
    out = []
    for r in raw_rows:
        url = (r.get("url") or "").strip()
        if not url:
            continue
        if not url.startswith("http"):
            url = "https://" + url.lstrip("/")
        if not _is_company_like_domain(url):
            continue
        d = _norm_domain(url)
        title = (r.get("title") or "").strip()
        name = re.sub(r"\s{2,}", " ", re.sub(r"[\|\-].*$", "", title)).strip()
        if not name:
            name = d.split(".")[0].replace("-", " ").title()
        out.append(
            {
                "company_name": name,
                "website": f"https://{d}/",
                "source_url": url,
                "domain": d,
                "snippet": (r.get("snippet") or "").strip(),
                "raw_source": r.get("source") or "web",
            }
        )
    return out


def _phase_d_normalize_dedup(rows: list[dict]) -> list[dict]:
    seen = set()
    out = []
    for r in rows:
        d = (r.get("domain") or "").lower()
        if not d or d in seen:
            continue
        seen.add(d)
        nm = re.sub(r"[^A-Za-z0-9\s&.\-]", "", (r.get("company_name") or "")).strip()
        if len(nm) > 70:
            nm = d.split(".")[0].replace("-", " ").title()
        r["company_name"] = nm
        out.append(r)
    return out


def _country_ok(row: dict, country: str) -> bool:
    if not country:
        return True
    ctx = _country_ctx(country)
    tld = ctx.get("tld", "")
    aliases = ctx.get("aliases", ())
    text = f"{row.get('source_url','')} {row.get('snippet','')}".lower()
    if tld and tld in (row.get("website") or "").lower():
        return True
    return any(a and a in text for a in aliases)


def _phase_e_validate(rows: list[dict], query: str, country: str) -> tuple[list[dict], dict]:
    discarded = {"missing_fields": 0, "non_company": 0, "country_mismatch": 0, "invalid_name": 0}
    q_words = {w for w in re.findall(r"[a-zA-Z]{3,}", (query or "").lower())}
    q_lower = (query or "").lower()
    aviation_keywords = (
        "jet",
        "aviation",
        "charter",
        "air",
        "aero",
        "flight",
        "aviazione",
        "aerotaxi",
        "elicotter",
        "helicopter",
        "aircraft",
        "airline",
    )
    aviation_query = any(k in q_lower for k in aviation_keywords)
    valid = []
    for r in rows:
        if not r.get("company_name") or not (r.get("website") or r.get("source_url")):
            discarded["missing_fields"] += 1
            continue
        if not _is_company_like_domain(r.get("source_url") or r.get("website")):
            discarded["non_company"] += 1
            continue
        if not _country_ok(r, country):
            discarded["country_mismatch"] += 1
            continue
        nm = (r.get("company_name") or "").lower()
        if nm in {"about us", "italy", "home", "contact", "news"}:
            discarded["invalid_name"] += 1
            continue
        if len(nm) < 3 or nm in {"global", "international", "directory"}:
            discarded["invalid_name"] += 1
            continue
        bag = f"{nm} {(r.get('snippet') or '').lower()} {(r.get('domain') or '').lower()}"
        if aviation_query and not any(k in bag for k in aviation_keywords):
            discarded["invalid_name"] += 1
            continue
        if q_words:
            hay = f"{nm} {(r.get('snippet') or '').lower()} {(r.get('domain') or '').lower()}"
            if not any(w in hay for w in q_words):
                discarded["invalid_name"] += 1
                continue
        valid.append(r)
    return valid, discarded


def _contacts(website: str) -> tuple[str, str]:
    try:
        html = _safe_get(website, timeout=4)
        text = BeautifulSoup(html, "lxml").get_text(" ", strip=True)[:25000]
        em = re.findall(r"[A-Z0-9._%+\-]+@[A-Z0-9.\-]+\.[A-Z]{2,}", text, re.I)
        ph = re.findall(r"(\+?\d[\d\s().-]{7,}\d)", text)
        return (em[0].lower() if em else ""), (ph[0].strip() if ph else "")
    except Exception:
        return "", ""


def _contacts_from_snippet(snippet: str) -> tuple[str, str]:
    s = (snippet or "")[:8000]
    em = re.findall(r"[A-Z0-9._%+\-]+@[A-Z0-9.\-]+\.[A-Z]{2,}", s, re.I)
    ph = re.findall(r"(\+?\d[\d\s().-]{7,}\d)", s)
    return (em[0].lower() if em else ""), (ph[0].strip() if ph else "")


def _classify_score(has_contacts: bool, snippet: str) -> tuple[int, str]:
    score = 45
    s = (snippet or "").lower()
    if has_contacts:
        score += 25
    if any(k in s for k in ("international", "global", "operator", "manufacturer", "corporate")):
        score += 15
    if any(k in s for k in ("blog", "news", "article")):
        score -= 20
    score = max(1, min(100, score))
    if score >= 70:
        return score, "HIGH VALUE"
    if score >= 45:
        return score, "MEDIUM"
    return score, "LOW"


def _phase_f_enrich(rows: list[dict], query: str, country: str, use_ai: bool) -> list[dict]:
    out = []
    max_contact_scans = 5
    max_ai_rows = 3
    homepage_fetch_budget = 0
    ai_calls = 0
    for r in rows:
        email, phone = _contacts_from_snippet(r.get("snippet", ""))
        has_core = bool(r.get("company_name") and r.get("domain") and (r.get("snippet") or "").strip())
        if (not email and not phone) and homepage_fetch_budget < max_contact_scans:
            email, phone = _contacts(r.get("website", ""))
            homepage_fetch_budget += 1
        has_contacts = bool(email or phone)
        score, cls = _classify_score(has_contacts, r.get("snippet", ""))
        item = {
            "name": r.get("company_name"),
            "domain": r.get("domain"),
            "website": r.get("website"),
            "source_url": r.get("source_url"),
            "country": country or "",
            "sector": query,
            "description": r.get("snippet", "")[:280],
            "size_estimate": "SMB",
            "international_presence": 1 if "international" in (r.get("snippet", "").lower()) else 0,
            "value_signals": r.get("snippet", "")[:160],
            "contact_email": email,
            "contact_phone": phone,
            "contact_page": "",
            "score": score,
            "classification": cls,
        }
        if use_ai and (not has_core) and ai_calls < max_ai_rows:
            ai_calls += 1
            try:
                with ThreadPoolExecutor(max_workers=1) as ex:
                    fut = ex.submit(ai_enrich_company, item["name"], item["description"], query)
                    extra = fut.result(timeout=2.5)
                if isinstance(extra, dict):
                    item.update(extra)
            except FuturesTimeout:
                logger.warning("[AI] enrich_timeout name=%r", (item.get("name") or "")[:80])
            except Exception:
                pass
        out.append(item)
    return out


def search_companies_real(query: str, country: str, num_results: int = 10) -> list[dict]:
    results, _ = search_companies_real_with_meta(query, country, num_results, mode="normal")
    return results


def search_companies_real_with_meta(
    query: str,
    country: str,
    num_results: int = 10,
    *,
    mode: str = "normal",
    minimal_internal: bool = False,
) -> tuple[list[dict], dict]:
    target = max(1, min(50, int(num_results or 10)))
    mode_norm = (mode or "normal").strip().lower()
    if mode_norm not in {"normal", "premium"}:
        mode_norm = "normal"
    cache_key = f"{mode_norm}|mi:{int(bool(minimal_internal))}|{(query or '').strip().lower()}|{(country or '').strip().lower()}|{target}"
    now = time.time()
    cached = _SEARCH_CACHE.get(cache_key)
    if cached and (now - cached[0]) <= _SEARCH_CACHE_TTL_SECONDS:
        payload = cached[1]
        meta_cached = dict(payload[1])
        meta_cached["cache_hit"] = True
        meta_cached["cache_age_seconds"] = round(now - cached[0], 3)
        return payload[0], meta_cached

    meta = {
        "queries_used": [],
        "raw_results_count": 0,
        "valid_results_count": 0,
        "discarded_results_count": 0,
        "cache_hit": False,
    }
    try:
        try:
            if minimal_internal:
                use_ai = False
            else:
                use_ai = is_ollama_available()
        except Exception:
            use_ai = False

        try:
            queries = _phase_a_query_builder(query, country, expanded=False)
            if use_ai and not minimal_internal:
                try:
                    queries.extend([q for q in ai_expand_search_queries(query, country) if isinstance(q, str)])
                except Exception as exc:
                    logger.warning("[DEBUG] ai_expand_failed: %s", str(exc)[:120])
            queries = list(dict.fromkeys(queries))[:10]
        except Exception as exc:
            logger.warning("[DEBUG] phase_query_builder_failed: %s", str(exc)[:120])
            queries = []
        meta["queries_used"] = queries
        logger.info("[DEBUG] queries_generated=%s %s", len(queries), queries)

        try:
            raw = _phase_b_fetch(queries, country) if queries else []
        except Exception as exc:
            logger.warning("[DEBUG] phase_fetch_failed: %s", str(exc)[:120])
            raw = []
        meta["raw_results_count"] = len(raw)
        logger.info("[DEBUG] raw_results_count=%s", len(raw))

        try:
            extracted = _phase_c_extract(raw)
        except Exception as exc:
            logger.warning("[DEBUG] phase_extract_failed: %s", str(exc)[:120])
            extracted = []
        try:
            deduped = _phase_d_normalize_dedup(extracted)
        except Exception as exc:
            logger.warning("[DEBUG] phase_dedup_failed: %s", str(exc)[:120])
            deduped = extracted
        try:
            valid, discarded = _phase_e_validate(deduped, query, country)
        except Exception as exc:
            logger.warning("[DEBUG] phase_validate_failed: %s", str(exc)[:120])
            valid, discarded = [], {"failed_validation_phase": len(deduped)}

        early_stop_at = 5 if mode_norm == "premium" else 10
        need_more_fetch = len(valid) < target and len(valid) < early_stop_at

        if need_more_fetch:
            try:
                q2 = _phase_a_query_builder(query, country, expanded=True)
                if use_ai and not minimal_internal:
                    try:
                        q2.extend([q for q in ai_expand_search_queries(f"{query} companies", country) if isinstance(q, str)])
                    except Exception as exc:
                        logger.warning("[DEBUG] ai_expand_fallback_failed: %s", str(exc)[:120])
                q2 = list(dict.fromkeys(q2))[:10]
            except Exception as exc:
                logger.warning("[DEBUG] phase_query_builder_fallback_failed: %s", str(exc)[:120])
                q2 = []
            meta["queries_used"] = list(dict.fromkeys(meta["queries_used"] + q2))[:20]
            logger.info("[DEBUG] queries_generated_expanded=%s %s", len(q2), q2)
            try:
                raw2 = _phase_b_fetch(q2, country) if q2 else []
            except Exception as exc:
                logger.warning("[DEBUG] phase_fetch_fallback_failed: %s", str(exc)[:120])
                raw2 = []
            meta["raw_results_count"] += len(raw2)
            logger.info("[DEBUG] raw_results_count_expanded=%s", len(raw2))
            try:
                extracted2 = _phase_c_extract(raw2)
                deduped2 = _phase_d_normalize_dedup(extracted2)
                valid2, discarded2 = _phase_e_validate(deduped2, query, country)
            except Exception as exc:
                logger.warning("[DEBUG] fallback_extract_validate_failed: %s", str(exc)[:120])
                valid2, discarded2 = [], {"fallback_failed": len(raw2)}
            discarded = {k: discarded.get(k, 0) + discarded2.get(k, 0) for k in set(discarded) | set(discarded2)}
            valid = _phase_d_normalize_dedup(valid + valid2)

        try:
            enriched = _phase_f_enrich(valid, query, country, use_ai=use_ai)
        except Exception as exc:
            logger.warning("[DEBUG] phase_enrich_failed: %s", str(exc)[:120])
            enriched = valid
        final = [r for r in enriched if r.get("website") and r.get("source_url")]
        meta["valid_results_count"] = len(final)
        meta["discarded_results_count"] = int(sum(discarded.values()))
        logger.info("[DEBUG] valid_results_count=%s", len(final))
        logger.info("[DEBUG] scartati_count=%s reason=%s", sum(discarded.values()), discarded)
        out = final[:target], meta
        _SEARCH_CACHE[cache_key] = (time.time(), out)
        return out
    except Exception as exc:
        logger.exception("search_companies_real failed: %s", str(exc)[:220])
        return [], meta
