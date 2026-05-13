"""Sector keywords and business phrases (English). Sector keys match other locale files."""

from __future__ import annotations

LANG = "en"

KEYWORDS: dict[str, dict[str, list[str]]] = {
    "aviazione": {
        "sector_terms": [
            "aviation",
            "general aviation",
            "business aviation",
            "air charter",
            "private jet",
            "aerotaxi",
        ],
        "synonyms": ["executive aviation", "charter flights", "corporate jets"],
        "business_queries": [
            "aviation companies Italy",
            "private jet operators Italy",
            "air charter services",
        ],
        "english_bridge": [],
    },
    "software": {
        "sector_terms": ["software", "SaaS", "enterprise software", "cloud"],
        "synonyms": ["application development", "IT services", "digital platforms"],
        "business_queries": ["software companies Italy", "SaaS providers"],
        "english_bridge": [],
    },
    "logistica": {
        "sector_terms": ["logistics", "freight", "shipping", "supply chain"],
        "synonyms": ["courier", "warehousing", "fulfillment"],
        "business_queries": ["logistics companies Italy", "freight operators"],
        "english_bridge": [],
    },
}
