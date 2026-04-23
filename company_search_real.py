import logging
import re
import time
from urllib.parse import quote_plus, urljoin, urlparse

import requests
from bs4 import BeautifulSoup

from ai_company_helper import ai_enrich_company, ai_expand_search_queries, ai_validate_company, is_ollama_available

logger = logging.getLogger(__name__)

COUNTRY_CONFIG = {
    "italia": {"lang": "it", "tld": ".it", "kompass": "IT", "local_keywords": ["azienda", "societa", "srl", "spa", "impresa"]},
    "italy": {"lang": "it", "tld": ".it", "kompass": "IT", "local_keywords": ["azienda", "societa", "srl", "spa", "impresa"]},
    "france": {"lang": "fr", "tld": ".fr", "kompass": "FR", "local_keywords": ["entreprise", "societe", "sarl", "sas"]},
    "germany": {"lang": "de", "tld": ".de", "kompass": "DE", "local_keywords": ["gmbh", "ag", "unternehmen", "firma"]},
    "spain": {"lang": "es", "tld": ".es", "kompass": "ES", "local_keywords": ["empresa", "sl", "sa", "sociedad"]},
    "uk": {"lang": "en", "tld": ".co.uk", "kompass": "GB", "local_keywords": ["ltd", "limited", "plc", "llp"]},
    "usa": {"lang": "en", "tld": ".com", "kompass": "US", "local_keywords": ["inc", "llc", "corp", "corporation"]},
}

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Accept-Language": "it-IT,it;q=0.9,en-US;q=0.8,en;q=0.7",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Referer": "https://www.google.com/",
}

BLACKLIST_DOMAINS = [
    "google.",
    "bing.",
    "yahoo.",
    "wikipedia.",
    "youtube.",
    "facebook.",
    "twitter.",
    "instagram.",
    "reddit.",
    "amazon.",
    "linkedin.com/in/",
    "tiktok.",
    "pinterest.",
    "tripadvisor.",
]


def build_queries(sector: str, country: str) -> list:
    country_lower = country.lower().strip()
    cfg = COUNTRY_CONFIG.get(country_lower, {"lang": "en", "tld": ".com", "local_keywords": []})
    queries = []

    queries.append(f"{sector} companies {country}")
    queries.append(f"top {sector} companies in {country} official website")
    queries.append(f"list of {sector} businesses {country}")
    queries.append(f"best {sector} firms {country} 2024")
    queries.append(f"{sector} industry leaders {country}")

    if cfg["lang"] == "it":
        queries.append(f"aziende {sector} Italia elenco")
        queries.append(f"migliori aziende {sector} italiane sito ufficiale")
        queries.append(f"imprese {sector} Italia lista completa")
        queries.append(f"societa {sector} italiane 2024")
        queries.append(f"{sector} aziende srl spa Italia")
    elif cfg["lang"] == "fr":
        queries.append(f"entreprises {sector} France liste")
        queries.append(f"meilleures societes {sector} France")
    elif cfg["lang"] == "de":
        queries.append(f"Unternehmen {sector} Deutschland Liste")
        queries.append(f"{sector} Firmen Deutschland GmbH AG")
    elif cfg["lang"] == "es":
        queries.append(f"empresas {sector} Espana lista")
        queries.append(f"mejores empresas {sector} Espana")

    queries.append(f"{sector} companies site:kompass.com {country}")
    queries.append(f"{sector} {country} site:europages.com")
    queries.append(f"{sector} aziende site:paginegialle.it" if cfg["lang"] == "it" else f"{sector} companies directory {country}")
    queries.append(f"site:linkedin.com/company {sector} {country}")

    logger.info("[QUERY] Costruite %s query per settore='%s' paese='%s'", len(queries), sector, country)
    return queries


def scrape_bing(query: str, num: int = 20) -> list:
    results = []
    url = f"https://www.bing.com/search?q={quote_plus(query)}&count={num}&setlang=en"
    try:
        resp = requests.get(url, headers=HEADERS, timeout=12)
        resp.raise_for_status()
        soup = BeautifulSoup(resp.text, "lxml")
        for item in soup.select("li.b_algo"):
            title_el = item.select_one("h2 a")
            desc_el = item.select_one("p, .b_caption p")
            if not title_el:
                continue
            results.append(
                {
                    "name": title_el.get_text(strip=True),
                    "url": title_el.get("href", ""),
                    "description": desc_el.get_text(strip=True) if desc_el else "",
                    "source": "bing",
                }
            )
        logger.info("[BING] '%s' -> %s risultati grezzi", query, len(results))
    except Exception as e:
        logger.error("[BING] Errore per query '%s': %s", query, e)
    return results


