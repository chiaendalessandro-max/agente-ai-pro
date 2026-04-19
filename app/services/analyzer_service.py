import logging
import re
from urllib.parse import urljoin, urlparse

from bs4 import BeautifulSoup

from app.services.data_quality import normalize_lead_dict, normalize_website_url
from app.services.http_client import get_with_retry

logger = logging.getLogger(__name__)


def _domain(url: str) -> str:
    return urlparse(url).netloc.lower().replace("www.", "")


def _extract_email(text: str) -> str:
    matches = re.findall(r"[A-Z0-9._%+\-]+@[A-Z0-9.\-]+\.[A-Z]{2,}", text, re.I)
    for email in matches:
        local = email.lower().split("@", 1)[0]
        if local in {"info", "sales", "contact", "office", "business", "marketing"}:
            return email.lower()
    return matches[0].lower() if matches else ""


def _extract_phone(text: str) -> str:
    matches = re.findall(r"(\+?\d[\d\s().-]{7,}\d)", text)
    return matches[0].strip() if matches else ""


def _sector(desc: str) -> str:
    low = desc.lower()
    if any(x in low for x in ("pharma", "biotech", "healthcare")):
        return "Pharma"
    if any(x in low for x in ("bank", "finance", "wealth", "investment")):
        return "Finance"
    if any(x in low for x in ("luxury", "premium", "exclusive")):
        return "Luxury"
    if any(x in low for x in ("saas", "software", "cloud", "ai")):
        return "Technology"
    if any(x in low for x in ("enterprise", "corporate", "b2b")):
        return "Corporate Services"
    if any(x in low for x in ("aviation", "aerospace", "aircraft", "aerospaziale", "aeronautic")):
        return "Aviation / Aerospace"
    return "General"


def _size(desc: str) -> str:
    low = desc.lower()
    if any(x in low for x in ("1000+", "multinational", "global offices")):
        return "Enterprise"
    if any(x in low for x in ("500+", "international team")):
        return "500+"
    if any(x in low for x in ("100+", "growing team")):
        return "100+"
    return "SMB"


def _intl_presence(text: str) -> int:
    low = text.lower()
    markers = ("global", "worldwide", "international", "emea", "apac", "americas", "offices")
    return sum(1 for m in markers if m in low)


def _infer_country_iso2(domain: str, text: str) -> str:
    d = (domain or "").lower()
    tld_iso = (
        (".it", "IT"),
        (".de", "DE"),
        (".at", "AT"),
        (".fr", "FR"),
        (".es", "ES"),
        (".nl", "NL"),
        (".ch", "CH"),
        (".be", "BE"),
        (".pl", "PL"),
        (".pt", "PT"),
        (".ie", "IE"),
        (".eu", "EU"),
        (".us", "US"),
    )
    for tld, iso in tld_iso:
        if d.endswith(tld):
            return iso
    if d.endswith(".co.uk") or d.endswith(".uk"):
        return "GB"
    low = (text or "").lower()[:12000]
    if any(x in low for x in ("italy", "italia", "italian", "partita iva", "p.iva", " milano ", " roma ", " torino ")):
        return "IT"
    if any(x in low for x in ("germany", "deutschland", " berlin ", " münchen ", " gmbh ")):
        return "DE"
    if any(x in low for x in ("france", " français", " s.a.s", " sarl", " paris ")):
        return "FR"
    if any(x in low for x in ("spain", "españa", " madrid ", " barcelona ")):
        return "ES"
    if any(x in low for x in ("netherlands", "nederland", " amsterdam ")):
        return "NL"
    if any(x in low for x in ("switzerland", "schweiz", "suisse", "svizzera")):
        return "CH"
    if any(x in low for x in ("united kingdom", " england ", " scotland ", " wales ")):
        return "GB"
    if any(x in low for x in ("united states", " usa ", " u.s.", " america ")):
        return "US"
    return "GLOBAL"


def _best_company_name(soup: BeautifulSoup, domain: str) -> str:
    og = soup.find("meta", attrs={"property": "og:site_name"})
    if og and og.get("content"):
        return str(og["content"]).strip()[:200]
    og_t = soup.find("meta", attrs={"property": "og:title"})
    if og_t and og_t.get("content"):
        return str(og_t["content"]).strip()[:200]
    if soup.title and soup.title.string:
        t = soup.title.get_text(" ", strip=True)
        return t.split("|")[0].split("–")[0].split("-")[0].strip()[:200]
    return domain.split(".")[0].replace("-", " ").title() if domain else "Unknown"


async def analyze_company(website: str, filter_country_iso2: str | None = None) -> dict:
    wu = normalize_website_url(website) or website
    html = await get_with_retry(wu)
    soup = BeautifulSoup(html, "html.parser")
    desc = ""
    meta = soup.find("meta", attrs={"name": "description"})
    if meta and meta.get("content"):
        desc = meta["content"].strip()
    if not desc:
        p = soup.find("p")
        desc = p.get_text(" ", strip=True)[:420] if p else ""

    text = soup.get_text(" ", strip=True)
    links = [urljoin(wu, a.get("href", "")) for a in soup.find_all("a")]
    contact_page = ""
    for link in links:
        if _domain(link) == _domain(wu) and any(x in link.lower() for x in ("contact", "contatti", "kontakt", "contacto")):
            contact_page = link
            break

    d = _domain(wu)
    blob = text + " " + desc
    inferred = _infer_country_iso2(d, blob)
    if filter_country_iso2 and inferred == "GLOBAL":
        hints = {
            "IT": ("italy", "italia", "italian", " milano ", " roma "),
            "DE": ("germany", "deutschland", " gmbh "),
            "FR": ("france", " français", " paris "),
            "ES": ("spain", "españa", " madrid "),
            "GB": ("united kingdom", " england ", " london "),
            "US": ("united states", " usa ", " america "),
            "NL": ("netherlands", "nederland", " amsterdam "),
            "CH": ("switzerland", "schweiz", "suisse"),
        }
        for hint in hints.get(filter_country_iso2, ()):
            if hint in blob.lower():
                inferred = filter_country_iso2
                break

    country = inferred
    name = _best_company_name(soup, d)

    raw = {
        "name": name,
        "domain": d,
        "website": wu,
        "country": country,
        "sector": _sector(desc),
        "size_estimate": _size(desc),
        "description": desc,
        "international_presence": _intl_presence(text),
        "value_signals": desc[:260],
        "contact_email": _extract_email(text),
        "contact_phone": _extract_phone(text),
        "contact_page": contact_page,
    }
    return normalize_lead_dict({**raw, "score": 0, "classification": "LOW"}, "")


async def safe_analyze_company(website: str, filter_country_iso2: str | None = None) -> dict | None:
    try:
        w = (website or "").strip()
        if not w or len(w) > 500:
            return None
        return await analyze_company(w, filter_country_iso2=filter_country_iso2)
    except Exception as exc:
        logger.warning("safe_analyze_company failed: %s | %s", (website or "")[:120], str(exc)[:220])
        return None
