import logging
import re
import time
from urllib.parse import quote_plus, urljoin, urlparse

import requests
from bs4 import BeautifulSoup
from duckduckgo_search import DDGS
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

from ai_company_helper import ai_enrich_company, ai_expand_search_queries, ai_validate_company, is_ollama_available
from ai_data_analysis import analizza_risultati_ricerca, ensure_local_dependencies

logger = logging.getLogger(__name__)

COUNTRY_CONFIG = {
    "italia": {"lang": "it", "tld": ".it", "kompass": "IT", "region": "it-it"},
    "italy": {"lang": "it", "tld": ".it", "kompass": "IT", "region": "it-it"},
    "france": {"lang": "fr", "tld": ".fr", "kompass": "FR", "region": "fr-fr"},
    "germany": {"lang": "de", "tld": ".de", "kompass": "DE", "region": "de-de"},
    "spain": {"lang": "es", "tld": ".es", "kompass": "ES", "region": "es-es"},
    "uk": {"lang": "en", "tld": ".co.uk", "kompass": "GB", "region": "uk-en"},
    "usa": {"lang": "en", "tld": ".com", "kompass": "US", "region": "us-en"},
}

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/125.0 Safari/537.36",
    "Accept-Language": "it-IT,it;q=0.9,en-US;q=0.8,en;q=0.7",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
}

BLACKLIST_DOMAINS = (
    "google.", "bing.", "yahoo.", "wikipedia.", "youtube.", "facebook.", "twitter.", "instagram.", "reddit.",
    "amazon.", "linkedin.com/in/", "tiktok.", "pinterest.", "tripadvisor.", "webcache.googleusercontent",
    "ansa.it", "reuters.com", "forbes.com", "ilsole24ore.com", "wikipedia.org", "facebook.com", "instagram.com",
    "twitter.com", "x.com", "youtube.com", "bloomberg.com", "nytimes.com", "ft.com", "wsj.com", "duckduckgo.com",
)

_SESSION = requests.Session()
_SESSION.mount("http://", HTTPAdapter(max_retries=Retry(total=2, backoff_factor=0.4, status_forcelist=[429, 500, 502, 503, 504])))
_SESSION.mount("https://", HTTPAdapter(max_retries=Retry(total=2, backoff_factor=0.4, status_forcelist=[429, 500, 502, 503, 504])))


def _norm_domain(url: str) -> str:
    try:
        return urlparse(url).netloc.lower().replace("www.", "")
    except Exception:
        return ""


def _country_match(url: str, desc: str, country: str, tld: str) -> bool:
    u = (url or "").lower()
    d = (desc or "").lower()
    c = (country or "").lower()
    if tld and tld in u:
        return True
    tokens = [c, c.replace("italia", "italy"), "italia", "italy"]
    return any(t for t in tokens if t and (t in u or t in d))


def build_queries(sector: str, country: str, relaxed: bool = False) -> list[str]:
    country_lower = country.lower().strip()
    cfg = COUNTRY_CONFIG.get(country_lower, {"lang": "en"})
    base = (sector or "").strip()
    q = [
        f"{base} companies {country}",
        f"{base} firms {country}",
        f"{base} business directory {country}",
        f"{base} companies official website {country}",
        f"{base} suppliers {country}",
        f"air charter companies Europe {country}",
        f"luxury aviation firms {country}",
    ]
    if cfg["lang"] == "it":
        q += [
            f"aziende {base} Italia",
            f"elenco aziende {base} Italia",
            f"societa {base} italiane",
            f"{base} operatori Italia",
            f"directory aziende {base} Italia",
        ]
    if not relaxed:
        q += [
            f"{base} site:kompass.com {country}",
            f"{base} site:europages.com {country}",
            f"{base} site:paginegialle.it",
        ]
    else:
        q += [
            f"{base} companies europe",
            f"{base} corporate operators",
            f"{base} services companies",
        ]
    out = []
    seen = set()
    for item in q:
        key = re.sub(r"\s+", " ", item).strip().lower()
        if key and key not in seen:
            seen.add(key)
            out.append(re.sub(r"\s+", " ", item).strip())
    return out


