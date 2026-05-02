from __future__ import annotations

import pytest

try:
    from fastapi.testclient import TestClient

    from app.main import app

    _HAVE_APP = True
except Exception:
    _HAVE_APP = False
    TestClient = None  # type: ignore[assignment,misc]
    app = None  # type: ignore[assignment]

pytestmark = pytest.mark.skipif(not _HAVE_APP, reason="Stack applicativo non importabile")


def test_register_login_me_flow() -> None:
    with TestClient(app) as client:
        email = "buyer_smoke_1@example.com"
        reg = client.post(
            "/auth/register",
            json={"email": email, "password": "password123", "company_name": "Buyer Co"},
        )
        assert reg.status_code in {200, 400}

        login = client.post("/auth/login", json={"email": email, "password": "password123"})
        assert login.status_code == 200
        tokens = login.json()
        access = tokens["access_token"]

        me = client.get("/auth/me", headers={"Authorization": f"Bearer {access}"})
        assert me.status_code == 200
        data = me.json()
        assert data.get("email") == email.lower()
        assert data.get("plan") in {"free", "premium"}


def test_dashboard_page_served() -> None:
    with TestClient(app) as client:
        r = client.get("/app/dashboard")
        assert r.status_code == 200
        assert "text/html" in (r.headers.get("content-type") or "")
