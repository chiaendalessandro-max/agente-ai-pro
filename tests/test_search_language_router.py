"""Test router lingua (una query + keyword, niente auto-detect)."""

from __future__ import annotations

import search_language_router as router


def test_normalize_invalid_defaults_to_en() -> None:
    assert router.normalize_search_language("") == "en"
    assert router.normalize_search_language("xx") == "en"
    assert router.normalize_search_language("IT") == "it"


def test_build_search_params_italian() -> None:
    lang, org_q, kw = router.build_search_params("it", "aviazione privata", "Italia", "", mode="normal")
    assert lang == "it"
    assert org_q == "aviazione privata"
    assert kw in {"aviazione privata", "aerotaxi", "jet privati", "charter executive"}


def test_build_search_params_english() -> None:
    lang, org_q, kw = router.build_search_params("en", "private aviation", "UK", "", mode="normal")
    assert lang == "en"
    assert org_q == "private aviation"
    assert "aviation" in kw.lower() or "charter" in kw.lower()


def test_build_search_params_french() -> None:
    lang, _, kw = router.build_search_params("fr", "jet privé", "France", "", mode="normal")
    assert lang == "fr"
    assert kw


def test_build_search_params_german() -> None:
    lang, _, kw = router.build_search_params("de", "Luftcharter", "Deutschland", "", mode="normal")
    assert lang == "de"
    assert kw


def test_build_search_params_spanish() -> None:
    lang, _, kw = router.build_search_params("es", "aviación privada", "España", "", mode="normal")
    assert lang == "es"
    assert kw


def test_premium_uses_premium_keyword() -> None:
    _, _, kw = router.build_search_params("en", "aviation", "Italy", "", mode="premium")
    assert "premium" in kw.lower() or "executive" in kw.lower()
