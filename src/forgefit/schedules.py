"""Adaptive fault scheduling models and calculation logic for ForgeFit."""

from __future__ import annotations

import math
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any


class FaultSchedule(ABC):
    """Abstract base class for resilience fault schedules.

    Schedules define how artificial latency and simulated failure probability
    evolve across sequential request iterations.
    """

    schedule_type: str

    @abstractmethod
    def get_parameters(self, iteration: int) -> tuple[int, float]:
        """Compute latency and failure probability for a given request iteration.

        Args:
            iteration: 1-based sequential request index.

        Returns:
            Tuple of (artificial_latency_ms: int, failure_probability: float).
        """

    @abstractmethod
    def to_dict(self) -> dict[str, Any]:
        """Serialize schedule configuration to a JSON-compatible dictionary."""

    @abstractmethod
    def validate(self) -> None:
        """Validate schedule parameters and boundary rules.

        Raises:
            ValueError: If numerical parameters violate boundaries or constraints.
            TypeError: If parameter types are invalid.
        """


@dataclass(slots=True)
class ConstantFaultSchedule(FaultSchedule):
    """Constant fault schedule: maintains fixed latency and failure probability.

    Attributes:
        artificial_latency_ms: Artificial delay in milliseconds (integer >= 0).
        failure_probability: Probability of simulated failure (float 0.0 to 1.0).
    """

    artificial_latency_ms: int = 0
    failure_probability: float = 0.0
    schedule_type: str = "constant"

    def __post_init__(self) -> None:
        self.validate()

    def validate(self) -> None:
        """Validate constant schedule parameters."""
        if isinstance(self.artificial_latency_ms, bool) or not isinstance(
            self.artificial_latency_ms, int
        ):
            t = type(self.artificial_latency_ms).__name__
            raise TypeError(f"artificial_latency_ms must be an integer, got {t}")
        if self.artificial_latency_ms < 0:
            raise ValueError(
                f"artificial_latency_ms must be >= 0, got {self.artificial_latency_ms}"
            )

        if isinstance(self.failure_probability, bool) or not isinstance(
            self.failure_probability, (int, float)
        ):
            t = type(self.failure_probability).__name__
            raise TypeError(f"failure_probability must be a float, got {t}")
        if math.isnan(self.failure_probability) or math.isinf(self.failure_probability):
            raise ValueError("failure_probability cannot be NaN or infinite")
        if not (0.0 <= self.failure_probability <= 1.0):
            raise ValueError(
                f"failure_probability must be between 0.0 and 1.0, "
                f"got {self.failure_probability}"
            )

    def get_parameters(self, iteration: int) -> tuple[int, float]:
        """Return invariant latency and failure probability."""
        if iteration < 1:
            raise ValueError(f"iteration must be >= 1, got {iteration}")
        return self.artificial_latency_ms, float(self.failure_probability)

    def to_dict(self) -> dict[str, Any]:
        """Serialize constant schedule to dict."""
        return {
            "schedule_type": "constant",
            "artificial_latency_ms": self.artificial_latency_ms,
            "failure_probability": round(float(self.failure_probability), 4),
        }


@dataclass(slots=True)
class StepEntry:
    """Individual threshold step in a step-based fault schedule.

    Attributes:
        threshold: 1-based iteration at which this step becomes active.
        artificial_latency_ms: Latency applied once this step is reached.
        failure_probability: Failure probability applied once this step is reached.
    """

    threshold: int
    artificial_latency_ms: int = 0
    failure_probability: float = 0.0

    def validate(self) -> None:
        """Validate step entry parameters."""
        if isinstance(self.threshold, bool) or not isinstance(self.threshold, int):
            t = type(self.threshold).__name__
            raise TypeError(f"threshold must be an integer, got {t}")
        if self.threshold < 1:
            raise ValueError(f"threshold must be >= 1, got {self.threshold}")

        if isinstance(self.artificial_latency_ms, bool) or not isinstance(
            self.artificial_latency_ms, int
        ):
            t = type(self.artificial_latency_ms).__name__
            raise TypeError(f"artificial_latency_ms must be an integer, got {t}")
        if self.artificial_latency_ms < 0:
            raise ValueError(
                f"artificial_latency_ms must be >= 0, got {self.artificial_latency_ms}"
            )

        if isinstance(self.failure_probability, bool) or not isinstance(
            self.failure_probability, (int, float)
        ):
            t = type(self.failure_probability).__name__
            raise TypeError(f"failure_probability must be a float, got {t}")
        if math.isnan(self.failure_probability) or math.isinf(self.failure_probability):
            raise ValueError("failure_probability cannot be NaN or infinite")
        if not (0.0 <= self.failure_probability <= 1.0):
            raise ValueError(
                f"failure_probability must be between 0.0 and 1.0, "
                f"got {self.failure_probability}"
            )


