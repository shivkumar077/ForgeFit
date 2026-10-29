"""Tests for the ForgeFit FastAPI backend endpoints."""

from __future__ import annotations

import time
from datetime import UTC, datetime
from pathlib import Path

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
