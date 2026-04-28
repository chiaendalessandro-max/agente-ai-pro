from __future__ import annotations

import asyncio
import statistics
import time

import pytest
from fastapi import HTTPException

from app.api.routes import leads as leads_routes
from app.models.user import User
from app.schemas.lead import CompanySearchIn


def _assert_contract_when_200(data: dict) -> None:
    assert "results" in data and isinstance(data["results"], list)
    assert "message" in data and isinstance(data["message"], str)
    assert "meta" in data and isinstance(data["meta"], dict)
    for key in ("queries_used", "raw_results_count", "valid_results_count", "discarded_results_count"):
        assert key in data["meta"]


async def _stress_run(mode: str, user_plan: str, payloads: list[dict], expected_statuses: set[int]) -> tuple[list[tuple[int, dict, float]], dict]:
    user = User(email=f"{user_plan}@test.local", password_hash="x", company_name="acme", plan=user_plan)
    latencies_ms: list[float] = []
    responses: list[tuple[int, dict, float]] = []
    errors = 0
    failures = 0

    async def _one(payload: dict) -> tuple[int, dict, float]:
        start = time.perf_counter()
        try:
            data = await leads_routes.company_search_endpoint(
                payload=CompanySearchIn(**payload),
                mode=mode,
                user=user,
            )
            status = 200
        except HTTPException as exc:
            status = int(exc.status_code)
            data = {"detail": exc.detail}
        elapsed = (time.perf_counter() - start) * 1000.0
        return status, data, elapsed

    batch = await asyncio.gather(*[_one(p) for p in payloads], return_exceptions=False)
    for status, data, elapsed in batch:
        latencies_ms.append(elapsed)
        responses.append((status, data, elapsed))
        if status >= 500:
            errors += 1
        if status not in expected_statuses:
            failures += 1

    metrics = {
        "requests_simulated": len(payloads),
        "errors": errors,
        "average_response_ms": round(statistics.mean(latencies_ms), 2) if latencies_ms else 0.0,
        "failures": failures,
    }
    return responses, metrics


@pytest.mark.asyncio
async def test_stress_normal_10_concurrent_same_query(monkeypatch: pytest.MonkeyPatch) -> None:
    def _fake_normal(query: str, country: str, _sector: str, limit: int) -> dict:
        return {
            "mode": "normal",
            "count": 1,
            "results": [{"company_name": f"{query}-{country}", "score": "MEDIUM"}],
            "message": "",
            "meta": {
                "queries_used": [f"{query} companies {country}"],
                "raw_results_count": 10,
                "valid_results_count": 1,
                "discarded_results_count": 9,
            },
        }

    monkeypatch.setattr(leads_routes, "normal_search_service", _fake_normal)
    payloads = [{"query": "aviazione", "country": "Italia", "limit": 10} for _ in range(10)]
    results, metrics = await _stress_run(mode="normal", user_plan="free", payloads=payloads, expected_statuses={200})

    print("[STRESS normal-10]", metrics)
    assert metrics["errors"] == 0
    assert metrics["failures"] == 0
    for status, data, _ in results:
        assert status == 200
        _assert_contract_when_200(data)


@pytest.mark.asyncio
async def test_stress_normal_20_concurrent_mixed_query_and_country(monkeypatch: pytest.MonkeyPatch) -> None:
    def _fake_normal(query: str, country: str, _sector: str, limit: int) -> dict:
        return {
            "mode": "normal",
            "count": 1,
            "results": [{"company_name": f"{query}-{country}", "score": "MEDIUM"}],
            "message": "",
            "meta": {
                "queries_used": [f"{query} companies {country}"],
                "raw_results_count": 8,
                "valid_results_count": 1,
                "discarded_results_count": 7,
            },
        }

    monkeypatch.setattr(leads_routes, "normal_search_service", _fake_normal)
    queries = ["aviazione", "private jet", "charter", "aerotaxi", "flight ops"]
    countries = ["Italia", "France", "Germany", "Spain"]
    payloads = [{"query": queries[i % len(queries)], "country": countries[i % len(countries)], "limit": 10} for i in range(20)]
    results, metrics = await _stress_run(mode="normal", user_plan="free", payloads=payloads, expected_statuses={200})

    print("[STRESS normal-20]", metrics)
    assert metrics["errors"] == 0
    assert metrics["failures"] == 0
    for status, data, _ in results:
        assert status == 200
        _assert_contract_when_200(data)


