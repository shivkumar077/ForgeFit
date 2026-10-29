"""Resilience execution engine for ForgeFit."""

from __future__ import annotations

import random
import time
from collections.abc import Callable
from datetime import UTC, datetime
from typing import Any

from forgefit.client import ResilienceClient
from forgefit.models import RequestOutcome, ResilienceReport, Scenario


class SafetyViolationError(PermissionError):
    """Raised when execution parameters violate mandatory safety constraints."""


class ResilienceEngine:
    """Orchestrates controlled, bounded resilience test execution.

    Enforces:
    - Default local loopback targets. External targets require explicit opt-in
      and authorization acknowledgement.
    - Strict overall execution deadlines.
    - Monotonic duration timing and timezone-aware UTC timestamps.
    - Local-only simulated failures without sending requests to the remote target.
    - Injectable sleeper and clock for deterministic, fast testing.
    - Seeded pseudo-random generator for reproducible fault simulation.
    """

    def __init__(
        self,
        client: ResilienceClient | None = None,
        sleeper: Callable[[float], None] = time.sleep,
        clock: Callable[[], float] = time.monotonic,
    ) -> None:
        self.client = client or ResilienceClient()
        self.sleeper = sleeper
        self.clock = clock

    def run_scenario(
        self,
        scenario: Scenario,
        extra_metadata: dict[str, Any] | None = None,
        progress_callback: Callable[[int, int, RequestOutcome], None] | None = None,
    ) -> ResilienceReport:
        """Execute a Scenario according to its configuration.

        Args:
            scenario: The Scenario containing ResilienceConfig and metadata.
            extra_metadata: Optional runtime metadata to attach to the report.

        Returns:
            Aggregated ResilienceReport.

        Raises:
            SafetyViolationError: If safety boundaries (e.g. non-loopback without
                acknowledgement) are violated.
        """
        config = scenario.config
        config.validate()

        # Enforce execution safety boundary: non-loopback requires explicit opt-in
        if not config.is_loopback_target:
            if not config.allow_external or not config.authorized_acknowledgement:
                msg = (
                    "Execution against external (non-loopback) targets requires "
                    "both allow_external=True and authorized_acknowledgement=True."
                )
                raise SafetyViolationError(msg)

        # Initialize pseudo-random generator for reproducible fault simulation
        rng = random.Random(config.seed)

        outcomes: list[RequestOutcome] = []
        start_wall = datetime.now(UTC)
        start_mono = self.clock()
        interrupted = False

        for i in range(1, config.request_count + 1):
            now_mono = self.clock()
            elapsed_run = now_mono - start_mono
            remaining_budget = config.total_deadline_seconds - elapsed_run

            # Stop scheduling requests once total execution deadline expires
            if remaining_budget <= 0.0:
                interrupted = True
                break

            iter_start_wall = datetime.now(UTC)

            # Determine iteration parameters from fault schedule or static config
            if scenario.schedule is not None:
                cur_latency_ms, cur_failure_prob = scenario.schedule.get_parameters(i)
            else:
                cur_latency_ms = config.artificial_latency_ms
                cur_failure_prob = config.failure_probability

            # Determine whether to simulate a failure locally
            simulated = cur_failure_prob > 0.0 and rng.random() < cur_failure_prob

            if simulated:
                # Locally simulated failure: DO NOT send outbound request!
                # Ensure artificial latency cannot deliberately consume more time
                # than the remaining execution budget.
                actual_latency_ms = 0.0
                if cur_latency_ms > 0:
                    planned_sleep = cur_latency_ms / 1000.0
                    sleep_duration = min(planned_sleep, max(0.0, remaining_budget))
                    if sleep_duration > 0.0:
                        self.sleeper(sleep_duration)
                    actual_latency_ms = round(sleep_duration * 1000.0, 2)

                iter_end_wall = datetime.now(UTC)
                outcome = RequestOutcome(
                    iteration=i,
                    target_url=config.target_url,
                    status_code=None,
                    latency_ms=actual_latency_ms,
                    success=False,
                    simulated_fault=True,
                    failure_category="simulated_failure",
                    error_message=(
                        "Simulated failure injected locally (no outbound request made)"
                    ),
                    start_time=iter_start_wall,
                    timestamp=iter_end_wall,
                )
                outcomes.append(outcome)
            else:
                # Live execution: inject configured artificial latency bounded
                # strictly by the remaining execution budget.
                added_latency_ms = 0.0
                if cur_latency_ms > 0:
                    planned_sleep = cur_latency_ms / 1000.0
                    sleep_duration = min(planned_sleep, max(0.0, remaining_budget))
                    if sleep_duration > 0.0:
                        self.sleeper(sleep_duration)
                    added_latency_ms = round(sleep_duration * 1000.0, 2)

                    # Re-calculate remaining budget after sleeping
                    now_after_sleep = self.clock()
                    remaining_budget = config.total_deadline_seconds - (
                        now_after_sleep - start_mono
                    )

                # If budget was exhausted during artificial latency, stop scheduling
                if remaining_budget <= 0.0:
                    interrupted = True
                    break

                # Ensure effective HTTP timeout cannot exceed remaining
                # execution budget.
                # Synchronous transport limitation note: Clamping effective_timeout
                # enforces the tightest synchronous boundary possible; operations like
                # OS-level DNS resolution or thread preemption remain best-effort.
                effective_timeout = min(config.timeout_seconds, remaining_budget)
                if effective_timeout < 0.001:
                    interrupted = True
                    break

                resp = self.client.send_request(
                    target_url=config.target_url,
                    timeout_seconds=effective_timeout,
                )

                outcome = RequestOutcome(
                    iteration=i,
                    target_url=config.target_url,
                    status_code=resp.status_code,
                    latency_ms=round(resp.latency_ms + added_latency_ms, 2),
                    success=resp.success,
                    simulated_fault=False,
                    failure_category=resp.failure_category,
                    error_message=resp.error_message,
                    start_time=resp.start_time,
                    timestamp=resp.end_time,
                )
                outcomes.append(outcome)

            if progress_callback is not None:
                try:
                    progress_callback(i, config.request_count, outcome)
                except Exception:
                    pass

        end_wall = datetime.now(UTC)
        end_mono = self.clock()
        total_duration_ms = round((end_mono - start_mono) * 1000.0, 2)

        meta = dict(scenario.tags and {"tags": scenario.tags} or {})
        if scenario.schedule is not None:
            meta["schedule"] = scenario.schedule.to_dict()
        if extra_metadata:
            meta.update(extra_metadata)

        return ResilienceReport.from_outcomes(
            scenario_name=scenario.name,
            outcomes=outcomes,
            start_time=start_wall,
            end_time=end_wall,
            total_duration_ms=total_duration_ms,
            interrupted=interrupted,
            metadata=meta,
        )
