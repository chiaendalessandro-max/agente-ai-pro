"""Normalizzazione paese utente → ISO2, keyword ricerca, TLD attesi, regione DDGS."""
from __future__ import annotations

import re
from dataclasses import dataclass


@dataclass(frozen=True)
class CountryContext:
    iso2: str
    label: str
    names_en: tuple[str, ...]
    names_local: tuple[str, ...]
    tlds: tuple[str, ...]
    query_tokens: tuple[str, ...]
    ddgs_region: str


_PROFILES: dict[str, CountryContext] = {
    "IT": CountryContext(
        iso2="IT",
        label="Italy",
        names_en=("Italy", "Italian"),
        names_local=("Italia", "italiane", "italiani", "italiano"),
        tlds=(".it", ".eu"),
        query_tokens=("Italy", "Italia", "Italian companies", "aziende italiane", "sito ufficiale Italia"),
        ddgs_region="it-it",
    ),
    "DE": CountryContext(
        iso2="DE",
        label="Germany",
        names_en=("Germany", "German"),
        names_local=("Deutschland", "deutsche", "Unternehmen"),
        tlds=(".de", ".eu"),
        query_tokens=("Germany", "Deutschland", "German companies", "deutsche Unternehmen"),
        ddgs_region="de-de",
    ),
    "FR": CountryContext(
        iso2="FR",
        label="France",
        names_en=("France", "French"),
        names_local=("France", "entreprises françaises", "sociétés"),
        tlds=(".fr", ".eu"),
        query_tokens=("France", "French companies", "entreprises France"),
        ddgs_region="fr-fr",
    ),
    "ES": CountryContext(
        iso2="ES",
        label="Spain",
        names_en=("Spain", "Spanish"),
        names_local=("España", "empresas españolas"),
        tlds=(".es", ".eu"),
        query_tokens=("Spain", "España", "Spanish companies"),
        ddgs_region="es-es",
    ),
    "US": CountryContext(
        iso2="US",
        label="United States",
        names_en=("USA", "United States", "American"),
        names_local=("US companies",),
        tlds=(".com", ".us", ".io"),
        query_tokens=("USA", "United States", "American companies"),
        ddgs_region="us-en",
    ),
    "GB": CountryContext(
        iso2="GB",
        label="United Kingdom",
        names_en=("UK", "United Kingdom", "British"),
        names_local=("British companies", "England"),
        tlds=(".co.uk", ".uk", ".com"),
        query_tokens=("UK", "United Kingdom", "British companies"),
        ddgs_region="uk-en",
    ),
    "CH": CountryContext(
        iso2="CH",
        label="Switzerland",
        names_en=("Switzerland", "Swiss"),
        names_local=("Schweiz", "Suisse", "Svizzera"),
        tlds=(".ch", ".li", ".eu"),
        query_tokens=("Switzerland", "Swiss companies", "Schweiz Unternehmen"),
        ddgs_region="ch-de",
    ),
    "NL": CountryContext(
        iso2="NL",
        label="Netherlands",
        names_en=("Netherlands", "Dutch"),
        names_local=("Nederland", "Nederlandse bedrijven"),
        tlds=(".nl", ".eu"),
        query_tokens=("Netherlands", "Dutch companies", "Nederland"),
        ddgs_region="nl-nl",
    ),
}

_ALIAS_TO_ISO: dict[str, str] = {}
for iso, ctx in _PROFILES.items():
    for bucket in (ctx.names_en, ctx.names_local, (iso.lower(), ctx.label.lower())):
        for n in bucket:
            _ALIAS_TO_ISO[n.lower()] = iso
    _ALIAS_TO_ISO["italia"] = "IT"
    _ALIAS_TO_ISO["italy"] = "IT"
    _ALIAS_TO_ISO["italie"] = "IT"
    _ALIAS_TO_ISO["germany"] = "DE"
    _ALIAS_TO_ISO["deutschland"] = "DE"
    _ALIAS_TO_ISO["francia"] = "FR"
    _ALIAS_TO_ISO["spagna"] = "ES"
    _ALIAS_TO_ISO["uk"] = "GB"
    _ALIAS_TO_ISO["inghilterra"] = "GB"
    _ALIAS_TO_ISO["stati uniti"] = "US"
    _ALIAS_TO_ISO["usa"] = "US"


def resolve_country(user_input: str) -> CountryContext | None:
    raw = (user_input or "").strip()
    if not raw:
        return None
    if len(raw) == 2 and raw.isalpha():
        iso = raw.upper()
        if iso in _PROFILES:
            return _PROFILES[iso]
    key = re.sub(r"\s+", " ", raw.lower())
    if key in _ALIAS_TO_ISO:
        return _PROFILES[_ALIAS_TO_ISO[key]]
    for alias, iso in _ALIAS_TO_ISO.items():
        if alias in key or key in alias:
            return _PROFILES[iso]
    return None
