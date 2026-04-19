"""Confidence 0–1: coerenza paese, completezza dati, affidabilità fonte."""
from __future__ import annotations

import re

from app.services.country_context import CountryContext


def _domain_has_tld(domain: str, tlds: tuple[str, ...]) -> bool:
    d = (domain or "").lower()
    for t in tlds:
        suf = t if str(t).startswith(".") else f".{t}"
        if d.endswith(suf):
            return True
    return False


def _text_country_signals(text: str, ctx: CountryContext) -> float:
    low = (text or "").lower()
    score = 0.0
    for w in ctx.names_en + ctx.names_local:
        if len(w) > 2 and w.lower() in low:
            score += 0.11
    if ctx.iso2 == "IT" and any(
        x in low
        for x in (
            " milano",
            " roma",
            " torino",
            " bologna",
            " firenze",
            " napoli",
            " italia",
            "p.iva",
            "partita iva",
            " sede legale",
        )
    ):
        score += 0.22
    if ctx.iso2 == "DE" and any(x in low for x in (" deutschland", " berlin", " münchen", " gmbh")):
        score += 0.22
    if ctx.iso2 == "FR" and any(x in low for x in (" paris", " lyon", " s.a.s", " sarl")):
        score += 0.18
    return min(0.48, score)


def compute_lead_confidence(
    lead: dict,
    *,
    country_ctx: CountryContext | None,
    discovery_source: str,
) -> float:
    domain = (lead.get("domain") or "").lower()
    desc = (lead.get("description") or "") + " " + (lead.get("value_signals") or "")
    country_field = (lead.get("country") or "").upper()
    name = (lead.get("name") or "").strip()

    completeness = 0.0
    if len(name) > 3 and not re.match(r"^[a-z0-9\-]+$", name, re.I):
        completeness += 0.14
    elif len(name) > 2:
        completeness += 0.07
    if len(desc.strip()) > 140:
        completeness += 0.24
    elif len(desc.strip()) > 60:
        completeness += 0.16
    if lead.get("contact_email"):
        completeness += 0.14
    if lead.get("contact_phone"):
        completeness += 0.08
    if lead.get("contact_page"):
        completeness += 0.06

    source_trust = 0.42
    if discovery_source == "ddgs":
        source_trust = 0.58
    elif discovery_source == "expanded":
        source_trust = 0.48
    elif discovery_source == "brand_guess":
        source_trust = 0.22

    if country_ctx:
        cscore = 0.0
        if country_field == country_ctx.iso2:
            cscore += 0.52
        if _domain_has_tld(domain, country_ctx.tlds):
            cscore += 0.3
        cscore += _text_country_signals(desc, country_ctx)
        if country_field == "GLOBAL":
            cscore = max(0.0, cscore - 0.08)
        country_score = min(0.95, cscore)
    else:
        country_score = 0.42 if country_field != "GLOBAL" else 0.28

    raw = source_trust * 0.34 + completeness * 0.36 + country_score * 0.34
    return max(0.0, min(1.0, round(raw, 3)))
