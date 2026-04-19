"""Normalizzazione e deduplicazione dati lead/azienda (production)."""
from __future__ import annotations

import re
from urllib.parse import urlparse, urlunparse

_BLOCKED_SUBSTR = (
    "google.",
    "bing.",
    "yahoo.",
    "wikipedia.",
    "reddit.",
    "medium.com",
    "crunchbase.",
    "zoominfo.",
    "linkedin.",
    "facebook.",
    "instagram.",
    "twitter.",
    "x.com",
    "youtube.",
    "tiktok.",
)


def normalize_domain(url_or_domain: str) -> str:
    s = (url_or_domain or "").strip().lower()
    if not s:
        return ""
    if "://" in s:
        s = urlparse(s).netloc or ""
    s = s.replace("www.", "").split("/")[0].strip()
    return s


def normalize_website_url(url: str) -> str:
    u = (url or "").strip()
    if not u:
        return ""
    if not u.startswith(("http://", "https://")):
        u = "https://" + u
    parsed = urlparse(u)
    if not parsed.netloc:
        return ""
    scheme = "https" if parsed.scheme in ("http", "https") else "https"
    netloc = parsed.netloc.lower().replace("www.", "")
    path = parsed.path or ""
    if path == "":
        path = "/"
    return urlunparse((scheme, netloc, path, "", "", ""))


def is_blocked_or_junk_domain(domain: str) -> bool:
    d = normalize_domain(domain)
    if not d or "." not in d:
        return True
    for sub in _BLOCKED_SUBSTR:
        if sub in d:
            return True
    return False


def sanitize_text(text: str | None, max_len: int) -> str:
    if not text:
        return ""
    t = re.sub(r"\s+", " ", str(text)).strip()
    return t[:max_len]


def empty_lead_record(website: str, source_query: str) -> dict:
    dom = normalize_domain(website)
    name = dom.split(".")[0].replace("-", " ").title() if dom else "Unknown"
    return {
        "name": name,
        "domain": dom,
        "website": normalize_website_url(website) or website,
        "country": "GLOBAL",
        "sector": "General",
        "size_estimate": "SMB",
        "description": "",
        "international_presence": 0,
        "value_signals": "",
        "contact_email": "",
        "contact_phone": "",
        "contact_page": "",
        "score": 0,
        "classification": "LOW",
        "source_query": source_query,
        "_data_quality": "fallback_minimal",
    }


def normalize_lead_dict(raw: dict, source_query: str) -> dict:
    website = normalize_website_url(raw.get("website") or "")
    domain = normalize_domain(raw.get("domain") or website)
    if not website and domain:
        website = f"https://{domain}/"
    name = sanitize_text(raw.get("name"), 200) or (domain.split(".")[0].replace("-", " ").title() if domain else "Unknown")
    return {
        "name": name,
        "domain": domain,
        "website": website,
        "country": sanitize_text(raw.get("country"), 40) or "GLOBAL",
        "sector": sanitize_text(raw.get("sector"), 80) or "General",
        "size_estimate": sanitize_text(raw.get("size_estimate"), 40) or "SMB",
        "description": sanitize_text(raw.get("description"), 2000),
        "international_presence": max(0, min(20, int(raw.get("international_presence") or 0))),
        "value_signals": sanitize_text(raw.get("value_signals"), 500),
        "contact_email": sanitize_text(raw.get("contact_email"), 120).lower(),
        "contact_phone": sanitize_text(raw.get("contact_phone"), 40),
        "contact_page": sanitize_text(raw.get("contact_page"), 500),
        "score": max(0, min(100, int(raw.get("score") or 0))),
        "classification": (
            raw.get("classification")
            if raw.get("classification") in ("HIGH VALUE", "MEDIUM", "LOW")
            else "LOW"
        ),
        "source_query": sanitize_text(source_query, 300),
    }


def dedupe_leads_by_domain(leads: list[dict]) -> list[dict]:
    seen: set[str] = set()
    out: list[dict] = []
    for item in leads:
        d = normalize_domain(item.get("domain") or item.get("website") or "")
        if not d or d in seen:
            continue
        seen.add(d)
        out.append(item)
    return out
