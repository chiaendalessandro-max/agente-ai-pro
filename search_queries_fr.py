"""Banque de requêtes français (données uniquement)."""

from __future__ import annotations

LANG_CODE = "fr"

QUERY_BANK: dict[str, list[str]] = {
    "keywords": [
        "aviation d'affaires",
        "affrètement aérien",
        "jet privé",
        "vols exécutifs",
        "aviation générale",
        "taxi aérien",
    ],
    "synonyms": [
        "transport aérien charter",
        "opérateurs de jet privé",
        "vols corporate",
    ],
    "business_queries": [
        "entreprises aviation France",
        "opérateurs charter aérien",
        "prestataires jet affaires",
    ],
    "premium_queries": [
        "opérateurs jet executive France",
        "affrètement premium jet privé",
        "aviation corporative haut de gamme",
    ],
}
