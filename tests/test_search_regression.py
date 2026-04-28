from __future__ import annotations

import pytest

try:
    from fastapi.testclient import TestClient

    from app.api.deps import apply_rate_limit, get_current_user
    from app.api.routes import leads as leads_routes
    from app.main import app
    from app.models.user import User

    _HAVE_APP = True
except Exception:
    _HAVE_APP = False
    TestClient = None  # type: ignore[assignment,misc]
    app = None  # type: ignore[assignment]

pytestmark = pytest.mark.skipif(not _HAVE_APP, reason="Stack applicativo non importabile")


def _override_user(plan: str):
    async def _user_override():
        return User(email=f"{plan}@test.local", password_hash="x", company_name="acme", plan=plan)

    return _user_override


async def _no_rate_limit():
    return None


def _clear_overrides() -> None:
    app.dependency_overrides.clear()


def _contract_ok(data: dict) -> None:
    assert "results" in data
    assert isinstance(data["results"], list)
    assert "message" in data
    assert isinstance(data["message"], str)
    assert "meta" in data
    assert isinstance(data["meta"], dict)
    for key in ("queries_used", "raw_results_count", "valid_results_count", "discarded_results_count"):
        assert key in data["meta"]


def test_normal_search_no_500(monkeypatch: pytest.MonkeyPatch) -> None:
    app.dependency_overrides[get_current_user] = _override_user("free")
    app.dependency_overrides[apply_rate_limit] = _no_rate_limit

    def _fake_normal(query: str, country: str, sector: str, limit: int) -> dict:
        assert query == "aviazione"
        assert country == "Italia"
        assert isinstance(sector, str)
        assert limit == 10
        return {
            "mode": "normal",
            "count": 1,
            "results": [{"company_name": "Aero Test", "score": "MEDIUM"}],
            "message": "",
            "meta": {
                "queries_used": ["aviazione companies italy"],
                "raw_results_count": 12,
                "valid_results_count": 1,
                "discarded_results_count": 11,
            },
        }

    monkeypatch.setattr(leads_routes, "normal_search_service", _fake_normal)
    with TestClient(app) as client:
        resp = client.post("/api/v1/company-search?mode=normal", json={"query": "aviazione", "country": "Italia", "limit": 10})
    _clear_overrides()

    assert resp.status_code == 200
    payload = resp.json()
    _contract_ok(payload)


def test_premium_free_returns_403_and_does_not_execute(monkeypatch: pytest.MonkeyPatch) -> None:
    app.dependency_overrides[get_current_user] = _override_user("free")
    app.dependency_overrides[apply_rate_limit] = _no_rate_limit
    called = {"premium": 0}

    def _fake_premium(*_args, **_kwargs):
        called["premium"] += 1
        return {"results": [], "message": "", "meta": {}}

    monkeypatch.setattr(leads_routes, "premium_search_service", _fake_premium)
    with TestClient(app) as client:
        resp = client.post("/api/v1/company-search?mode=premium", json={"query": "aviazione", "country": "Italia", "limit": 10})
    _clear_overrides()

    assert resp.status_code == 403
    assert called["premium"] == 0


def test_premium_user_no_500_and_empty_result_contract(monkeypatch: pytest.MonkeyPatch) -> None:
    app.dependency_overrides[get_current_user] = _override_user("premium")
    app.dependency_overrides[apply_rate_limit] = _no_rate_limit

    def _fake_premium(_query: str, _country: str, _sector: str, _limit: int) -> dict:
        return {
            "mode": "premium",
            "count": 0,
            "results": [],
            "message": "Nessuna azienda trovata con criteri attuali",
            "meta": {
                "queries_used": ["aviazione companies italy"],
                "raw_results_count": 0,
                "valid_results_count": 0,
                "discarded_results_count": 0,
            },
        }

    monkeypatch.setattr(leads_routes, "premium_search_service", _fake_premium)
    with TestClient(app) as client:
        resp = client.post("/api/v1/company-search?mode=premium", json={"query": "aviazione", "country": "Italia", "limit": 10})
    _clear_overrides()

    assert resp.status_code == 200
    payload = resp.json()
    _contract_ok(payload)
    assert payload["results"] == []
    assert payload["message"]


def test_normal_search_empty_list_no_crash(monkeypatch: pytest.MonkeyPatch) -> None:
    app.dependency_overrides[get_current_user] = _override_user("free")
    app.dependency_overrides[apply_rate_limit] = _no_rate_limit

    def _fake_normal(_query: str, _country: str, _sector: str, _limit: int) -> dict:
        return {
            "mode": "normal",
            "count": 0,
            "results": [],
            "message": "Nessuna azienda trovata con criteri attuali",
            "meta": {
                "queries_used": [],
                "raw_results_count": 0,
                "valid_results_count": 0,
                "discarded_results_count": 0,
            },
        }

    monkeypatch.setattr(leads_routes, "normal_search_service", _fake_normal)
    with TestClient(app) as client:
        resp = client.post("/api/v1/company-search?mode=normal", json={"query": "aviazione", "country": "Italia", "limit": 10})
    _clear_overrides()

    assert resp.status_code == 200
    payload = resp.json()
    _contract_ok(payload)
    assert payload["results"] == []
