"""English query bank for company search (data only)."""

from __future__ import annotations

LANG_CODE = "en"

QUERY_BANK: dict[str, list[str]] = {
    "keywords": [
        "private aviation",
        "air charter",
        "business jet",
        "executive flights",
        "general aviation",
        "corporate aviation",
    ],
    "synonyms": [
        "private jet operators",
        "on-demand charter",
        "executive air travel",
        "VIP charter flights",
    ],
    "business_queries": [
        "aviation companies Italy",
        "air charter operators Europe",
        "business jet services",
    ],
    "premium_queries": [
        "top executive jet operators",
        "premium air charter providers",
        "high-end business aviation companies",
    ],
}
