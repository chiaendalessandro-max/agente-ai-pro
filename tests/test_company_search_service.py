"""Test orchestratore company search interno (nuovo result model, no Apollo)."""
from __future__ import annotations

import pytest

import app.services.company_search_service as svc
import company_search_real as csr

_MODEL_KEYS = {
    "company_name",
    "website",
    "country",
    "sector",
    "email",
    "phone",
    "revenue",
    "source_url",
    "confidence_score",
    "validation_status",
}


def _engine_rows() -> tuple[list[dict], dict]:
    return (
        [
            {
                "name": "Aero Uno",
                "website": "https://aerouno.it/",
                "source_url": "https://aerouno.it/",
                "country": "Italy",
                "sector": "aviazione",
                "contact_email": "info@aerouno.it",
                "contact_phone": "+39 06 1234567",
                "score": 78,
                "classification": "HIGH VALUE",
            },
            {
                "name": "Aero Due",
                "website": "https://aerodue.it/",
                "source_url": "https://aerodue.it/",
                "country": "Italy",
                "sector": "aviazione",
                "contact_email": "",
                "contact_phone": "",
                "score": 50,
                "classification": "MEDIUM",
            },
        ],
        {"queries_used": ["aviazione companies italy"], "raw_results_count": 8, "discarded_results_count": 6},
    )


@pytest.fixture(autouse=True)
def _patch_engine(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        csr,
        "search_companies_real_with_meta",
        lambda *a, **k: _engine_rows(),
    )


def test_normal_returns_new_result_model() -> None:
    out = svc.normal_search_service("aviazione", "Italia", "", 10, language="it")
    assert out["mode"] == "normal"
    assert out["count"] == 2
    row = out["results"][0]
    assert set(row.keys()) == _MODEL_KEYS
    assert row["revenue"] == "not found"
    assert row["validation_status"] == "verified"
    assert isinstance(row["confidence_score"], int)


def test_fast_service_caps_at_10_and_no_ai_mode() -> None:
    out = svc.fast_search_service("aviazione", "Italia", "", 10, language="it")
    assert out["mode"] == "fast"
    assert out["meta"]["depth"] == "fast"
    assert out["count"] <= 10


def test_deep_service_depth_meta_and_cap() -> None:
    out = svc.deep_search_service("aviazione", "Italia", "", 50, language="it")
    assert out["mode"] == "deep"
    assert out["meta"]["depth"] == "deep"
    assert out["count"] <= 50


def test_meta_contract_keys_present() -> None:
    out = svc.normal_search_service("aviazione", "Italia", "", 10)
    for key in ("queries_used", "raw_results_count", "valid_results_count", "discarded_results_count"):
        assert key in out["meta"]
    assert out["meta"]["engine"] == "internal"


def test_premium_prioritizes_contacts_and_caps_10() -> None:
    out = svc.premium_search_service("aviazione", "Italia", "", 10, language="it")
    assert out["mode"] == "premium"
    assert out["count"] <= 10
    assert out["results"][0]["company_name"] == "Aero Uno"
    assert out["results"][0]["validation_status"] == "verified"


def test_empty_engine_returns_controlled_message(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        csr,
        "search_companies_real_with_meta",
        lambda *a, **k: ([], {"queries_used": [], "raw_results_count": 0, "discarded_results_count": 0}),
    )
    out = svc.normal_search_service("xyznotexist", "Italia", "", 10)
    assert out["count"] == 0
    assert out["results"] == []
    assert out["message"] == "Nessuna azienda trovata con questi criteri"


def test_engine_exception_no_crash(monkeypatch: pytest.MonkeyPatch) -> None:
    def _boom(*_a, **_k):
        raise RuntimeError("network down")

    monkeypatch.setattr(csr, "search_companies_real_with_meta", _boom)
    out = svc.normal_search_service("aviazione", "Italia", "", 10)
    assert out["count"] == 0
    assert out["results"] == []
    assert out["message"] == "Nessuna azienda trovata con questi criteri"
