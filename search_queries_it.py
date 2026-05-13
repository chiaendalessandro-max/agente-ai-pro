"""Query e keyword per ricerca aziendale in italiano (solo dati)."""

from __future__ import annotations

LANG_CODE = "it"

QUERY_BANK: dict[str, list[str]] = {
    "keywords": [
        "aviazione privata",
        "aerotaxi",
        "jet privati",
        "charter executive",
        "aviazione generale",
        "business aviation Italia",
    ],
    "synonyms": [
        "operatori aerei charter",
        "voli executive",
        "servizi jet privato",
        "noleggio jet",
    ],
    "business_queries": [
        "aziende aviazione Italia",
        "operatori charter Italia",
        "fornitori servizi aerei business",
    ],
    "premium_queries": [
        "operatori jet executive Italia",
        "charter business jet premium",
        "aviazione corporativa Italia",
    ],
}
