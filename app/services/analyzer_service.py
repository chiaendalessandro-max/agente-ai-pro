import re
from urllib.parse import urljoin, urlparse

from bs4 import BeautifulSoup

from app.services.http_client import get_with_retry


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


async def analyze_company(website: str) -> dict:
    html = await get_with_retry(website)
    soup = BeautifulSoup(html, "html.parser")
    desc = ""
    meta = soup.find("meta", attrs={"name": "description"})
    if meta and meta.get("content"):
        desc = meta["content"].strip()
    if not desc:
        p = soup.find("p")
        desc = p.get_text(" ", strip=True)[:420] if p else ""

    text = soup.get_text(" ", strip=True)
    links = [urljoin(website, a.get("href", "")) for a in soup.find_all("a")]
    contact_page = ""
    for link in links:
        if _domain(link) == _domain(website) and any(x in link.lower() for x in ("contact", "contatti")):
            contact_page = link
            break

    country = "GLOBAL"
    d = _domain(website)
    if d.endswith(".it"):
        country = "IT"
    elif d.endswith(".de"):
        country = "DE"
    elif d.endswith(".fr"):
        country = "FR"
    elif d.endswith(".es"):
        country = "ES"

    return {
        "name": d.split(".")[0].replace("-", " ").title(),
        "domain": d,
        "website": website,
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
