"""Normalizzazione nomi paese per Apollo (inglese)."""

from __future__ import annotations

_COUNTRY_TO_APOLLO: dict[str, str] = {
    "italia": "Italy",
    "italy": "Italy",
    "germania": "Germany",
    "germany": "Germany",
    "deutschland": "Germany",
    "francia": "France",
    "france": "France",
    "spagna": "Spain",
    "spain": "Spain",
    "espana": "Spain",
    "españa": "Spain",
    "regno unito": "United Kingdom",
    "united kingdom": "United Kingdom",
    "uk": "United Kingdom",
    "great britain": "United Kingdom",
    "stati uniti": "United States",
    "usa": "United States",
    "us": "United States",
    "united states": "United States",
    "united states of america": "United States",
}


def normalize_country_for_apollo(country: str) -> str:
    raw = (country or "").strip()
    if not raw:
        return ""
    key = raw.lower()
    return _COUNTRY_TO_APOLLO.get(key, raw)
