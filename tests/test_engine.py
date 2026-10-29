"""Tests for ForgeFit resilience execution engine."""

from __future__ import annotations

from unittest.mock import MagicMock

import pytest

from forgefit.client import ClientResponse, ResilienceClient
from forgefit.config import ResilienceConfig
from forgefit.engine import ResilienceEngine, SafetyViolationError
from forgefit.models import Scenario


def test_engine_loopback_allowed_by_default() -> None:
    """ResilienceEngine allows loopback execution without external flags."""
    mock_client = MagicMock(spec=ResilienceClient)
    mock_client.send_request.return_value = ClientResponse(
        status_code=200,
        latency_ms=10.0,
        success=True,
        failure_category=None,
        error_message=None,
        start_time=MagicMock(),
        end_time=MagicMock(),
    )

    cfg = ResilienceConfig(
        target_url="http://127.0.0.1:8000/api",
        request_count=3,
    )
    scenario = Scenario(name="local_test", config=cfg)
    engine = ResilienceEngine(client=mock_client)

    report = engine.run_scenario(scenario)
    assert report.total_requests == 3
    assert report.successful_requests == 3
    assert mock_client.send_request.call_count == 3


def test_engine_external_target_rejected_by_default() -> None:
    """ResilienceEngine rejects external targets without authorization flags."""
    cfg = ResilienceConfig(
        target_url="https://api.external.com/health",
        allow_external=False,
        authorized_acknowledgement=False,
    )
    scenario = Scenario(name="external_denied", config=cfg)
    engine = ResilienceEngine()

    with pytest.raises(SafetyViolationError, match="requires both allow_external=True"):
        engine.run_scenario(scenario)


def test_engine_external_target_allowed_with_acknowledgement() -> None:
    """ResilienceEngine allows external targets when both flags are explicitly True."""
    mock_client = MagicMock(spec=ResilienceClient)
    mock_client.send_request.return_value = ClientResponse(
        status_code=200,
        latency_ms=15.0,
        success=True,
        failure_category=None,
        error_message=None,
        start_time=MagicMock(),
        end_time=MagicMock(),
    )

    cfg = ResilienceConfig(
        target_url="https://api.external.com/health",
        allow_external=True,
        authorized_acknowledgement=True,
        request_count=2,
    )
    scenario = Scenario(name="external_allowed", config=cfg)
    engine = ResilienceEngine(client=mock_client)

    report = engine.run_scenario(scenario)
    assert report.total_requests == 2
    assert report.successful_requests == 2


def test_engine_simulated_fault_zero_network_calls() -> None:
    """Simulated failures are generated locally with zero outbound network calls."""
    mock_client = MagicMock(spec=ResilienceClient)
    # If client is called, it would fail this test
    mock_client.send_request.side_effect = AssertionError(
        "Outbound request attempted during simulated failure"
    )

    cfg = ResilienceConfig(
        target_url="http://localhost:8080/test",
        request_count=5,
        failure_probability=1.0,  # 100% simulated failure
    )
    scenario = Scenario(name="simulated_fault_test", config=cfg)
    engine = ResilienceEngine(client=mock_client)

    report = engine.run_scenario(scenario)
    assert report.total_requests == 5
    assert report.successful_requests == 0
    assert report.failed_requests == 5
    assert report.simulated_fault_count == 5
    assert mock_client.send_request.call_count == 0

    for outcome in report.outcomes:
        assert outcome.simulated_fault is True
        assert outcome.status_code is None
        assert outcome.failure_category == "simulated_failure"
        assert "no outbound request made" in (outcome.error_message or "")


def test_engine_deterministic_seed() -> None:
    """Fixed seed produces repeatable fault decisions."""
    mock_client = MagicMock(spec=ResilienceClient)
    mock_client.send_request.return_value = ClientResponse(
        status_code=200,
        latency_ms=10.0,
        success=True,
        failure_category=None,
        error_message=None,
        start_time=MagicMock(),
        end_time=MagicMock(),
    )

    cfg1 = ResilienceConfig(
        target_url="http://localhost/test",
        request_count=10,
        failure_probability=0.4,
        seed=12345,
    )
    report1 = ResilienceEngine(client=mock_client).run_scenario(
        Scenario(name="s1", config=cfg1)
    )

    cfg2 = ResilienceConfig(
        target_url="http://localhost/test",
        request_count=10,
        failure_probability=0.4,
        seed=12345,
    )
    report2 = ResilienceEngine(client=mock_client).run_scenario(
        Scenario(name="s2", config=cfg2)
    )

    faults1 = [o.simulated_fault for o in report1.outcomes]
    faults2 = [o.simulated_fault for o in report2.outcomes]
    assert faults1 == faults2
    assert any(faults1)  # Ensure at least some faults triggered


