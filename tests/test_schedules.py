"""Focused tests for adaptive fault schedules and deterministic seeded execution."""

from __future__ import annotations

import pytest

from forgefit.client import ClientResponse, ResilienceClient
from forgefit.config import ResilienceConfig
from forgefit.engine import ResilienceEngine
from forgefit.models import Scenario
from forgefit.schedules import (
    ConstantFaultSchedule,
    RampedFaultSchedule,
    StepEntry,
    StepFaultSchedule,
    create_fault_schedule,
)


class MockConstantClient(ResilienceClient):
    """Mock client returning deterministic 200 responses without network calls."""

    def send_request(
        self,
        target_url: str,
        timeout_seconds: float,
    ) -> ClientResponse:
        from datetime import UTC, datetime

        now = datetime.now(UTC)
        return ClientResponse(
            status_code=200,
            latency_ms=10.0,
            success=True,
            failure_category=None,
            error_message=None,
            start_time=now,
            end_time=now,
        )


def test_constant_schedule_progression_and_validation() -> None:
    """Constant schedule validates inputs and returns invariant values."""
    sched = ConstantFaultSchedule(artificial_latency_ms=50, failure_probability=0.2)
    assert sched.get_parameters(1) == (50, 0.2)
    assert sched.get_parameters(100) == (50, 0.2)
    assert sched.to_dict()["schedule_type"] == "constant"

    # Validation errors
    with pytest.raises(ValueError, match="artificial_latency_ms must be >= 0"):
        ConstantFaultSchedule(artificial_latency_ms=-1)
    with pytest.raises(ValueError, match="failure_probability must be between"):
        ConstantFaultSchedule(failure_probability=1.5)


def test_step_schedule_progression_and_boundaries() -> None:
    """Step schedule applies parameter changes at thresholds and clamps beyond max."""
    steps = [
        StepEntry(threshold=1, artificial_latency_ms=10, failure_probability=0.0),
        StepEntry(threshold=5, artificial_latency_ms=100, failure_probability=0.5),
        StepEntry(threshold=10, artificial_latency_ms=250, failure_probability=1.0),
    ]
    sched = StepFaultSchedule(steps=steps)

    # Iteration 1-4: Step 1
    assert sched.get_parameters(1) == (10, 0.0)
    assert sched.get_parameters(4) == (10, 0.0)

    # Iteration 5-9: Step 2
    assert sched.get_parameters(5) == (100, 0.5)
    assert sched.get_parameters(9) == (100, 0.5)

    # Iteration 10+: Step 3 (clamped)
    assert sched.get_parameters(10) == (250, 1.0)
    assert sched.get_parameters(50) == (250, 1.0)


def test_step_schedule_validation() -> None:
    """Step schedule rejects non-ascending thresholds and empty steps."""
    with pytest.raises(ValueError, match="must contain at least one step entry"):
        StepFaultSchedule(steps=[])

    with pytest.raises(ValueError, match="must be strictly ascending"):
        StepFaultSchedule(
            steps=[
                StepEntry(threshold=5, artificial_latency_ms=10),
                StepEntry(threshold=3, artificial_latency_ms=20),
            ]
        )


def test_ramped_schedule_progression_and_interpolation() -> None:
    """Ramped schedule linearly interpolates between start and end values."""
    sched = RampedFaultSchedule(
        start_latency_ms=0,
        end_latency_ms=100,
        start_failure_probability=0.0,
        end_failure_probability=1.0,
        ramp_requests=11,  # 11 steps: index 1 to 11
        start_iteration=1,
    )

    # Start iteration
    assert sched.get_parameters(1) == (0, 0.0)

    # Midpoint (iteration 6 out of 11: 5/10 = 0.5 progress)
    lat, prob = sched.get_parameters(6)
    assert lat == 50
    assert prob == 0.5

    # End iteration and beyond (clamped)
    assert sched.get_parameters(11) == (100, 1.0)
    assert sched.get_parameters(20) == (100, 1.0)


def test_create_fault_schedule_factory() -> None:
    """Factory correctly parses and constructs schedules from dict."""
    const_s = create_fault_schedule(
        {"schedule_type": "constant", "artificial_latency_ms": 30}
    )
    assert isinstance(const_s, ConstantFaultSchedule)
    assert const_s.artificial_latency_ms == 30

    ramp_s = create_fault_schedule(
        {
            "schedule_type": "ramped",
            "start_latency_ms": 10,
            "end_latency_ms": 50,
            "ramp_requests": 5,
        }
    )
    assert isinstance(ramp_s, RampedFaultSchedule)
    assert ramp_s.end_latency_ms == 50

    with pytest.raises(ValueError, match="Unsupported schedule_type"):
        create_fault_schedule({"schedule_type": "quantum"})


def test_schedule_deterministic_seeded_behavior() -> None:
    """Two identical runs with the same seed produce identical fault decisions."""
    sched = RampedFaultSchedule(
        start_latency_ms=0,
        end_latency_ms=10,
        start_failure_probability=0.1,
        end_failure_probability=0.8,
        ramp_requests=10,
    )
    config = ResilienceConfig(
        target_url="http://127.0.0.1:8080/test",
        request_count=10,
        seed=12345,
    )
    scenario1 = Scenario(name="Seeded Run 1", config=config, schedule=sched)
    scenario2 = Scenario(name="Seeded Run 2", config=config, schedule=sched)

    engine1 = ResilienceEngine(
        client=MockConstantClient(), sleeper=lambda _: None, clock=lambda: 0.0
    )
    engine2 = ResilienceEngine(
        client=MockConstantClient(), sleeper=lambda _: None, clock=lambda: 0.0
    )

    report1 = engine1.run_scenario(scenario1)
    report2 = engine2.run_scenario(scenario2)

    assert report1.total_requests == report2.total_requests
    assert report1.successful_requests == report2.successful_requests
    assert report1.simulated_fault_count == report2.simulated_fault_count
    # Check each individual outcome match
    for o1, o2 in zip(report1.outcomes, report2.outcomes, strict=True):
        assert o1.iteration == o2.iteration
        assert o1.simulated_fault == o2.simulated_fault
        assert o1.success == o2.success
