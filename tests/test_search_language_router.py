"""Test router lingua (import singolo modulo, niente auto-detect)."""

from __future__ import annotations

import pytest

import search_language_router as router


def test_normalize_invalid_defaults_to_en() -> None:
    assert router.normalize_search_language("") == "en"
    assert router.normalize_search_language("xx") == "en"
    assert router.normalize_search_language("IT") == "it"


def test_build_queries_italian_only_from_it_file() -> None:
    code, qs = router.build_apollo_query_strings("it", "aviazione privata", "Italia", "", mode="normal")
    assert code == "it"
    assert qs[0] == "aviazione privata"
    flat = " | ".join(qs).lower()
    assert "aerotaxi" in flat or "jet privati" in flat


def test_build_queries_english_examples() -> None:
    code, qs = router.build_apollo_query_strings("en", "private aviation", "UK", "", mode="normal")
    assert code == "en"
    joined = " | ".join(qs).lower()
    assert "air charter" in joined or "business jet" in joined


def test_build_queries_french() -> None:
    code, qs = router.build_apollo_query_strings("fr", "jet privé", "France", "", mode="normal")
    assert code == "fr"
    assert any("affrètement" in q or "charter" in q.lower() for q in qs)


def test_build_queries_german() -> None:
    code, qs = router.build_apollo_query_strings("de", "Luftcharter", "Deutschland", "", mode="normal")
    assert code == "de"
    assert any("geschäftsfliegerei" in q.lower() or "charter" in q.lower() for q in qs)


def test_build_queries_spanish() -> None:
    code, qs = router.build_apollo_query_strings("es", "aviación privada", "España", "", mode="normal")
    assert code == "es"
    assert any("fletamento" in q.lower() or "charter" in q.lower() for q in qs)


def test_premium_includes_premium_queries() -> None:
    _, qs = router.build_apollo_query_strings("en", "aviation", "Italy", "", mode="premium")
    joined = " | ".join(qs).lower()
    assert "premium" in joined or "executive" in joined
