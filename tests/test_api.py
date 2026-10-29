"""Tests for the ForgeFit FastAPI backend endpoints."""

from __future__ import annotations

import time
from datetime import UTC, datetime
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from forgefit import __version__
from forgefit.api import app
from forgefit.models import ResilienceConfig, ResilienceReport, Scenario
from forgefit.reports import save_report


def test_api_status() -> None:
    """Test /api/status returns health info and supported capabilities."""
    client = TestClient(app)
    response = client.get("/api/status")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "ok"
    assert data["version"] == __version__
    assert data["toolkit"] == "ForgeFit"
    assert "scenarios" in data["features"]
    assert "ramped" in data["supported_schedules"]
    assert "prometheus" in data["supported_export_formats"]


def test_api_validate_scenario_valid() -> None:
    """Test scenario validation endpoint with valid payload."""
    client = TestClient(app)
    payload = {
        "name": "Web Test Scenario",
        "description": "Validation test",
        "config": {
            "target_url": "http://127.0.0.1:8080/health",
            "request_count": 10,
            "timeout_seconds": 2.0,
        },
    }
    response = client.post("/api/scenarios/validate", json=payload)
    assert response.status_code == 200
    data = response.json()
    assert data["valid"] is True
    assert data["scenario"]["name"] == "Web Test Scenario"


def test_api_validate_scenario_invalid() -> None:
    """Test scenario validation endpoint with invalid payload."""
    client = TestClient(app)
    payload = {
        "name": "Bad Scenario",
        "config": {
            "target_url": "invalid-url",
            "timeout_seconds": -5.0,
        },
    }
    response = client.post("/api/scenarios/validate", json=payload)
    assert response.status_code == 200
    data = response.json()
    assert data["valid"] is False
    assert "error" in data


def test_api_run_external_target_forbidden() -> None:
    """Test safety enforcement: non-loopback target rejected with 403."""
    client = TestClient(app)
    payload = {
        "scenario": {
            "name": "External Attempt",
            "config": {
                "target_url": "https://api.github.com/zen",
                "request_count": 5,
                "allow_external": False,
            },
        }
    }
    response = client.post("/api/runs", json=payload)
    assert response.status_code == 403
    assert "not a local loopback" in response.json()["detail"]


def test_api_run_execution_and_status(tmp_path: Path) -> None:
    """Test submitting a run, retrieving status, and inspecting completed report."""
    client = TestClient(app)
    payload = {
        "scenario": {
            "name": "Local Simulated Run",
            "config": {
                "target_url": "http://127.0.0.1:8080/api",
                "request_count": 5,
                "timeout_seconds": 1.0,
                "failure_probability": 1.0,  # 100% simulated failure -> 0 network calls
                "total_deadline_seconds": 10.0,
                "seed": 42,
            },
        },
        "save_report": True,
        "output_dir": str(tmp_path),
    }

    response = client.post("/api/runs", json=payload)
    assert response.status_code == 200
    init_data = response.json()
    run_id = init_data["run_id"]
    assert init_data["status"] == "queued"
    assert init_data["scenario_name"] == "Local Simulated Run"

    # Poll until completed (simulated failures finish quickly)
    completed = False
    for _ in range(50):
        time.sleep(0.05)
        st_resp = client.get(f"/api/runs/{run_id}?output_dir={tmp_path}")
        assert st_resp.status_code == 200
        st_data = st_resp.json()
        if st_data["status"] == "completed":
            completed = True
            rep = st_data["report"]
            assert rep["total_requests"] == 5
            assert rep["simulated_fault_count"] == 5
            assert rep["failed_requests"] == 5
            assert rep["successful_requests"] == 0
            break

    assert completed, "Run did not complete within expected timeout"


def test_api_reports_list_and_load(tmp_path: Path) -> None:
    """Test listing reports and loading a single report by run_id."""
    now = datetime.now(UTC)
    cfg = ResilienceConfig(
        target_url="http://127.0.0.1:8080/test",
        request_count=5,
    )
    sc = Scenario(name="Report Test Scenario", config=cfg)
    rep = ResilienceReport(
        scenario_name="Report Test Scenario",
        total_requests=5,
        successful_requests=5,
        failed_requests=0,
        simulated_fault_count=0,
        average_latency_ms=12.5,
        p95_latency_ms=15.0,
        start_time=now,
        end_time=now,
    )
    run_id = "run_test_api_001"
    save_report(rep, scenario=sc, output_dir=tmp_path, run_id=run_id)

    client = TestClient(app)
    # Test listing reports
    list_resp = client.get(f"/api/reports?directory={tmp_path}")
    assert list_resp.status_code == 200
    reports = list_resp.json()
    assert len(reports) >= 1
    assert any(r["run_id"] == run_id for r in reports)

    # Test loading single report
    single_resp = client.get(f"/api/reports/{run_id}?directory={tmp_path}")
    assert single_resp.status_code == 200
    single_data = single_resp.json()
    assert single_data["run_id"] == run_id
    assert single_data["scenario_name"] == "Report Test Scenario"