@dataclass(slots=True)
class StepFaultSchedule(FaultSchedule):
    """Step-based fault schedule: applies parameter changes at defined thresholds.

    Boundary Behavior:
    - For request iterations prior to the first threshold, the schedule uses the
      first step's configuration.
    - For iterations between thresholds, the highest threshold <= iteration applies.
    - Beyond the highest threshold, parameters remain clamped to the final step.

    Attributes:
        steps: List of StepEntry thresholds sorted in strictly ascending order.
    """

    steps: list[StepEntry] = field(default_factory=list)
    schedule_type: str = "step"

    def __post_init__(self) -> None:
        self.validate()

    def validate(self) -> None:
        """Validate step entries and ordering."""
        if not isinstance(self.steps, list):
            t = type(self.steps).__name__
            raise TypeError(f"steps must be a list, got {t}")
        if not self.steps:
            raise ValueError("Step fault schedule must contain at least one step entry")

        last_threshold = 0
        for idx, entry in enumerate(self.steps):
            if not isinstance(entry, StepEntry):
                t = type(entry).__name__
                raise TypeError(
                    f"All entries in 'steps' must be StepEntry instances, "
                    f"got {t} at index {idx}"
                )
            entry.validate()
            if entry.threshold <= last_threshold:
                raise ValueError(
                    f"Step thresholds must be strictly ascending: "
                    f"step {idx} ({entry.threshold}) <= previous ({last_threshold})"
                )
            last_threshold = entry.threshold

    def get_parameters(self, iteration: int) -> tuple[int, float]:
        """Return parameters corresponding to the highest active step threshold."""
        if iteration < 1:
            raise ValueError(f"iteration must be >= 1, got {iteration}")

        active_step = self.steps[0]
        for step in self.steps:
            if iteration >= step.threshold:
                active_step = step
            else:
                break

        return active_step.artificial_latency_ms, float(active_step.failure_probability)

    def to_dict(self) -> dict[str, Any]:
        """Serialize step schedule to dict."""
        return {
            "schedule_type": "step",
            "steps": [
                {
                    "threshold": s.threshold,
                    "artificial_latency_ms": s.artificial_latency_ms,
                    "failure_probability": round(float(s.failure_probability), 4),
                }
                for s in self.steps
            ],
        }


