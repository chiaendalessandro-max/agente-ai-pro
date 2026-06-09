from __future__ import annotations

import pytest

from search_country import normalize_country_for_apollo


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


def _apollo_ok_response():
    return [
        {
            "name": "Apollo Jet",
            "website_url": "https://apollo-jet.com",
            "phone": "",
            "id": "org-1",
        }
    ], {"raw_results_count": 1, "apollo_status": "ok"}


@pytest.fixture(autouse=True)
def _apollo_provider_default(monkeypatch: pytest.MonkeyPatch) -> None:
    import app.services.company_search_service as svc

    monkeypatch.setattr(svc.settings, "search_provider", "apollo", raising=False)


def test_apollo_not_configured_returns_controlled_error(monkeypatch: pytest.MonkeyPatch) -> None:
    import app.services.company_search_service as svc

    monkeypatch.setattr(svc.settings, "apollo_api_key", "", raising=False)
    out = svc.normal_search_service("aviazione", "Italia", "", 10)
    assert out["count"] == 0
    assert out["results"] == []
    assert out["message"] == "Apollo non configurato"


def test_internal_provider_uses_internal_when_no_apollo_key(monkeypatch: pytest.MonkeyPatch) -> None:
    import app.services.company_search_service as svc

    monkeypatch.setattr(svc.settings, "search_provider", "internal", raising=False)
    monkeypatch.setattr(svc.settings, "apollo_api_key", "", raising=False)
    monkeypatch.setattr(
        svc,
        "_internal_rows",
        lambda *a, **k: _internal_sample(),
    )
    out = svc.normal_search_service("aviazione", "Italia", "", 10)
    assert out["count"] >= 1
    assert out["results"][0].get("source") == "internal"


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
    monkeypatch.setattr(svc, "_internal_rows", _no_internal)

    out = svc.normal_search_service("aviazione", "Italia", "", 10)
    assert out["mode"] == "normal"
    assert out["count"] == 0
    assert out["results"] == []
    assert calls["internal"] == 0


def test_apollo_timeout_meta_without_crash(monkeypatch: pytest.MonkeyPatch) -> None:
    import app.services.company_search_service as svc

    class _TimeoutApollo:
        def __init__(self, *_args, **_kwargs):
            pass

        def search_organizations(self, *_args, **_kwargs):
            return [], {"apollo_status": "timeout", "raw_results_count": 0}

    monkeypatch.setattr(svc.settings, "apollo_api_key", "test-key", raising=False)
    monkeypatch.setattr(svc, "ApolloProvider", _TimeoutApollo)

    out = svc.normal_search_service("aviazione", "Italia", "", 10)
    assert out["count"] == 0
    assert out["results"] == []
    assert out["meta"]["apollo_status"] == "timeout"


def test_apollo_primary_single_call_with_source_apollo(monkeypatch: pytest.MonkeyPatch) -> None:
    import app.services.company_search_service as svc

    calls = {"search": 0}

    class _ApolloOk:
        def __init__(self, *_args, **_kwargs):
            pass

        def search_organizations(self, *_args, **_kwargs):
            calls["search"] += 1
            return _apollo_ok_response()

    monkeypatch.setattr(svc.settings, "apollo_api_key", "test-key", raising=False)
    monkeypatch.setattr(svc, "ApolloProvider", _ApolloOk)

    out = svc.normal_search_service("aviazione", "Italia", "", 10, language="it")
    assert calls["search"] == 1
    assert out["results"][0]["company_name"] == "Apollo Jet"
    assert out["results"][0]["source"] == "apollo"
    assert out["meta"]["search_provider"] == "apollo"


def test_country_normalized_before_apollo(monkeypatch: pytest.MonkeyPatch) -> None:
    import app.services.company_search_service as svc

    captured = {}

    class _ApolloOk:
        def __init__(self, *_args, **_kwargs):
            pass

        def search_organizations(self, query, country, sector, limit, **kwargs):
            captured["country"] = country
            return _apollo_ok_response()

    monkeypatch.setattr(svc.settings, "apollo_api_key", "test-key", raising=False)
    monkeypatch.setattr(svc, "ApolloProvider", _ApolloOk)

    svc.normal_search_service("aviazione", "Italia", "", 10)
    assert captured["country"] == "Italy"
    assert normalize_country_for_apollo("Germania") == "Germany"


def test_premium_filter_on_apollo_results(monkeypatch: pytest.MonkeyPatch) -> None:
    import app.services.company_search_service as svc

    class _ApolloOk:
        def __init__(self, *_args, **_kwargs):
            pass

        def search_organizations(self, *_args, **_kwargs):
            return _apollo_ok_response()

    monkeypatch.setattr(svc.settings, "apollo_api_key", "test-key", raising=False)
    monkeypatch.setattr(svc, "ApolloProvider", _ApolloOk)

    out = svc.premium_search_service("aviazione", "Italia", "", 10)
    assert out["mode"] == "premium"
    assert out["count"] == 1
    assert out["results"][0]["score"] in {"HIGH", "MEDIUM"}
    assert out["results"][0]["source"] == "apollo"
