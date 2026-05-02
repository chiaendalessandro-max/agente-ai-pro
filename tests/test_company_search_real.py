from __future__ import annotations

import pytest

import company_search_real as csr


def test_phase_e_validate_italian_aviation_query_not_over_filtered() -> None:
    rows = [
        {
            "company_name": "Aero Partner Srl",
            "website": "https://aeropartner.it/",
            "source_url": "https://aeropartner.it/",
            "domain": "aeropartner.it",
            "snippet": "Servizi di aviazione generale e charter in Italia",
        }
    ]
    valid, discarded = csr._phase_e_validate(rows, query="aviazione", country="Italia")
    assert valid
    assert sum(discarded.values()) == 0


def test_phase_f_enrich_limits_contact_scans_and_ai_calls(monkeypatch: pytest.MonkeyPatch) -> None:
    calls = {"contacts": 0, "ai": 0}

    def _contacts(_website: str) -> tuple[str, str]:
        calls["contacts"] += 1
        return "", ""

    def _ai_enrich(*_args, **_kwargs):
        calls["ai"] += 1
        return {}

    monkeypatch.setattr(csr, "_contacts", _contacts)
    monkeypatch.setattr(csr, "ai_enrich_company", _ai_enrich)

    rows = [
        {
            "company_name": f"Company {i}",
            "website": f"https://company{i}.com/",
            "source_url": f"https://company{i}.com/",
            "domain": f"company{i}.com",
            "snippet": "operator corporate services",
        }
        for i in range(10)
    ]

    out = csr._phase_f_enrich(rows, query="private jet", country="Italia", use_ai=True)
    assert len(out) == 10
    assert calls["contacts"] == 6
    assert calls["ai"] == 3
