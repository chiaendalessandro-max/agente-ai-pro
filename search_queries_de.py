"""Deutsche Suchbegriffe (nur Daten)."""

from __future__ import annotations

LANG_CODE = "de"

QUERY_BANK: dict[str, list[str]] = {
    "keywords": [
        "geschäftsfliegerei",
        "luftcharter",
        "business jet",
        "executive flights",
        "allgemeine luftfahrt",
        "lufttaxi",
    ],
    "synonyms": [
        "privatjet anbieter",
        "charterflüge",
        "executive luftfahrt",
    ],
    "business_queries": [
        "luftfahrtunternehmen deutschland",
        "charter anbieter europa",
        "business aviation dienstleister",
    ],
    "premium_queries": [
        "premium privatjet betreiber",
        "executive charter anbieter deutschland",
        "high-end business aviation",
    ],
}