def scrape_duckduckgo(query: str, num: int = 20) -> list:
    results = []
    _ = num
    url = f"https://html.duckduckgo.com/html/?q={quote_plus(query)}"
    try:
        resp = requests.get(url, headers=HEADERS, timeout=12)
        resp.raise_for_status()
        soup = BeautifulSoup(resp.text, "lxml")
        for item in soup.select(".result__body"):
            title_el = item.select_one(".result__a")
            url_el = item.select_one(".result__url")
            desc_el = item.select_one(".result__snippet")
            if not title_el:
                continue
            raw_url = url_el.get_text(strip=True) if url_el else ""
            full_url = ("https://" + raw_url) if raw_url and not raw_url.startswith("http") else raw_url
            results.append(
                {
                    "name": title_el.get_text(strip=True),
                    "url": full_url or title_el.get("href", ""),
                    "description": desc_el.get_text(strip=True) if desc_el else "",
                    "source": "duckduckgo",
                }
            )
        logger.info("[DDG] '%s' -> %s risultati grezzi", query, len(results))
    except Exception as e:
        logger.error("[DDG] Errore per query '%s': %s", query, e)
    return results


def scrape_kompass(sector: str, country_code: str) -> list:
    results = []
    url = f"https://it.kompass.com/search/?text={quote_plus(sector)}&country[]={country_code}"
    try:
        resp = requests.get(url, headers=HEADERS, timeout=15)
        soup = BeautifulSoup(resp.text, "lxml")
        for card in soup.select(".companyTitle a, .company-name a, h3.title a"):
            name = card.get_text(strip=True)
            href = card.get("href", "")
            if name and len(name) > 2:
                full_url = urljoin("https://it.kompass.com", href)
                results.append(
                    {
                        "name": name,
                        "url": full_url,
                        "description": "Trovata su Kompass - directory B2B",
                        "source": "kompass",
                    }
                )
        logger.info("[KOMPASS] settore='%s' paese='%s' -> %s risultati", sector, country_code, len(results))
    except Exception as e:
        logger.error("[KOMPASS] Errore: %s", e)
    return results


def scrape_europages(sector: str, country: str) -> list:
    results = []
    url = f"https://www.europages.it/aziende/{quote_plus(country)}/{quote_plus(sector)}.html"
    try:
        resp = requests.get(url, headers=HEADERS, timeout=15)
        soup = BeautifulSoup(resp.text, "lxml")
        for card in soup.select(".company-name, .ep-company-name, h2.title"):
            name = card.get_text(strip=True)
            if name and len(name) > 2:
                results.append(
                    {
                        "name": name,
                        "url": url,
                        "description": "Trovata su Europages - directory europea",
                        "source": "europages",
                    }
                )
        logger.info("[EUROPAGES] settore='%s' paese='%s' -> %s risultati", sector, country, len(results))
    except Exception as e:
        logger.error("[EUROPAGES] Errore: %s", e)
    return results


def extract_company_info(raw: dict, sector: str, country: str) -> dict:
    name = raw.get("name", "").strip()
    url = raw.get("url", "").strip()
    desc = raw.get("description", "").strip()
    name = re.sub(r"https?://\S+", "", name)
    name = re.sub(r"\s*[-|–]\s*(Bing|Google|Yahoo|DuckDuckGo|Wikipedia).*", "", name, flags=re.IGNORECASE)
    name = re.sub(r"\s{2,}", " ", name).strip()
    parsed = urlparse(url)
    domain = parsed.netloc.lower().replace("www.", "") if parsed.netloc else ""
    return {
        "name": name,
        "domain": domain,
        "website": url,
        "country": country,
        "sector": sector,
        "description": desc[:250],
        "source": raw.get("source", "web"),
        "contacts": {},
        "contact_email": "",
        "contact_phone": "",
        "contact_page": "",
        "size_estimate": "SMB",
        "international_presence": 0,
        "value_signals": desc[:180],
        "score": 0,
        "classification": "LOW",
    }


def is_valid_company(company: dict, sector: str, country: str) -> bool:
    name = company.get("name", "").lower().strip()
    url = company.get("website", "").lower().strip()
    if any(b in url for b in BLACKLIST_DOMAINS):
        return False
    if len(name) < 3:
        return False
    generic_terms = [sector.lower(), country.lower(), "global", "general", "international", "worldwide", "group"]
    if name in generic_terms:
        return False
    if not url.startswith("http"):
        return False
    return True


