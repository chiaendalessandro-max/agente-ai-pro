"""Smoke API: richiedono dipendenze installate (SQLAlchemy, FastAPI, ecc.)."""
from __future__ import annotations

import pytest

try:
    from fastapi.testclient import TestClient

    from app.main import app

    _HAVE_APP = True
except Exception:  # pragma: no cover - ambiente senza stack completo
    _HAVE_APP = False
    app = None  # type: ignore[assignment]
    TestClient = None  # type: ignore[assignment,misc]

pytestmark = pytest.mark.skipif(not _HAVE_APP, reason="Stack applicativo non importabile (installare requirements su Python 3.11–3.12)")


def test_health_ok() -> None:
    with TestClient(app) as client:
        r = client.get("/health")
        assert r.status_code == 200
        data = r.json()
        assert data.get("status") == "ok"
        assert "version" in data


def test_ready_database() -> None:
    with TestClient(app) as client:
        r = client.get("/ready")
        assert r.status_code == 200
        data = r.json()
        assert data.get("status") == "ready"
        assert data.get("database") == "ok"


def test_openapi_available() -> None:
    with TestClient(app) as client:
        r = client.get("/openapi.json")
        assert r.status_code == 200
        spec = r.json()
        assert spec.get("openapi")
        assert "/health" in str(spec.get("paths", {}))