def test_engine_artificial_latency_with_mock_sleeper() -> None:
    """Artificial latency is applied via sleeper without real-world sleeping."""
    mock_client = MagicMock(spec=ResilienceClient)
    mock_client.send_request.return_value = ClientResponse(
        status_code=200,
        latency_ms=5.0,
        success=True,
        failure_category=None,
        error_message=None,
        start_time=MagicMock(),
        end_time=MagicMock(),
    )

    sleep_calls: list[float] = []

    def mock_sleeper(seconds: float) -> None:
        sleep_calls.append(seconds)

    cfg = ResilienceConfig(
        target_url="http://localhost/test",
        request_count=4,
        artificial_latency_ms=250,
    )
    scenario = Scenario(name="latency_test", config=cfg)
    engine = ResilienceEngine(client=mock_client, sleeper=mock_sleeper)

    report = engine.run_scenario(scenario)
    assert len(sleep_calls) == 4
    assert sleep_calls == [0.25, 0.25, 0.25, 0.25]
    # Each outcome includes added artificial latency
    for outcome in report.outcomes:
        assert outcome.latency_ms >= 250.0


def test_engine_total_deadline_exhaustion() -> None:
    """Engine stops scheduling requests when total execution deadline is reached."""
    mock_client = MagicMock(spec=ResilienceClient)
    mock_client.send_request.return_value = ClientResponse(
        status_code=200,
        latency_ms=10.0,
        success=True,
        failure_category=None,
        error_message=None,
        start_time=MagicMock(),
        end_time=MagicMock(),
    )

    # Simulated clock that advances by 6 seconds per call
    time_cursor = 100.0

    def mock_clock() -> float:
        nonlocal time_cursor
        current = time_cursor
        time_cursor += 6.0
        return current

    cfg = ResilienceConfig(
        target_url="http://localhost/test",
        request_count=10,
        total_deadline_seconds=15.0,
    )
    scenario = Scenario(name="deadline_test", config=cfg)
    engine = ResilienceEngine(client=mock_client, clock=mock_clock)

    report = engine.run_scenario(scenario)
    # Clock increments 6s each check; after 3 requests (0, 6, 12, 18),
    # 18 >= 15 deadline triggers
    assert report.interrupted is True
    assert report.total_requests < 10
    assert report.total_requests >= 2


def test_engine_report_metrics_calculation() -> None:
    """Report accurately aggregates mixed outcome metrics and p95."""
    mock_client = MagicMock(spec=ResilienceClient)
    responses = [
        ClientResponse(
            status_code=200,
            latency_ms=10.0,
            success=True,
            failure_category=None,
            error_message=None,
            start_time=MagicMock(),
            end_time=MagicMock(),
        ),
        ClientResponse(
            status_code=500,
            latency_ms=100.0,
            success=False,
            failure_category="http_error",
            error_message="HTTP 500",
            start_time=MagicMock(),
            end_time=MagicMock(),
        ),
        ClientResponse(
            status_code=None,
            latency_ms=200.0,
            success=False,
            failure_category="timeout",
            error_message="Timeout",
            start_time=MagicMock(),
            end_time=MagicMock(),
        ),
    ]
    mock_client.send_request.side_effect = responses

    cfg = ResilienceConfig(
        target_url="http://localhost/test",
        request_count=3,
    )
    scenario = Scenario(name="metrics_scenario", config=cfg)
    engine = ResilienceEngine(client=mock_client)

    report = engine.run_scenario(scenario)
    assert report.total_requests == 3
    assert report.successful_requests == 1
    assert report.failed_requests == 2
    assert report.http_error_count == 1
    assert report.timeout_count == 1
    assert report.connection_error_count == 0
    assert report.simulated_fault_count == 0
    # Latencies: [10.0, 100.0, 200.0] -> avg = 310 / 3 = 103.33
    assert report.average_latency_ms == 103.33
    # Nearest rank p95 of 3 items:
    # ceil(0.95 * 3) - 1 = ceil(2.85) - 1 = 3 - 1 = index 2 (200.0)
    assert report.p95_latency_ms == 200.0


