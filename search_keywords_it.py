"""Keyword e sinonimi per ricerca aziendale (italiano). Chiavi settore allineate agli altri file lingua."""

from __future__ import annotations

LANG = "it"

# Chiave = slug settore condiviso con search_keywords_en|fr|de|es
KEYWORDS: dict[str, dict[str, list[str]]] = {
    "aviazione": {
        "sector_terms": [
            "aviazione",
            "aviazione generale",
            "aviazione d'affari",
            "aerotaxi",
            "jet privato",
            "charter aereo",
        ],
        "synonyms": [
            "operatori aerei",
            "servizi charter",
            "voli executive",
            "business jet",
        ],
        "business_queries": [
            "aziende aviazione Italia",
            "operatori charter Italia",
            "servizi jet privato",
        ],
        "english_bridge": [
            "aviation",
            "air charter",
            "private jet",
            "business aviation",
        ],
    },
    "software": {
        "sector_terms": ["software", "saas", "applicazioni", "piattaforme digitali"],
        "synonyms": ["sviluppo software", "IT solutions", "cloud computing"],
        "business_queries": ["aziende software Italia", "fornitori SaaS"],
        "english_bridge": ["software company", "SaaS", "enterprise software"],
    },
    "logistica": {
        "sector_terms": ["logistica", "trasporti", "spedizioni", "supply chain"],
        "synonyms": ["corrieri", "magazzino", "fulfillment"],
        "business_queries": ["aziende logistica Italia", "operatori trasporto merci"],
        "english_bridge": ["logistics", "freight", "supply chain"],
    },
}
