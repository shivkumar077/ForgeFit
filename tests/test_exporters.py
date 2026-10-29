"""Focused tests for Prometheus and OpenTelemetry metrics exporters."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from forgefit.exporters import (
    export_opentelemetry,
    export_prometheus,
    export_report,
)


def _make_dummy_report_data() -> dict:
    """Helper to construct dummy report dictionary matching ForgeFit report schema."""
    return {
        "run_id": "run_20261030_120000_abc123",
        "scenario_name": 'Demo "Test" Scenario',
        "created_at": "2026-10-30T12:00:00+00:00",
        "report": {
            "scenario_name": 'Demo "Test" Scenario',
            "total_requests": 20,
            "successful_requests": 18,
            "failed_requests": 2,
            "simulated_fault_count": 1,
            "http_error_count": 1,
            "timeout_count": 0,
            "connection_error_count": 0,
            "average_latency_ms": 45.5,
            "p95_latency_ms": 78.2,
            "total_duration_ms": 1250.0,
            "outcomes": [],
        },
    }


def test_export_prometheus_format() -> None:
    """Prometheus exporter produces valid exposition format with correct escaping."""
    data = _make_dummy_report_data()
    output = export_prometheus(data)

    assert "# HELP forgefit_requests_total" in output
    assert "# TYPE forgefit_requests_total counter" in output
    assert "forgefit_requests_total{" in output
    assert " 20" in output

    assert "# HELP forgefit_requests_success_total" in output
    assert "forgefit_requests_success_total{" in output
    assert " 18" in output

    assert "# HELP forgefit_requests_failed_total" in output
    assert "forgefit_requests_failed_total{" in output
    assert " 2" in output

    assert 'category="http_error"' in output
    assert 'category="simulated_fault"' in output

    # Latencies in seconds
    assert "forgefit_request_latency_average_seconds{" in output
    assert " 0.0455" in output
    assert "forgefit_request_latency_p95_seconds{" in output
    assert " 0.0782" in output
    assert "forgefit_execution_duration_seconds{" in output
    assert " 1.25" in output

    # Label escaping check
    assert 'scenario="Demo \\"Test\\" Scenario"' in output


def test_export_opentelemetry_json() -> None:
    """OpenTelemetry exporter produces compliant OTLP JSON structure."""
    data = _make_dummy_report_data()
    otel_dict = export_opentelemetry(data)

    assert "resourceMetrics" in otel_dict
    rm = otel_dict["resourceMetrics"][0]
    resource_attrs = rm["resource"]["attributes"]
    attr_map = {a["key"]: a["value"]["stringValue"] for a in resource_attrs}
    assert attr_map["service.name"] == "forgefit"
    assert attr_map["forgefit.run_id"] == "run_20261030_120000_abc123"

    scope_metrics = rm["scopeMetrics"][0]
    metrics = {m["name"]: m for m in scope_metrics["metrics"]}

    assert "forgefit.requests.total" in metrics
    total_dp = metrics["forgefit.requests.total"]["sum"]["dataPoints"][0]
    assert total_dp["asInt"] == 20

    assert "forgefit.request.latency.average" in metrics
    avg_dp = metrics["forgefit.request.latency.average"]["gauge"]["dataPoints"][0]
    assert avg_dp["asDouble"] == 0.0455

    assert "forgefit.execution.duration" in metrics
    dur_dp = metrics["forgefit.execution.duration"]["gauge"]["dataPoints"][0]
    assert dur_dp["asDouble"] == 1.25


def test_export_report_file_and_format_selection(tmp_path: Path) -> None:
    """export_report loads saved files and supports prometheus and otel formats."""
    data = _make_dummy_report_data()
    report_file = tmp_path / "test_report.json"
    report_file.write_text(json.dumps(data), encoding="utf-8")

    # Prometheus export from file
    prom_text = export_report(report_file, format="prometheus")
    assert "forgefit_requests_total{" in prom_text

    # OpenTelemetry export from file
    otel_text = export_report(report_file, format="otel")
    otel_json = json.loads(otel_text)
    assert "resourceMetrics" in otel_json

    # Unsupported format error
    with pytest.raises(ValueError, match="Unsupported export format 'datadog'"):
        export_report(report_file, format="datadog")