@dataclass(slots=True)
class RampedFaultSchedule(FaultSchedule):
    """Ramped fault schedule: progressively transitions latency and failure probability.

    Boundary Behavior:
    - For iterations <= start_iteration: parameters equal (start_latency_ms,
      start_failure_probability).
    - For iterations between start_iteration and start_iteration + ramp_requests - 1:
      parameters linearly interpolate from start to end values.
    - For iterations >= start_iteration + ramp_requests - 1: parameters remain clamped
      to (end_latency_ms, end_failure_probability).

    Attributes:
        start_latency_ms: Initial latency before ramping starts (integer >= 0).
        end_latency_ms: Target latency at end of ramp (integer >= 0).
        start_failure_probability: Initial failure probability (0.0 to 1.0).
        end_failure_probability: Target failure probability at end of ramp (0.0 to 1.0).
        ramp_requests: Number of iterations over which ramp occurs (integer >= 1).
        start_iteration: 1-based iteration where ramp commences (default 1).
    """

    start_latency_ms: int = 0
    end_latency_ms: int = 0
    start_failure_probability: float = 0.0
    end_failure_probability: float = 0.0
    ramp_requests: int = 10
    start_iteration: int = 1
    schedule_type: str = "ramped"

    def __post_init__(self) -> None:
        self.validate()

    def validate(self) -> None:
        """Validate ramped schedule parameters."""
        for name, val in (
            ("start_latency_ms", self.start_latency_ms),
            ("end_latency_ms", self.end_latency_ms),
        ):
            if isinstance(val, bool) or not isinstance(val, int):
                t = type(val).__name__
                raise TypeError(f"{name} must be an integer, got {t}")
            if val < 0:
                raise ValueError(f"{name} must be >= 0, got {val}")

        for name, val in (
            ("start_failure_probability", self.start_failure_probability),
            ("end_failure_probability", self.end_failure_probability),
        ):
            if isinstance(val, bool) or not isinstance(val, (int, float)):
                t = type(val).__name__
                raise TypeError(f"{name} must be a float, got {t}")
            if math.isnan(val) or math.isinf(val):
                raise ValueError(f"{name} cannot be NaN or infinite")
            if not (0.0 <= val <= 1.0):
                raise ValueError(f"{name} must be between 0.0 and 1.0, got {val}")

        for name, val in (
            ("ramp_requests", self.ramp_requests),
            ("start_iteration", self.start_iteration),
        ):
            if isinstance(val, bool) or not isinstance(val, int):
                t = type(val).__name__
                raise TypeError(f"{name} must be an integer, got {t}")
            if val < 1:
                raise ValueError(f"{name} must be >= 1, got {val}")

    def get_parameters(self, iteration: int) -> tuple[int, float]:
        """Compute linearly interpolated latency and failure probability."""
        if iteration < 1:
            raise ValueError(f"iteration must be >= 1, got {iteration}")

        if iteration <= self.start_iteration:
            return self.start_latency_ms, float(self.start_failure_probability)

        ramp_end = self.start_iteration + self.ramp_requests - 1
        if iteration >= ramp_end or self.ramp_requests == 1:
            return self.end_latency_ms, float(self.end_failure_probability)

        # Linear interpolation fraction: 0.0 <= progress <= 1.0
        progress = (iteration - self.start_iteration) / float(self.ramp_requests - 1)
        cur_latency = self.start_latency_ms + progress * (
            self.end_latency_ms - self.start_latency_ms
        )
        cur_prob = self.start_failure_probability + progress * (
            self.end_failure_probability - self.start_failure_probability
        )

        return int(round(cur_latency)), round(float(cur_prob), 4)

    def to_dict(self) -> dict[str, Any]:
        """Serialize ramped schedule to dict."""
        return {
            "schedule_type": "ramped",
            "start_latency_ms": self.start_latency_ms,
            "end_latency_ms": self.end_latency_ms,
            "start_failure_probability": round(
                float(self.start_failure_probability), 4
            ),
            "end_failure_probability": round(float(self.end_failure_probability), 4),
            "ramp_requests": self.ramp_requests,
            "start_iteration": self.start_iteration,
        }


def create_fault_schedule(data: dict[str, Any]) -> FaultSchedule:
    """Factory to construct and validate a FaultSchedule from a dictionary.

    Args:
        data: Dictionary containing schedule configuration keys.

    Returns:
        Concrete FaultSchedule instance.

    Raises:
        TypeError: If data is not a dictionary.
        ValueError: If schedule_type is missing or unsupported.
    """
    if not isinstance(data, dict):
        t = type(data).__name__
        raise TypeError(f"Schedule data must be a dictionary, got {t}")

    schedule_type = data.get("schedule_type")
    if not schedule_type or not isinstance(schedule_type, str):
        raise ValueError(
            "Fault schedule must specify a non-empty string 'schedule_type'"
        )

    st = schedule_type.strip().lower()
    if st == "constant":
        return ConstantFaultSchedule(
            artificial_latency_ms=data.get("artificial_latency_ms", 0),
            failure_probability=data.get("failure_probability", 0.0),
        )

    if st == "step":
        raw_steps = data.get("steps")
        if not isinstance(raw_steps, list):
            raise TypeError("Step fault schedule must contain a 'steps' list")
        steps: list[StepEntry] = []
        for idx, s in enumerate(raw_steps):
            if not isinstance(s, dict):
                t = type(s).__name__
                raise TypeError(
                    f"Step entry at index {idx} must be a dictionary, got {t}"
                )
            if "threshold" not in s:
                raise ValueError(
                    f"Step entry at index {idx} missing required 'threshold'"
                )
            steps.append(
                StepEntry(
                    threshold=s["threshold"],
                    artificial_latency_ms=s.get("artificial_latency_ms", 0),
                    failure_probability=s.get("failure_probability", 0.0),
                )
            )
        return StepFaultSchedule(steps=steps)

    if st == "ramped":
        return RampedFaultSchedule(
            start_latency_ms=data.get("start_latency_ms", 0),
            end_latency_ms=data.get("end_latency_ms", 0),
            start_failure_probability=data.get("start_failure_probability", 0.0),
            end_failure_probability=data.get("end_failure_probability", 0.0),
            ramp_requests=data.get("ramp_requests", 10),
            start_iteration=data.get("start_iteration", 1),
        )

    raise ValueError(
        f"Unsupported schedule_type '{schedule_type}'. "
        "Supported types are: 'constant', 'step', 'ramped'."
    )