def _request(url: str, timeout: int = 12) -> str:
    r = _SESSION.get(url, headers=HEADERS, timeout=timeout)
    r.raise_for_status()
    return r.text


def scrape_bing(query: str, num: int = 20) -> list[dict]:
    results = []
    try:
        html = _request(f"https://www.bing.com/search?q={quote_plus(query)}&count={num}&setlang=en")
        soup = BeautifulSoup(html, "lxml")
        for item in soup.select("li.b_algo"):
            a = item.select_one("h2 a")
            p = item.select_one("p, .b_caption p")
            if not a:
                continue
            results.append({"name": a.get_text(strip=True), "url": a.get("href", ""), "description": p.get_text(strip=True) if p else "", "source": "bing_html"})
    except Exception as e:
        logger.warning("[BING] %s | %s", query[:80], str(e)[:160])
    return results


def scrape_duckduckgo_html(query: str) -> list[dict]:
    out = []
    try:
        html = _request(f"https://html.duckduckgo.com/html/?q={quote_plus(query)}")
        soup = BeautifulSoup(html, "lxml")
        for item in soup.select(".result"):
            a = item.select_one(".result__a")
            snippet = item.select_one(".result__snippet")
            if not a:
                continue
            out.append({"name": a.get_text(strip=True), "url": a.get("href", ""), "description": snippet.get_text(strip=True) if snippet else "", "source": "ddg_html"})
    except Exception as e:
        logger.warning("[DDG_HTML] %s | %s", query[:80], str(e)[:160])
    return out


def scrape_ddgs_api(query: str, region: str) -> list[dict]:
    out = []
    for backend in ("lite", "html", "api"):
        try:
            with DDGS() as ddgs:
                rows = list(ddgs.text(query, max_results=30, backend=backend, region=region))
            for row in rows:
                out.append(
                    {
                        "name": (row.get("title") or "").strip(),
                        "url": row.get("href") or row.get("url") or "",
                        "description": (row.get("body") or "").strip(),
                        "source": f"ddgs_{backend}",
                    }
                )
            if rows:
                break
        except Exception:
            continue
    return out


def scrape_kompass(sector: str, country_code: str) -> list[dict]:
    out = []
    try:
        html = _request(f"https://it.kompass.com/search/?text={quote_plus(sector)}&country[]={country_code}", timeout=14)
        soup = BeautifulSoup(html, "lxml")
        for a in soup.select(".companyTitle a, .company-name a, h3.title a"):
            name = a.get_text(strip=True)
            href = a.get("href", "")
            if name and href:
                out.append({"name": name, "url": urljoin("https://it.kompass.com", href), "description": "Directory B2B", "source": "kompass"})
    except Exception as e:
        logger.warning("[KOMPASS] %s", str(e)[:150])
    return out


def scrape_europages(sector: str, country: str) -> list[dict]:
    out = []
    try:
        url = f"https://www.europages.it/aziende/{quote_plus(country)}/{quote_plus(sector)}.html"
        html = _request(url, timeout=14)
        soup = BeautifulSoup(html, "lxml")
        for card in soup.select(".company-name, .ep-company-name, h2.title"):
            name = card.get_text(strip=True)
            if name:
                out.append({"name": name, "url": url, "description": "Directory europea", "source": "europages"})
    except Exception as e:
        logger.warning("[EUROPAGES] %s", str(e)[:150])
    return out


