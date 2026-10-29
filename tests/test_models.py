"""Tests for ForgeFit domain models and serialization."""

from __future__ import annotations

import json
from datetime import UTC, datetime

from forgefit.config import ResilienceConfig
from forgefit.models import RequestOutcome, ResilienceReport, Scenario


def test_scenario_model() -> None:
    """Scenario model initializes and serializes correctly."""
    cfg = ResilienceConfig(target_url="https://api.example.com/status")
    scenario = Scenario(
        name="health_check_resilience",
        config=cfg,
        description="Verify health endpoint resilience under latency",
        tags=["smoke", "latency"],
    )

    data = scenario.to_dict()
    assert data["name"] == "health_check_resilience"
    assert data["description"] == "Verify health endpoint resilience under latency"
    assert data["tags"] == ["smoke", "latency"]
    assert data["config"]["target_url"] == "https://api.example.com/status"

    # Confirm JSON-dumpable
    serialized = json.dumps(data)
    assert "health_check_resilience" in serialized


def test_request_outcome_model() -> None:
    """RequestOutcome model records metrics and produces ISO timestamps."""
    fixed_time = datetime(2026, 10, 30, 12, 0, 0, tzinfo=UTC)
    outcome = RequestOutcome(
        iteration=1,
        target_url="https://api.example.com/users",
        status_code=200,
        latency_ms=145.678,
        success=True,
        simulated_fault=False,
        error_message=None,
        timestamp=fixed_time,
    )

    data = outcome.to_dict()
    assert data["iteration"] == 1
    assert data["target_url"] == "https://api.example.com/users"
    assert data["status_code"] == 200
    assert data["latency_ms"] == 145.68
    assert data["success"] is True
    assert data["simulated_fault"] is False
    assert data["error_message"] is None
    assert data["timestamp"] == "2026-10-30T12:00:00+00:00"

    # JSON serialization check
    json_str = json.dumps(data)
    decoded = json.loads(json_str)
    assert decoded["latency_ms"] == 145.68


def test_resilience_report_model() -> None:
    """ResilienceReport aggregates outcomes and serializes cleanly."""
    t_start = datetime(2026, 10, 30, 12, 0, 0, tzinfo=UTC)
    t_end = datetime(2026, 10, 30, 12, 1, 0, tzinfo=UTC)

    o1 = RequestOutcome(
        iteration=1,
        target_url="https://api.example.com/data",
        status_code=200,
        latency_ms=50.2,
        success=True,
        timestamp=t_start,
    )
    o2 = RequestOutcome(
        iteration=2,
        target_url="https://api.example.com/data",
        status_code=503,
        latency_ms=500.8,
        success=False,
        simulated_fault=True,
        error_message="Injected Service Unavailable",
        timestamp=t_end,
    )

    report = ResilienceReport(
        scenario_name="data_endpoint_stress",
        total_requests=2,
        successful_requests=1,
        failed_requests=1,
        simulated_fault_count=1,
        average_latency_ms=275.5,
        p95_latency_ms=500.8,
        start_time=t_start,
        end_time=t_end,
        outcomes=[o1, o2],
        metadata={"environment": "staging", "runner": "forgefit-foundation"},
    )

    data = report.to_dict()
    assert data["scenario_name"] == "data_endpoint_stress"
    assert data["total_requests"] == 2
    assert data["successful_requests"] == 1
    assert data["failed_requests"] == 1
    assert data["simulated_fault_count"] == 1
    assert len(data["outcomes"]) == 2
    assert data["outcomes"][0]["status_code"] == 200
    assert data["outcomes"][1]["status_code"] == 503
    assert data["outcomes"][1]["simulated_fault"] is True
    assert data["metadata"]["environment"] == "staging"

    # Guarantee pure JSON compatibility
    json_bytes = json.dumps(data).encode("utf-8")
    assert len(json_bytes) > 0


def test_resilience_report_from_outcomes_empty() -> None:
    """from_outcomes gracefully handles 0 outcomes with 0.0 metrics."""
    t_start = datetime(2026, 10, 30, 12, 0, 0, tzinfo=UTC)
    t_end = datetime(2026, 10, 30, 12, 0, 5, tzinfo=UTC)

    report = ResilienceReport.from_outcomes(
        scenario_name="empty_run",
        outcomes=[],
        start_time=t_start,
        end_time=t_end,
    )
    assert report.total_requests == 0
    assert report.successful_requests == 0
    assert report.failed_requests == 0
    assert report.average_latency_ms == 0.0
    assert report.p95_latency_ms == 0.0
    assert report.total_duration_ms == 5000.0
    assert report.interrupted is False