def test_engine_request_timeout_clamped_to_remaining_budget() -> None:
    """Request timeout is clamped to the remaining total execution budget."""
    mock_client = MagicMock(spec=ResilienceClient)
    mock_client.send_request.return_value = ClientResponse(
        status_code=200,
        latency_ms=10.0,
        success=True,
        failure_category=None,
        error_message=None,
        start_time=MagicMock(),
        end_time=MagicMock(),
    )

    # Clock: start at 0, first iteration at 0.0 (remaining 10.0),
    # second iteration at 7.5 (remaining 2.5)
    call_times = [0.0, 0.0, 7.5, 11.0]
    call_idx = 0

    def mock_clock() -> float:
        nonlocal call_idx
        val = call_times[min(call_idx, len(call_times) - 1)]
        call_idx += 1
        return val

    cfg = ResilienceConfig(
        target_url="http://localhost/test",
        timeout_seconds=5.0,  # Configured timeout is 5.0s
        request_count=3,
        total_deadline_seconds=10.0,
    )
    scenario = Scenario(name="timeout_clamp_test", config=cfg)
    engine = ResilienceEngine(client=mock_client, clock=mock_clock)

    report = engine.run_scenario(scenario)

    assert mock_client.send_request.call_count == 2
    # First call had remaining 10.0s, so min(5.0, 10.0) = 5.0
    first_call_timeout = mock_client.send_request.call_args_list[0].kwargs[
        "timeout_seconds"
    ]
    assert first_call_timeout == 5.0
    # Second call had remaining 2.5s, so min(5.0, 2.5) = 2.5 (clamped!)
    second_call_timeout = mock_client.send_request.call_args_list[1].kwargs[
        "timeout_seconds"
    ]
    assert second_call_timeout == 2.5

    assert report.total_requests == 2
    assert report.interrupted is True


def test_engine_artificial_latency_clamped_to_remaining_budget() -> None:
    """Artificial latency cannot sleep longer than remaining execution budget."""
    mock_client = MagicMock(spec=ResilienceClient)
    sleep_calls: list[float] = []

    def mock_sleeper(seconds: float) -> None:
        sleep_calls.append(seconds)

    # Clock: start at 0.0, top of loop at 0.0 (budget 2.0).
    # Sleeper sleeps 2.0. Clock after sleep is 2.0 (budget 0.0).
    call_times = [0.0, 0.0, 2.0, 2.0]
    call_idx = 0

    def mock_clock() -> float:
        nonlocal call_idx
        val = call_times[min(call_idx, len(call_times) - 1)]
        call_idx += 1
        return val

    cfg = ResilienceConfig(
        target_url="http://localhost/test",
        request_count=2,
        artificial_latency_ms=5000,  # Configured 5.0s > 2.0s deadline
        total_deadline_seconds=2.0,
    )
    scenario = Scenario(name="latency_clamp_test", config=cfg)
    engine = ResilienceEngine(
        client=mock_client, sleeper=mock_sleeper, clock=mock_clock
    )

    report = engine.run_scenario(scenario)

    # Sleeper was clamped to 2.0s (never slept for 5.0s)
    assert sleep_calls == [2.0]
    # Outbound request was aborted because deadline was exhausted during sleep
    mock_client.send_request.assert_not_called()
    assert report.total_requests == 0
    assert report.interrupted is True


def test_engine_immediate_deadline_exhaustion_zero_requests() -> None:
    """Zero requests are scheduled if execution deadline is already exhausted."""
    mock_client = MagicMock(spec=ResilienceClient)
    cfg = ResilienceConfig(
        target_url="http://localhost/test",
        request_count=5,
        total_deadline_seconds=1.0,
    )
    scenario = Scenario(name="immediate_exhaustion", config=cfg)
    # Clock starts at 10.0, next check is 15.0 (elapsed 5.0 >= 1.0)
    times = [10.0, 15.0]
    idx = 0

    def mock_clock() -> float:
        nonlocal idx
        val = times[min(idx, len(times) - 1)]
        idx += 1
        return val

    engine = ResilienceEngine(client=mock_client, clock=mock_clock)
    report = engine.run_scenario(scenario)

    mock_client.send_request.assert_not_called()
    assert report.total_requests == 0
    assert report.successful_requests == 0
    assert report.failed_requests == 0
    assert report.average_latency_ms == 0.0
    assert report.p95_latency_ms == 0.0
    assert report.interrupted is True


def test_engine_external_target_partial_authorizations() -> None:
    """External target requires both flags; partial authorization is denied."""
    cfg1 = ResilienceConfig(
        target_url="https://external.example.com/api",
        allow_external=True,
        authorized_acknowledgement=False,
    )
    engine = ResilienceEngine()
    with pytest.raises(SafetyViolationError):
        engine.run_scenario(Scenario(name="partial_1", config=cfg1))

    cfg2 = ResilienceConfig(
        target_url="https://external.example.com/api",
        allow_external=False,
        authorized_acknowledgement=True,
    )
    with pytest.raises(SafetyViolationError):
        engine.run_scenario(Scenario(name="partial_2", config=cfg2))