def extract_company_info(raw: dict, sector: str, country: str) -> dict:
    name = re.sub(r"\s{2,}", " ", re.sub(r"https?://\S+", "", (raw.get("name") or "").strip())).strip()
    website = (raw.get("url") or "").strip()
    if website and not website.startswith("http"):
        website = f"https://{website.lstrip('/')}"
    desc = (raw.get("description") or "").strip()
    domain = _norm_domain(website)
    source_url = website
    if domain:
        website = f"https://{domain}/"
    if (len(name) > 65 or " - " in name or "|" in name or "..." in name or "…" in name) and domain:
        name = domain.split(".")[0].replace("-", " ").title()
    return {
        "name": name,
        "domain": domain,
        "website": website,
        "source_url": source_url,
        "country": country,
        "sector": sector,
        "description": desc[:320],
        "source": raw.get("source", "web"),
        "contact_email": "",
        "contact_phone": "",
        "contact_page": "",
        "size_estimate": "SMB",
        "international_presence": 0,
        "value_signals": desc[:180],
        "score": 0,
        "classification": "LOW",
    }


def _quality_score(company: dict, req_country: str, req_tld: str) -> float:
    score = 0.2
    name = (company.get("name") or "").lower()
    website = (company.get("website") or "").lower()
    desc = (company.get("description") or "").lower()
    if len(name) > 4:
        score += 0.18
    if website.startswith("http") and "." in _norm_domain(website):
        score += 0.2
    if desc:
        score += 0.17
    if _country_match(website, desc, req_country, req_tld):
        score += 0.22
    if any(k in desc for k in ("company", "azienda", "charter", "aviation", "services", "operator")):
        score += 0.12
    if any(g in name for g in ("global", "international", "directory", "search")):
        score -= 0.25
    return max(0.0, min(1.0, score))


def _sector_relevant(company: dict, sector: str) -> bool:
    text = f"{company.get('name','')} {company.get('description','')} {company.get('website','')}".lower()
    words = [w for w in re.findall(r"[a-zA-Z]{3,}", (sector or "").lower()) if w not in {"company", "companies", "firm", "firms"}]
    if any(w in text for w in words):
        return True
    if any(w in words for w in ("jet", "aviation", "charter", "air")):
        return any(k in text for k in ("jet", "aviation", "charter", "aircraft", "flight", "aero"))
    return len(words) == 0


def is_valid_company(company: dict, sector: str, country: str, tld: str) -> bool:
    name = (company.get("name") or "").strip().lower()
    url = (company.get("website") or "").strip().lower()
    source_url = (company.get("source_url") or "").strip().lower()
    if not name or len(name) < 3 or not url.startswith("http"):
        return False
    if not source_url.startswith("http"):
        return False
    if any(b in url for b in BLACKLIST_DOMAINS):
        return False
    if name in {sector.lower().strip(), country.lower().strip(), "global", "international", "directory"}:
        return False
    if any(k in name for k in ("acquisito", "oggi", "anni", "notizie", "news", "article", "report")):
        return False
    if len(name.split()) > 7:
        return False
    if len(_norm_domain(url)) < 4:
        return False
    if tld and not _country_match(url, company.get("description", ""), country, tld):
        return False
    return True


def _assign_classification(score: float) -> str:
    if score >= 0.72:
        return "HIGH VALUE"
    if score >= 0.48:
        return "MEDIUM"
    return "LOW"


def deduplicate(companies: list[dict]) -> list[dict]:
    seen_dom = set()
    seen_name = set()
    out = []
    for c in companies:
        dom = _norm_domain(c.get("website", ""))
        nkey = re.sub(r"[\W_]+", "", (c.get("name") or "").lower())[:30]
        if (dom and dom in seen_dom) or (nkey and nkey in seen_name):
            continue
        if dom:
            seen_dom.add(dom)
        if nkey:
            seen_name.add(nkey)
        out.append(c)
    return out


def _collect_from_queries(queries: list[str], region: str, target_raw: int, use_sleep: float) -> list[dict]:
    all_raw: list[dict] = []
    for i, query in enumerate(queries):
        if len(all_raw) >= target_raw:
            break
        all_raw.extend(scrape_ddgs_api(query, region))
        all_raw.extend(scrape_bing(query, num=15))
        all_raw.extend(scrape_duckduckgo_html(query))
        logger.info("[QUERY] '%s' -> raw=%s", query[:80], len(all_raw))
        time.sleep(use_sleep)
    return all_raw


