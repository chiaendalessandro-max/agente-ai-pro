"""Test motore multilingua query (senza chiamate Apollo)."""

from __future__ import annotations

import pytest

from search_query_multilang import build_apollo_query_variants, detect_query_language


def test_detect_italian_query() -> None:
    assert detect_query_language("ricerca aziende aviazione Italia per charter") == "it"


def test_detect_english_query() -> None:
    assert detect_query_language("private jet operators in Italy") == "en"


def test_variants_italian_includes_english_bridge() -> None:
    lang, qs = build_apollo_query_variants("aviazione italia", "Italia", "")
    assert lang == "it"
    flat = " | ".join(qs).lower()
    assert "private jet" in flat or "aviation" in flat


def test_variants_english_private_jet() -> None:
    lang, qs = build_apollo_query_variants("private jet italy", "Italy", "")
    assert lang == "en"
    assert any("private" in q.lower() for q in qs)


def test_variants_french_aviation() -> None:
    lang, qs = build_apollo_query_variants("aviation affaires France", "France", "")
    assert lang == "fr"
    joined = " ".join(qs).lower()
    assert "private jet" in joined or "aviation" in joined


def test_variants_german_luftfahrt() -> None:
    lang, qs = build_apollo_query_variants("Luftfahrt Unternehmen Deutschland", "Germany", "")
    assert lang == "de"
    joined = " ".join(qs).lower()
    assert "luftfahrt" in joined or "aviation" in joined


def test_variants_spanish_aviacion() -> None:
    lang, qs = build_apollo_query_variants("empresas aviación España", "Spain", "")
    assert lang == "es"
    joined = " ".join(qs).lower()
    assert "aviación" in joined or "aviation" in joined