@pytest.mark.asyncio
async def test_stress_premium_free_403(monkeypatch: pytest.MonkeyPatch) -> None:
    called = {"premium_calls": 0}

    def _fake_premium(*_args, **_kwargs):
        called["premium_calls"] += 1
        return {"mode": "premium", "count": 0, "results": [], "message": "", "meta": {}}

    monkeypatch.setattr(leads_routes, "premium_search_service", _fake_premium)
    payloads = [{"query": "aviazione", "country": "Italia", "limit": 10} for _ in range(10)]
    results, metrics = await _stress_run(mode="premium", user_plan="free", payloads=payloads, expected_statuses={403})

    print("[STRESS premium-free-10]", metrics)
    assert metrics["errors"] == 0
    assert metrics["failures"] == 0
    assert called["premium_calls"] == 0
    for status, data, _ in results:
        assert status == 403
        assert "detail" in data


@pytest.mark.asyncio
async def test_stress_premium_premium_20_valid_json(monkeypatch: pytest.MonkeyPatch) -> None:
    def _fake_premium(query: str, country: str, _sector: str, limit: int) -> dict:
        return {
            "mode": "premium",
            "count": 1,
            "results": [{"company_name": f"{query}-{country}", "score": "HIGH"}],
            "message": "",
            "meta": {
                "queries_used": [f"{query} companies {country}"],
                "raw_results_count": 9,
                "valid_results_count": 1,
                "discarded_results_count": 8,
            },
        }

    monkeypatch.setattr(leads_routes, "premium_search_service", _fake_premium)
    payloads = [{"query": "aviazione", "country": "Italia", "limit": 10} for _ in range(20)]
    results, metrics = await _stress_run(mode="premium", user_plan="premium", payloads=payloads, expected_statuses={200})

    print("[STRESS premium-premium-20]", metrics)
    assert metrics["errors"] == 0
    assert metrics["failures"] == 0
    for status, data, _ in results:
        assert status == 200
        _assert_contract_when_200(data)


@pytest.mark.asyncio
async def test_stress_no_results_returns_empty(monkeypatch: pytest.MonkeyPatch) -> None:
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
    payloads = [{"query": "nores", "country": "Italia", "limit": 10} for _ in range(10)]
    results, metrics = await _stress_run(mode="normal", user_plan="free", payloads=payloads, expected_statuses={200})

    print("[STRESS no-results-10]", metrics)
    assert metrics["errors"] == 0
    assert metrics["failures"] == 0
    for status, data, _ in results:
        assert status == 200
        _assert_contract_when_200(data)
        assert data["results"] == []


@pytest.mark.asyncio
async def test_stress_sources_unreachable_no_crash(monkeypatch: pytest.MonkeyPatch) -> None:
    def _failing_premium(_query: str, _country: str, _sector: str, _limit: int) -> dict:
        raise RuntimeError("upstream source timeout")

    monkeypatch.setattr(leads_routes, "premium_search_service", _failing_premium)
    payloads = [{"query": "aviazione", "country": "Italia", "limit": 10} for _ in range(10)]
    results, metrics = await _stress_run(mode="premium", user_plan="premium", payloads=payloads, expected_statuses={200})

    print("[STRESS upstream-fail-10]", metrics)
    assert metrics["errors"] == 0
    assert metrics["failures"] == 0
    for status, data, _ in results:
        assert status == 200
        _assert_contract_when_200(data)
        assert isinstance(data["results"], list)