def search_companies_real(sector: str, country: str, num_results: int = 10) -> list[dict]:
    num_results = max(1, min(50, int(num_results or 10)))
    logger.info("[RICERCA] avvio settore=%r paese=%r target=%s", sector, country, num_results)
    ensure_local_dependencies()
    use_ai = is_ollama_available()

    key = (country or "").strip().lower()
    cfg = COUNTRY_CONFIG.get(key, {"lang": "en", "tld": "", "kompass": "IT", "region": "wt-wt"})
    tld = cfg.get("tld", "")
    region = cfg.get("region", "wt-wt")

    all_raw = []
    all_raw.extend(scrape_kompass(sector, cfg.get("kompass", "IT")))
    all_raw.extend(scrape_europages(sector, country))

    base_queries = build_queries(sector, country, relaxed=False)
    if use_ai:
        base_queries.extend(ai_expand_search_queries(sector, country))
    raw_target = max(num_results * 9, 80)
    all_raw.extend(_collect_from_queries(base_queries, region, raw_target, 0.35))

    if len(all_raw) < raw_target:
        relaxed_queries = build_queries(sector, country, relaxed=True)
        if cfg.get("lang") != "en":
            relaxed_queries.extend([f"{sector} companies Europe", f"{sector} firms international", f"{sector} operators"])
        all_raw.extend(_collect_from_queries(relaxed_queries, "wt-wt", raw_target, 0.25))

    logger.info("[RICERCA] raw raccolti=%s", len(all_raw))
    clean = []
    for raw in all_raw:
        c = extract_company_info(raw, sector, country)
        if is_valid_company(c, sector, country, tld):
            c["quality_score"] = _quality_score(c, country, tld)
            if _sector_relevant(c, sector):
                clean.append(c)

    clean = deduplicate(clean)
    if use_ai and len(clean) >= num_results:
        validated = []
        for item in clean[: max(num_results * 3, 24)]:
            try:
                if ai_validate_company(item["name"], item["website"], sector, country):
                    validated.append(item)
            except Exception:
                validated.append(item)
        if len(validated) >= num_results:
            clean = validated + clean[len(validated):]

    clean.sort(key=lambda x: float(x.get("quality_score") or 0), reverse=True)
    for item in clean:
        qs = float(item.get("quality_score") or 0.0)
        item["score"] = max(1, min(100, int(round(qs * 100))))
        item["classification"] = _assign_classification(qs)
    final = clean[:num_results]

    if len(final) < num_results:
        backup = [c for c in deduplicate([extract_company_info(r, sector, country) for r in all_raw]) if c.get("website", "").startswith("http")]
        backup = sorted(backup, key=lambda x: _quality_score(x, country, tld), reverse=True)
        dom = {c.get("domain") for c in final}
        for b in backup:
            if b.get("domain") in dom:
                continue
            qs = _quality_score(b, country, tld)
            b["quality_score"] = qs
            b["score"] = max(1, min(100, int(round(qs * 100))))
            b["classification"] = _assign_classification(qs)
            final.append(b)
            dom.add(b.get("domain"))
            if len(final) >= num_results:
                break

    if final:
        try:
            final = analizza_risultati_ricerca(final, sector, country)
        except Exception as e:
            logger.warning("[ANALISI] fallback senza NLP: %s", str(e)[:180])
    else:
        logger.warning("[RICERCA] nessun dato reale verificabile, AI processing saltato")

    if use_ai and final:
        for company in final[: min(12, len(final))]:
            try:
                extra = ai_enrich_company(company.get("name", ""), company.get("description", ""), sector)
                if extra:
                    company.update(extra)
            except Exception:
                continue

    for i, c in enumerate(final[:num_results], start=1):
        logger.info("[RISULTATO %02d] %s | %s | q=%.2f", i, c.get("name"), c.get("website"), float(c.get("quality_score") or 0))
    return final[:num_results]
