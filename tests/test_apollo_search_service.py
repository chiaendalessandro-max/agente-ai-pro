from __future__ import annotations

import pytest


def _internal_sample() -> tuple[list[dict], dict]:
    return (
        [
            {
                "name": "Internal Air One",
                "website": "https://internal-air-one.it/",
                "source_url": "https://internal-air-one.it/",
                "country": "Italia",
                "score": 55,
                "classification": "MEDIUM",
                "contact_email": "",
                "contact_phone": "",
                "sector": "aviazione",
            }
        ],
        {
            "queries_used": ["aviazione companies italy"],
            "raw_results_count": 4,
            "valid_results_count": 1,
            "discarded_results_count": 3,
        },
    )


def test_apollo_absent_uses_internal_fallback(monkeypatch: pytest.MonkeyPatch) -> None:
    import app.services.company_search_service as svc

    monkeypatch.setattr(svc.settings, "apollo_api_key", "", raising=False)
    monkeypatch.setattr(svc, "search_companies_real_with_meta", lambda q, c, l: _internal_sample())

    out = svc.normal_search_service("aviazione", "Italia", 10)
    assert out["mode"] == "normal"
    assert out["count"] >= 1
    assert isinstance(out["results"], list)
    assert out["results"][0].get("source_url")


def test_apollo_error_uses_internal_fallback(monkeypatch: pytest.MonkeyPatch) -> None:
    import app.services.company_search_service as svc

    class _BrokenApollo:
        def __init__(self, *_args, **_kwargs):
            pass

        def search_organizations(self, *_args, **_kwargs):
            raise RuntimeError("apollo timeout")

    monkeypatch.setattr(svc.settings, "apollo_api_key", "test-key", raising=False)
    monkeypatch.setattr(svc, "ApolloProvider", _BrokenApollo)
    monkeypatch.setattr(svc, "search_companies_real_with_meta", lambda q, c, l: _internal_sample())

    out = svc.normal_search_service("aviazione", "Italia", 10)
    assert out["mode"] == "normal"
    assert out["count"] >= 1
    assert out["results"][0]["company_name"] == "Internal Air One"


def test_apollo_primary_then_internal_completion(monkeypatch: pytest.MonkeyPatch) -> None:
    import app.services.company_search_service as svc

    class _ApolloOk:
        def __init__(self, *_args, **_kwargs):
            pass

        def search_organizations(self, *_args, **_kwargs):
            return [
                {
                    "name": "Apollo Jet",
                    "website": "https://apollo-jet.com",
                    "source_url": "https://apollo-jet.com",
                    "country": "Italia",
                    "score": 70,
                    "classification": "HIGH VALUE",
                    "contact_email": "",
                    "contact_phone": "",
                    "sector": "aviazione",
                }
            ], {"raw_results_count": 1}

    monkeypatch.setattr(svc.settings, "apollo_api_key", "test-key", raising=False)
    monkeypatch.setattr(svc, "ApolloProvider", _ApolloOk)
    monkeypatch.setattr(svc, "search_companies_real_with_meta", lambda q, c, l: _internal_sample())

    out = svc.normal_search_service("aviazione", "Italia", 10)
    names = {r["company_name"] for r in out["results"]}
    assert "Apollo Jet" in names
    assert "Internal Air One" in names


def test_premium_still_works_with_apollo_path(monkeypatch: pytest.MonkeyPatch) -> None:
    import app.services.company_search_service as svc

    class _ApolloOk:
        def __init__(self, *_args, **_kwargs):
            pass

        def search_organizations(self, *_args, **_kwargs):
            return [
                {
                    "name": "Apollo High",
                    "website": "https://apollo-high.com",
                    "source_url": "https://apollo-high.com",
                    "country": "Italia",
                    "score": 88,
                    "classification": "HIGH VALUE",
                    "contact_email": "sales@apollo-high.com",
                    "contact_phone": "",
                    "sector": "aviazione",
                }
            ], {"raw_results_count": 1}

    monkeypatch.setattr(svc.settings, "apollo_api_key", "test-key", raising=False)
    monkeypatch.setattr(svc, "ApolloProvider", _ApolloOk)
    monkeypatch.setattr(svc, "search_companies_real_with_meta", lambda q, c, l: ([], {"raw_results_count": 0}))

    out = svc.premium_search_service("aviazione", "Italia", 10)
    assert out["mode"] == "premium"
    assert out["count"] == 1
    assert out["results"][0]["score"] in {"HIGH", "MEDIUM"}
