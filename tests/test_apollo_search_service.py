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
    monkeypatch.setattr(
        svc,
        "search_companies_real_with_meta",
        lambda q, c, l, mode="normal", minimal_internal=False: _internal_sample(),
    )

    out = svc.normal_search_service("aviazione", "Italia", "", 10)
    assert out["mode"] == "normal"
    assert out["count"] >= 1
    assert isinstance(out["results"], list)
    assert out["results"][0].get("source_url")


def test_apollo_error_returns_empty_without_internal(monkeypatch: pytest.MonkeyPatch) -> None:
    import app.services.company_search_service as svc

    class _BrokenApollo:
        def __init__(self, *_args, **_kwargs):
            pass

        def search_organizations(self, *_args, **_kwargs):
            raise RuntimeError("apollo timeout")

    calls = {"internal": 0}

    def _no_internal(*a, **k):
        calls["internal"] += 1
        return _internal_sample()

    monkeypatch.setattr(svc.settings, "apollo_api_key", "test-key", raising=False)
    monkeypatch.setattr(svc, "ApolloProvider", _BrokenApollo)
    monkeypatch.setattr(svc, "search_companies_real_with_meta", _no_internal)

    out = svc.normal_search_service("aviazione", "Italia", "", 10)
    assert out["mode"] == "normal"
    assert out["count"] == 0
    assert out["results"] == []
    assert calls["internal"] == 0
    assert "disponibile" in (out.get("message") or "").lower()


def test_apollo_primary_does_not_merge_internal(monkeypatch: pytest.MonkeyPatch) -> None:
    import app.services.company_search_service as svc

    class _ApolloOk:
        def __init__(self, *_args, **_kwargs):
            pass

        def search_organizations(self, *_args, **_kwargs):
            return [
                {
                    "name": "Apollo Jet",
                    "website_url": "https://apollo-jet.com",
                    "phone": "",
                    "id": "org-1",
                }
            ], {"raw_results_count": 1, "apollo_status": "ok"}

    calls = {"internal": 0}

    def _track_internal(*a, **k):
        calls["internal"] += 1
        return _internal_sample()

    monkeypatch.setattr(svc.settings, "apollo_api_key", "test-key", raising=False)
    monkeypatch.setattr(svc, "ApolloProvider", _ApolloOk)
    monkeypatch.setattr(svc, "search_companies_real_with_meta", _track_internal)

    out = svc.normal_search_service("aviazione", "Italia", "", 10)
    names = {r["company_name"] for r in out["results"]}
    assert "Apollo Jet" in names
    assert "Internal Air One" not in names
    assert calls["internal"] == 0


def test_premium_still_works_with_apollo_path(monkeypatch: pytest.MonkeyPatch) -> None:
    import app.services.company_search_service as svc

    class _ApolloOk:
        def __init__(self, *_args, **_kwargs):
            pass

        def search_organizations(self, *_args, **_kwargs):
            return [
                {
                    "name": "Apollo High",
                    "website_url": "https://apollo-high.com",
                    "phone": "",
                    "linkedin_url": "https://linkedin.com/company/apollo-high",
                    "id": "org-2",
                }
            ], {"raw_results_count": 1, "apollo_status": "ok"}

    monkeypatch.setattr(svc.settings, "apollo_api_key", "test-key", raising=False)
    monkeypatch.setattr(svc, "ApolloProvider", _ApolloOk)
    monkeypatch.setattr(
        svc,
        "search_companies_real_with_meta",
        lambda q, c, l, mode="premium", minimal_internal=False: ([], {"raw_results_count": 0}),
    )

    out = svc.premium_search_service("aviazione", "Italia", "", 10)
    assert out["mode"] == "premium"
    assert out["count"] == 1
    assert out["results"][0]["score"] in {"HIGH", "MEDIUM"}