def deduplicate(companies: list) -> list:
    seen_urls = set()
    seen_names = set()
    unique = []
    for c in companies:
        url_key = re.sub(r"https?://(www\.)?", "", c.get("website", "")).rstrip("/").lower()
        name_key = re.sub(r"[\s\-_]+", "", c.get("name", "")).lower()[:25]
        if url_key and url_key in seen_urls:
            continue
        if name_key and name_key in seen_names:
            continue
        if url_key:
            seen_urls.add(url_key)
        if name_key:
            seen_names.add(name_key)
        unique.append(c)
    return unique


def search_companies_real(sector: str, country: str, num_results: int = 10) -> list:
    logger.info("========================================")
    logger.info("[RICERCA AVVIATA] settore='%s' paese='%s' target=%s", sector, country, num_results)
    logger.info("========================================")
    USE_AI = is_ollama_available()
    logger.info("[AI] Modalita AI: %s", "ATTIVA" if USE_AI else "DISATTIVA (solo scraping)")

    all_raw = []
    country_lower = country.lower().strip()
    cfg = COUNTRY_CONFIG.get(country_lower, {"kompass": "IT"})

    logger.info("[FASE 1] Scraping directory B2B: Kompass + Europages")
    kompass_results = scrape_kompass(sector, cfg["kompass"])
    europages_results = scrape_europages(sector, country)
    all_raw.extend(kompass_results)
    all_raw.extend(europages_results)
    logger.info("[FASE 1] Totale da directory: %s risultati", len(all_raw))

    logger.info("[FASE 2] Scraping motori di ricerca con query multiple")
    queries = build_queries(sector, country)
    if USE_AI:
        ai_queries = ai_expand_search_queries(sector, country)
        queries = queries + ai_queries
        logger.info("[AI] Query totali con AI: %s", len(queries))
    else:
        logger.warning("[AI] Ollama non disponibile, uso solo scraping")

    for i, query in enumerate(queries):
        if len(all_raw) >= num_results * 4:
            logger.info("[FASE 2] Raccolti abbastanza risultati grezzi (%s), stop alla query %s", len(all_raw), i + 1)
            break
        if i % 2 == 0:
            results = scrape_bing(query, num=20)
        else:
            results = scrape_duckduckgo(query, num=20)
        all_raw.extend(results)
        time.sleep(1.5)

    logger.info("[FASE 2] Totale risultati grezzi raccolti: %s", len(all_raw))

    logger.info("[FASE 3] Pulizia e deduplicazione")
    companies = []
    for raw in all_raw:
        company = extract_company_info(raw, sector, country)
        if is_valid_company(company, sector, country):
            if USE_AI:
                if not ai_validate_company(company["name"], company["website"], sector, country):
                    continue
            companies.append(company)

    companies = deduplicate(companies)
    logger.info("[FASE 3] Dopo filtro + dedup: %s aziende uniche", len(companies))

    if len(companies) < num_results:
        logger.warning("[FALLBACK] Trovate solo %s aziende, ne servono %s. Amplio la ricerca...", len(companies), num_results)
        fallback_queries = [
            f"{sector} {country} aziende lista completa 2024",
            f"directory aziende {sector} {country}",
            f"{sector} imprese {country} contatti sito web",
            f"chi sono le aziende {sector} in {country}",
            f"elenco {sector} societa {country} ufficiale",
        ]
        for fq in fallback_queries:
            if len(companies) >= num_results:
                break
            logger.info("[FALLBACK] Query aggiuntiva: '%s'", fq)
            extra = scrape_bing(fq, num=25)
            for raw in extra:
                company = extract_company_info(raw, sector, country)
                if is_valid_company(company, sector, country):
                    if USE_AI:
                        if not ai_validate_company(company["name"], company["website"], sector, country):
                            continue
                    companies.append(company)
            companies = deduplicate(companies)
            time.sleep(2.0)
        logger.info("[FALLBACK] Dopo fallback: %s aziende", len(companies))

    final = companies[:num_results]
    if USE_AI:
        for company in final:
            extra = ai_enrich_company(company["name"], company["description"], sector)
            company.update(extra)

    logger.info("========================================")
    logger.info("[RICERCA COMPLETATA] Restituite %s aziende reali", len(final))
    for i, c in enumerate(final):
        logger.info("  [%02d] %-40s | %s", i + 1, c["name"], c["website"])
    logger.info("========================================")
    return final