def test_resilience_report_from_outcomes_calculation() -> None:
    """from_outcomes correctly aggregates failure categories and p95."""
    t_start = datetime(2026, 10, 30, 12, 0, 0, tzinfo=UTC)
    t_end = datetime(2026, 10, 30, 12, 0, 10, tzinfo=UTC)

    outcomes = [
        RequestOutcome(
            iteration=1,
            target_url="http://localhost",
            status_code=200,
            latency_ms=10.0,
            success=True,
        ),
        RequestOutcome(
            iteration=2,
            target_url="http://localhost",
            status_code=500,
            latency_ms=20.0,
            success=False,
            failure_category="http_error",
        ),
        RequestOutcome(
            iteration=3,
            target_url="http://localhost",
            status_code=None,
            latency_ms=30.0,
            success=False,
            failure_category="timeout",
        ),
        RequestOutcome(
            iteration=4,
            target_url="http://localhost",
            status_code=None,
            latency_ms=40.0,
            success=False,
            failure_category="connection_error",
        ),
        RequestOutcome(
            iteration=5,
            target_url="http://localhost",
            status_code=None,
            latency_ms=50.0,
            success=False,
            simulated_fault=True,
            failure_category="simulated_failure",
        ),
    ]

    report = ResilienceReport.from_outcomes(
        scenario_name="all_categories",
        outcomes=outcomes,
        start_time=t_start,
        end_time=t_end,
        interrupted=True,
    )
    assert report.total_requests == 5
    assert report.successful_requests == 1
    assert report.failed_requests == 4
    assert report.http_error_count == 1
    assert report.timeout_count == 1
    assert report.connection_error_count == 1
    assert report.simulated_fault_count == 1
    assert report.average_latency_ms == 30.0
    assert report.p95_latency_ms == 50.0
    assert report.interrupted is True


def test_resilience_report_counts_and_metrics_consistency() -> None:
    """Report counts are internally consistent and p95 follows nearest rank formula."""
    t_start = datetime(2026, 10, 30, 12, 0, 0, tzinfo=UTC)
    t_end = datetime(2026, 10, 30, 12, 1, 0, tzinfo=UTC)

    # 10 outcomes: 6 successes, 1 http error, 1 timeout, 1 conn error, 1 simulated
    # Latencies: 10, 20, 30, 40, 50, 60, 70, 80, 90, 100
    outcomes: list[RequestOutcome] = []
    for i in range(1, 11):
        if i <= 6:
            outcomes.append(
                RequestOutcome(
                    iteration=i,
                    target_url="http://localhost",
                    status_code=200,
                    latency_ms=float(i * 10),
                    success=True,
                )
            )
        elif i == 7:
            outcomes.append(
                RequestOutcome(
                    iteration=i,
                    target_url="http://localhost",
                    status_code=500,
                    latency_ms=70.0,
                    success=False,
                    failure_category="http_error",
                )
            )
        elif i == 8:
            outcomes.append(
                RequestOutcome(
                    iteration=i,
                    target_url="http://localhost",
                    status_code=None,
                    latency_ms=80.0,
                    success=False,
                    failure_category="timeout",
                )
            )
        elif i == 9:
            outcomes.append(
                RequestOutcome(
                    iteration=i,
                    target_url="http://localhost",
                    status_code=None,
                    latency_ms=90.0,
                    success=False,
                    failure_category="connection_error",
                )
            )
        else:
            outcomes.append(
                RequestOutcome(
                    iteration=i,
                    target_url="http://localhost",
                    status_code=None,
                    latency_ms=100.0,
                    success=False,
                    simulated_fault=True,
                    failure_category="simulated_failure",
                )
            )

    report = ResilienceReport.from_outcomes(
        scenario_name="consistency_check",
        outcomes=outcomes,
        start_time=t_start,
        end_time=t_end,
    )

    # Invariant 1: total equals successful + failed
    assert report.total_requests == report.successful_requests + report.failed_requests
    assert report.total_requests == 10
    assert report.successful_requests == 6
    assert report.failed_requests == 4

    # Invariant 2: failed equals sum of all failure categories
    all_categories_sum = (
        report.http_error_count
        + report.timeout_count
        + report.connection_error_count
        + report.simulated_fault_count
    )
    assert report.failed_requests == all_categories_sum

    # Invariant 3: average latency is exact mean (550 / 10 = 55.0)
    assert report.average_latency_ms == 55.0

    # Invariant 4: nearest rank p95 of 10 items is:
    # index ceil(0.95 * 10) - 1 = 10 - 1 = 9 (100.0)
    assert report.p95_latency_ms == 100.0

    # Invariant 5: JSON serialization is valid and deterministic
    as_dict = report.to_dict()
    as_json = json.dumps(as_dict)
    restored = json.loads(as_json)
    assert restored["total_requests"] == 10
    assert restored["failed_requests"] == 4
    assert len(restored["outcomes"]) == 10
