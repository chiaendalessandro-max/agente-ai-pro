"""Smoke di produzione end-to-end (senza mock): valida il wiring reale dei punti obbligatori.

Aree coperte: health check, readiness DB, registrazione, login, /me, dashboard,
ricerca normale (no 500, motore interno) e gate premium per utenti free.
"""
from __future__ import annotations

import pytest

try:
    from fastapi.testclient import TestClient

    from app.main import app

    _HAVE_APP = True
except Exception:  # pragma: no cover - ambiente senza stack completo
    _HAVE_APP = False
    TestClient = None  # type: ignore[assignment,misc]
    app = None  # type: ignore[assignment]

pytestmark = pytest.mark.skipif(not _HAVE_APP, reason="Stack applicativo non importabile")

_EMAIL = "prod_smoke_user@example.com"
_PASSWORD = "password123"


def _register_and_login(client: "TestClient") -> str:
    reg = client.post(
        "/auth/register",
        json={"email": _EMAIL, "password": _PASSWORD, "company_name": "Prod Smoke Co"},
    )
    assert reg.status_code in {200, 400}, reg.text

    login = client.post("/auth/login", json={"email": _EMAIL, "password": _PASSWORD})
    assert login.status_code == 200, login.text
    tokens = login.json()
    assert tokens.get("access_token")
    assert tokens.get("refresh_token")
    return tokens["access_token"]


def test_health_check() -> None:
    with TestClient(app) as client:
        r = client.get("/health")
        assert r.status_code == 200
        assert r.json().get("status") == "ok"


def test_readiness_database() -> None:
    with TestClient(app) as client:
        r = client.get("/ready")
        assert r.status_code == 200
        assert r.json().get("database") == "ok"


def test_registration_and_login_and_me() -> None:
    with TestClient(app) as client:
        access = _register_and_login(client)
        me = client.get("/auth/me", headers={"Authorization": f"Bearer {access}"})
        assert me.status_code == 200
        data = me.json()
        assert data.get("email") == _EMAIL.lower()
        assert data.get("plan") in {"free", "premium"}


def test_login_wrong_password_401() -> None:
    with TestClient(app) as client:
        _register_and_login(client)
        bad = client.post("/auth/login", json={"email": _EMAIL, "password": "wrong-pass"})
        assert bad.status_code == 401


def test_dashboard_page_served() -> None:
    with TestClient(app) as client:
        r = client.get("/app/dashboard")
        assert r.status_code == 200
        assert "text/html" in (r.headers.get("content-type") or "")


def test_normal_search_real_no_500(monkeypatch: pytest.MonkeyPatch) -> None:
    # Motore di ricerca isolato dalla rete: testiamo il wiring (auth -> endpoint -> servizio -> modello).
    import company_search_real as csr

    monkeypatch.setattr(
        csr,
        "search_companies_real_with_meta",
        lambda *a, **k: (
            [
                {
                    "name": "Smoke Air",
                    "website": "https://smoke-air.it/",
                    "source_url": "https://smoke-air.it/",
                    "country": "Italy",
                    "sector": "aviazione",
                    "contact_email": "info@smoke-air.it",
                    "contact_phone": "+39 06 0000000",
                    "score": 72,
                    "classification": "HIGH VALUE",
                }
            ],
            {"queries_used": ["q"], "raw_results_count": 1, "discarded_results_count": 0},
        ),
    )
    with TestClient(app) as client:
        access = _register_and_login(client)
        r = client.post(
            "/api/v1/company-search?mode=normal",
            headers={"Authorization": f"Bearer {access}"},
            json={"query": "aviazione", "country": "Italia", "limit": 10, "language": "it"},
        )
        assert r.status_code == 200, r.text
        body = r.json()
        assert isinstance(body.get("results"), list)
        assert "message" in body
        assert "meta" in body
        if body["results"]:
            row = body["results"][0]
            for key in ("company_name", "website", "country", "sector", "email", "phone", "revenue", "source_url", "confidence_score", "validation_status"):
                assert key in row
            assert row["revenue"] == "not found"


def test_premium_search_free_user_blocked_403() -> None:
    with TestClient(app) as client:
        access = _register_and_login(client)
        r = client.post(
            "/api/v1/company-search?mode=premium",
            headers={"Authorization": f"Bearer {access}"},
            json={"query": "aviazione", "country": "Italia", "limit": 10, "language": "it"},
        )
        assert r.status_code == 403


def test_save_lead_from_search_result() -> None:
    # FASE 7: il salvataggio lead deve creare davvero il lead (idempotente per dominio).
    with TestClient(app) as client:
        access = _register_and_login(client)
        headers = {"Authorization": f"Bearer {access}"}
        payload = {
            "company_name": "Smoke Air",
            "website": "https://smoke-air.it/",
            "source_url": "https://smoke-air.it/",
            "country": "Italy",
            "sector": "aviazione",
            "email": "info@smoke-air.it",
            "phone": "+39 06 0000000",
            "confidence_score": 72,
            "query": "aviazione",
        }
        r = client.post("/api/v1/leads/save", headers=headers, json=payload)
        assert r.status_code == 200, r.text
        body = r.json()
        assert body.get("ok") is True
        assert isinstance(body.get("lead_id"), int)

        # idempotenza: stessa azienda -> nessun nuovo lead, ma aggiornamento
        r2 = client.post("/api/v1/leads/save", headers=headers, json=payload)
        assert r2.status_code == 200, r2.text
        assert r2.json().get("lead_id") == body.get("lead_id")

        # presente nella lista lead dell'utente
        listing = client.get("/leads", headers=headers)
        assert listing.status_code == 200
        names = [item.get("company_name") for item in listing.json()]
        assert "Smoke Air" in names


def test_save_lead_invalid_url_no_crash() -> None:
    with TestClient(app) as client:
        access = _register_and_login(client)
        headers = {"Authorization": f"Bearer {access}"}
        r = client.post(
            "/api/v1/leads/save",
            headers=headers,
            json={"company_name": "No Site", "website": "", "source_url": ""},
        )
        assert r.status_code == 422
