"""Branchen-Keywords und Business-Suchstrings (Deutsch). Schlüssel wie in anderen Locales."""

from __future__ import annotations

LANG = "de"

KEYWORDS: dict[str, dict[str, list[str]]] = {
    "aviazione": {
        "sector_terms": [
            "luftfahrt",
            "geschäftsfliegerei",
            "allgemeine luftfahrt",
            "privatjet",
            "lufttaxi",
            "charterflug",
        ],
        "synonyms": ["executive aviation", "charterdienste", "business jet"],
        "business_queries": [
            "luftfahrtunternehmen Deutschland",
            "charter anbieter",
            "privatjet dienstleister",
        ],
        "english_bridge": [
            "aviation",
            "private jet",
            "air charter",
            "business aviation",
        ],
    },
    "software": {
        "sector_terms": ["software", "saas", "unternehmenssoftware", "cloud"],
        "synonyms": ["anwendungsentwicklung", "IT dienstleistungen"],
        "business_queries": ["software unternehmen deutschland", "saas anbieter"],
        "english_bridge": ["software company", "SaaS", "enterprise software"],
    },
    "logistica": {
        "sector_terms": ["logistik", "fracht", "spedition", "supply chain"],
        "synonyms": ["kurier", "lager", "fulfillment"],
        "business_queries": ["logistik unternehmen deutschland", "frachtführer"],
        "english_bridge": ["logistics", "freight", "supply chain"],
    },
}