def test_api_reports_compare(tmp_path: Path) -> None:
    """Test comparing two saved reports via /api/reports/compare."""
    now = datetime.now(UTC)
    cfg = ResilienceConfig(
        target_url="http://127.0.0.1:8080/health",
        request_count=10,
    )
    sc = Scenario(name="Compare Scenario", config=cfg)

    rep1 = ResilienceReport(
        scenario_name="Compare Scenario",
        total_requests=10,
        successful_requests=10,
        failed_requests=0,
        simulated_fault_count=0,
        average_latency_ms=50.0,
        p95_latency_ms=60.0,
        start_time=now,
        end_time=now,
    )
    rep2 = ResilienceReport(
        scenario_name="Compare Scenario",
        total_requests=10,
        successful_requests=9,
        failed_requests=1,
        simulated_fault_count=0,
        average_latency_ms=30.0,
        p95_latency_ms=35.0,
        start_time=now,
        end_time=now,
    )

    id1 = "run_baseline_001"
    id2 = "run_comparison_002"
    save_report(rep1, scenario=sc, output_dir=tmp_path, run_id=id1)
    save_report(rep2, scenario=sc, output_dir=tmp_path, run_id=id2)

    client = TestClient(app)
    payload = {
        "baseline_run_id": id1,
        "comparison_run_id": id2,
        "directory": str(tmp_path),
    }
    comp_resp = client.post("/api/reports/compare", json=payload)
    assert comp_resp.status_code == 200
    comp_data = comp_resp.json()
    assert comp_data["baseline_run_id"] == id1
    assert comp_data["comparison_run_id"] == id2
    assert "metrics" in comp_data
    assert "average_latency_ms" in comp_data["metrics"]
    avg_metric = comp_data["metrics"]["average_latency_ms"]
    assert avg_metric["direction"] == "improved"


def test_api_reports_export(tmp_path: Path) -> None:
    """Test exporting saved reports to Prometheus and OpenTelemetry formats."""
    now = datetime.now(UTC)
    cfg = ResilienceConfig(
        target_url="http://127.0.0.1:8080/health",
        request_count=10,
    )
    sc = Scenario(name="Export Scenario", config=cfg)
    rep = ResilienceReport(
        scenario_name="Export Scenario",
        total_requests=10,
        successful_requests=8,
        failed_requests=2,
        simulated_fault_count=0,
        average_latency_ms=25.0,
        p95_latency_ms=30.0,
        start_time=now,
        end_time=now,
    )
    run_id = "run_export_001"
    save_report(rep, scenario=sc, output_dir=tmp_path, run_id=run_id)

    client = TestClient(app)
    # Test Prometheus export
    prom_resp = client.get(
        f"/api/reports/{run_id}/export?format=prometheus&directory={tmp_path}"
    )
    assert prom_resp.status_code == 200
    assert "text/plain" in prom_resp.headers["content-type"]
    assert "forgefit_requests_total" in prom_resp.text
    assert 'scenario="Export Scenario"' in prom_resp.text

    # Test OpenTelemetry export
    otel_resp = client.get(
        f"/api/reports/{run_id}/export?format=otel&directory={tmp_path}"
    )
    assert otel_resp.status_code == 200
    assert "application/json" in otel_resp.headers["content-type"]
    otel_data = otel_resp.json()
    assert "resourceMetrics" in otel_data

    # Test invalid format returns 400
    bad_resp = client.get(
        f"/api/reports/{run_id}/export?format=unknown&directory={tmp_path}"
    )
    assert bad_resp.status_code == 400


def test_api_path_traversal_rejected() -> None:
    """Test API rejects path traversal in directory and run_id parameters."""
    client = TestClient(app)

    # Directory traversal rejection
    resp = client.get("/api/reports?directory=../../sensitive")
    assert resp.status_code == 400
    assert "Directory traversal is not permitted" in resp.json()["detail"]

    # Run ID path traversal rejection
    resp2 = client.get("/api/reports/..%2F..%2Fetc/export")
    assert resp2.status_code in (400, 404)

    resp3 = client.get("/api/reports/run_safe/export?directory=../reports")
    assert resp3.status_code == 400


def test_api_concurrency_bounding() -> None:
    """Test JobManager enforces active concurrent run limit."""
    from forgefit.api import JobManager

    jm = JobManager(max_concurrent=2)
    cfg = ResilienceConfig(
        target_url="http://127.0.0.1:8000/api/status",
        request_count=5,
    )
    sc = Scenario(name="Bounded Scenario", config=cfg)

    id1 = jm.create_run(sc)
    id2 = jm.create_run(sc)
    assert id1 and id2

    # 3rd run should raise 429
    from fastapi import HTTPException

    with pytest.raises(HTTPException) as exc_info:
        jm.create_run(sc)
    assert exc_info.value.status_code == 429


