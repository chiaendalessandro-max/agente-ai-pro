"""Mots-clés secteur et requêtes métier (français). Clés alignées sur les autres locales."""

from __future__ import annotations

LANG = "fr"

KEYWORDS: dict[str, dict[str, list[str]]] = {
    "aviazione": {
        "sector_terms": [
            "aviation",
            "aviation d'affaires",
            "aviation générale",
            "jet privé",
            "affrètement aérien",
        ],
        "synonyms": ["transport aérien charter", "vols exécutifs", "aérotaxi"],
        "business_queries": [
            "entreprises aviation France",
            "opérateurs jet privé",
            "services affrètement aérien",
        ],
        "english_bridge": [
            "aviation",
            "private jet",
            "air charter",
            "business aviation",
        ],
    },
    "software": {
        "sector_terms": ["logiciel", "saas", "éditeur logiciel", "cloud"],
        "synonyms": ["développement logiciel", "solutions IT"],
        "business_queries": ["entreprises logiciel France", "fournisseurs SaaS"],
        "english_bridge": ["software", "SaaS", "enterprise software"],
    },
    "logistica": {
        "sector_terms": ["logistique", "transport", "fret", "supply chain"],
        "synonyms": ["messagerie", "entrepôt", "fulfillment"],
        "business_queries": ["entreprises logistique France", "transporteurs"],
        "english_bridge": ["logistics", "freight", "supply chain"],
    },
}