def test_cors_origins_parsing(monkeypatch: pytest.MonkeyPatch) -> None:
    """Test get_cors_origins parses environment variable and filters invalid entries."""
    from forgefit.api import (
        DEFAULT_CORS_ORIGINS,
        get_cors_origin_regex,
        get_cors_origins,
    )

    # When unset, returns DEFAULT_CORS_ORIGINS and None regex
    monkeypatch.delenv("FORGEFIT_CORS_ORIGINS", raising=False)
    monkeypatch.delenv("FORGEFIT_CORS_ORIGIN_REGEX", raising=False)
    assert get_cors_origins() == DEFAULT_CORS_ORIGINS
    assert get_cors_origin_regex() is None

    # Custom comma-separated list with wildcard
    monkeypatch.setenv(
        "FORGEFIT_CORS_ORIGINS",
        "https://my-app.vercel.app, https://forgefit.example.com/, *, https://*.vercel.app",
    )
    parsed = get_cors_origins()
    assert "https://my-app.vercel.app" in parsed
    assert "https://forgefit.example.com" in parsed
    # Wildcards are stripped from allow_origins for credentials safety
    assert "*" not in parsed
    assert "https://*.vercel.app" not in parsed

    # Wildcard is translated into allow_origin_regex
    regex = get_cors_origin_regex()
    assert regex is not None
    import re

    compiled = re.compile(regex)
    assert compiled.fullmatch("https://forgefit.vercel.app")
    assert compiled.fullmatch("https://forgefit-preview-123.vercel.app")
    assert not compiled.fullmatch("https://unauthorized.com")


def test_api_key_protection(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    """Test API key authentication for POST /api/runs."""
    client = TestClient(app)
    run_payload = {
        "scenario": {
            "name": "Auth Scenario",
            "config": {
                "target_url": "http://127.0.0.1:8000/api/status",
                "request_count": 1,
            },
        },
        "output_dir": str(tmp_path),
    }

    # Case 1: FORGEFIT_API_KEY is not set -> Unauthenticated access allowed
    monkeypatch.delenv("FORGEFIT_API_KEY", raising=False)
    status_resp = client.get("/api/status")
    assert status_resp.status_code == 200
    assert status_resp.json()["api_key_required"] is False

    run_resp = client.post("/api/runs", json=run_payload)
    assert run_resp.status_code == 200

    # Case 2: FORGEFIT_API_KEY is configured
    test_key = "test-secret-key-42"
    monkeypatch.setenv("FORGEFIT_API_KEY", test_key)

    # Status endpoint reflects requirement without exposing key
    status_resp = client.get("/api/status")
    assert status_resp.status_code == 200
    assert status_resp.json()["api_key_required"] is True
    assert "test-secret-key-42" not in status_resp.text

    # Missing header -> 401
    missing_resp = client.post("/api/runs", json=run_payload)
    assert missing_resp.status_code == 401
    assert "Missing required X-ForgeFit-API-Key" in missing_resp.json()["detail"]

    # Incorrect header -> 401
    wrong_resp = client.post(
        "/api/runs",
        json=run_payload,
        headers={"X-ForgeFit-API-Key": "wrong-key"},
    )
    assert wrong_resp.status_code == 401
    assert "Invalid X-ForgeFit-API-Key" in wrong_resp.json()["detail"]

    # Correct header -> 200
    correct_resp = client.post(
        "/api/runs",
        json=run_payload,
        headers={"X-ForgeFit-API-Key": test_key},
    )
    assert correct_resp.status_code == 200
    assert "run_id" in correct_resp.json()


def test_configured_reports_dir_isolation(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """Test that FORGEFIT_REPORTS_DIR locks the reports directory."""
    client = TestClient(app)
    custom_reports = tmp_path / "custom_reports"
    custom_reports.mkdir(parents=True, exist_ok=True)

    monkeypatch.setenv("FORGEFIT_REPORTS_DIR", str(custom_reports))

    status_resp = client.get("/api/status")
    assert status_resp.status_code == 200
    assert status_resp.json()["default_output_dir"] == str(custom_reports)

    # Save a report directly in custom_reports
    sc = Scenario(
        name="Locked Dir Scenario",
        config=ResilienceConfig(target_url="http://127.0.0.1:8000/api/status"),
    )
    now = datetime.now(UTC)
    rep = ResilienceReport(
        scenario_name="Locked Dir Scenario",
        total_requests=1,
        successful_requests=1,
        failed_requests=0,
        simulated_fault_count=0,
        average_latency_ms=10.0,
        p95_latency_ms=10.0,
        start_time=now,
        end_time=now,
    )
    save_report(rep, scenario=sc, output_dir=custom_reports, run_id="locked_run_1")

    # Listing with an attempted client override still uses custom_reports
    list_resp = client.get("/api/reports?directory=some_other_directory")
    assert list_resp.status_code == 200
    reports = list_resp.json()
    assert len(reports) == 1
    assert reports[0]["run_id"] == "locked_run_1"

    # Fetching report
    get_resp = client.get("/api/reports/locked_run_1?directory=some_other_directory")
    assert get_resp.status_code == 200
    assert get_resp.json()["run_id"] == "locked_run_1"
