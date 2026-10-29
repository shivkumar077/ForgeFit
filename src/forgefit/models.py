"""Domain models for ForgeFit resilience testing scenarios and outcomes."""

from __future__ import annotations

import json
import math
from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from forgefit.config import ResilienceConfig
from forgefit.schedules import FaultSchedule, create_fault_schedule


def _serialize_datetime(dt: datetime) -> str:
    """Format datetime as ISO-8601 string in UTC."""
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=UTC)
    return dt.astimezone(UTC).isoformat()


@dataclass(slots=True)
class Scenario:
    """A defined API resilience testing scenario.

    Attributes:
        name: Short identifier for the scenario.
        config: Resilience configuration parameters for this scenario.
        description: Human-readable explanation of the test intent.
        tags: Optional list of categorization tags.
    """

    name: str
    config: ResilienceConfig
    description: str = ""
    tags: list[str] = field(default_factory=list)
    schedule: FaultSchedule | None = None

    def to_dict(self) -> dict[str, Any]:
        """Serialize scenario to a clean JSON-compatible dictionary."""
        result: dict[str, Any] = {
            "name": self.name,
            "description": self.description,
            "tags": list(self.tags),
            "config": self.config.to_dict(),
        }
        if self.schedule is not None:
            result["schedule"] = self.schedule.to_dict()
        return result

    @classmethod
    def from_dict(cls, data: Any) -> Scenario:
        """Construct a Scenario from a dictionary, with strict validation.

        Args:
            data: Dictionary containing scenario fields ('name', 'config', etc.)
                or a legacy flat ResilienceConfig dictionary.

        Returns:
            Validated Scenario instance.

        Raises:
            TypeError: If input or field types are invalid.
            ValueError: If required fields are missing or values are out of bounds.
        """
        if not isinstance(data, dict):
            raise TypeError(
                f"Scenario data must be a dictionary, got {type(data).__name__}"
            )

        # Backward compatibility: support legacy direct configuration dictionaries
        if "target_url" in data and "config" not in data:
            config = ResilienceConfig.from_dict(data)
            legacy_sched = None
            if "schedule" in data and data["schedule"] is not None:
                if isinstance(data["schedule"], FaultSchedule):
                    legacy_sched = data["schedule"]
                elif isinstance(data["schedule"], dict):
                    legacy_sched = create_fault_schedule(data["schedule"])
                else:
                    t = type(data["schedule"]).__name__
                    raise TypeError(
                        f"Scenario 'schedule' must be a dict or FaultSchedule, got {t}"
                    )
            return cls(name="default", config=config, schedule=legacy_sched)

        if "name" not in data:
            raise ValueError("Scenario dictionary must contain a 'name' field.")
        name = data["name"]
        if isinstance(name, bool) or not isinstance(name, str):
            raise TypeError(
                f"Scenario 'name' must be a string, got {type(name).__name__}"
            )
        if not name.strip():
            raise ValueError("Scenario 'name' cannot be empty or whitespace.")

        description = data.get("description", "")
        if not isinstance(description, str):
            raise TypeError(
                f"Scenario 'description' must be a string, "
                f"got {type(description).__name__}"
            )

        tags_raw = data.get("tags", [])
        if not isinstance(tags_raw, list):
            raise TypeError(
                f"Scenario 'tags' must be a list of strings, "
                f"got {type(tags_raw).__name__}"
            )
        tags: list[str] = []
        for tag in tags_raw:
            if not isinstance(tag, str):
                raise TypeError(
                    f"Scenario tag item must be a string, got {type(tag).__name__}"
                )
            tags.append(tag)

        if "config" not in data:
            raise ValueError("Scenario dictionary must contain a 'config' mapping.")
        config_data = data["config"]
        if isinstance(config_data, ResilienceConfig):
            config = config_data
        elif isinstance(config_data, dict):
            config = ResilienceConfig.from_dict(config_data)
        else:
            raise TypeError(
                f"Scenario 'config' must be a dict or ResilienceConfig, "
                f"got {type(config_data).__name__}"
            )

        # Check for optional fault schedule
        schedule_raw = data.get("schedule")
        if schedule_raw is None and isinstance(data.get("config"), dict):
            schedule_raw = data["config"].get("schedule")

        schedule: FaultSchedule | None = None
        if schedule_raw is not None:
            if isinstance(schedule_raw, FaultSchedule):
                schedule = schedule_raw
            elif isinstance(schedule_raw, dict):
                schedule = create_fault_schedule(schedule_raw)
            else:
                t = type(schedule_raw).__name__
                raise TypeError(
                    f"Scenario 'schedule' must be a dict or FaultSchedule, got {t}"
                )

        return cls(
            name=name.strip(),
            config=config,
            description=description,
            tags=tags,
            schedule=schedule,
        )

    @classmethod
    def from_json_file(cls, file_path: str | Path) -> Scenario:
        """Load and validate a Scenario from a JSON file.

        Args:
            file_path: Path to scenario JSON file.

        Returns:
            Validated Scenario instance.

        Raises:
            FileNotFoundError: If the specified file does not exist.
            ValueError: If file content is malformed JSON or has invalid fields.
            TypeError: If JSON root is not a dictionary.
        """
        path = Path(file_path)
        if not path.is_file():
            raise FileNotFoundError(f"Scenario configuration file not found: {path}")

        try:
            with open(path, encoding="utf-8") as f:
                data = json.load(f)
        except json.JSONDecodeError as err:
            raise ValueError(
                f"Malformed JSON in scenario file '{path}': {err}"
            ) from err

        scenario = cls.from_dict(data)
        # For legacy flat configs without explicit name, default name to file stem
        if "name" not in data and scenario.name == "default":
            scenario.name = path.stem
        return scenario

    def to_json_file(self, file_path: str | Path) -> None:
        """Serialize scenario to a JSON file.

        Args:
            file_path: Path where scenario JSON will be written.
        """
        path = Path(file_path)
        path.parent.mkdir(parents=True, exist_ok=True)
        with open(path, "w", encoding="utf-8") as f:
            json.dump(self.to_dict(), f, indent=2)
            f.write("\n")


@dataclass(slots=True)
class RequestOutcome:
    """The result of an individual request evaluated under resilience conditions.

    Attributes:
        iteration: Sequential 1-based index of this request iteration.
        target_url: The URL targeted by this request.
        status_code: HTTP status code, or None if timed out / failed to connect.
        latency_ms: Measured or simulated response latency in milliseconds.
        success: Whether the outcome met expected success criteria (e.g. 2xx).
        simulated_fault: Whether a simulated fault was injected for this request.
        failure_category: Categorization of failure when unsuccessful:
            'simulated_failure', 'http_error', 'timeout', or 'connection_error'.
        error_message: Optional error message or exception description.
        start_time: Timestamp when request processing started (UTC).
        timestamp: Timestamp when request processing completed (UTC).
    """

    iteration: int
    target_url: str
    status_code: int | None
    latency_ms: float
    success: bool
    simulated_fault: bool = False
    failure_category: str | None = None
    error_message: str | None = None
    start_time: datetime | None = None
    timestamp: datetime = field(default_factory=lambda: datetime.now(UTC))

    def to_dict(self) -> dict[str, Any]:
        """Serialize outcome to a clean JSON-compatible dictionary."""
        return {
            "iteration": self.iteration,
            "target_url": self.target_url,
            "status_code": self.status_code,
            "latency_ms": round(float(self.latency_ms), 2),
            "success": self.success,
            "simulated_fault": self.simulated_fault,
            "failure_category": self.failure_category,
            "error_message": self.error_message,
            "start_time": (
                _serialize_datetime(self.start_time) if self.start_time else None
            ),
            "timestamp": _serialize_datetime(self.timestamp),
        }


@dataclass(slots=True)
class ResilienceReport:
    """Aggregated outcome report of a completed resilience test run.

    Attributes:
        scenario_name: Identifier of the executed scenario.
        total_requests: Total number of requests executed.
        successful_requests: Number of successful requests (2xx, no fault).
        failed_requests: Number of failed requests (all failure categories).
        simulated_fault_count: Requests where local fault injection occurred.
        http_error_count: Requests that received non-2xx HTTP responses.
        timeout_count: Requests that timed out before receiving a response.
        connection_error_count: Requests that failed to establish connection.
        average_latency_ms: Mean response latency across all attempted requests.
        p95_latency_ms: 95th percentile latency (nearest-rank) in milliseconds.
        total_duration_ms: Total elapsed execution time in milliseconds.
        start_time: Run start timestamp in UTC.
        end_time: Run completion timestamp in UTC.
        interrupted: Whether execution stopped before completing all iterations.
        outcomes: List of individual request outcomes.
        metadata: Optional key-value annotations for reporting.
    """

    scenario_name: str
    total_requests: int
    successful_requests: int
    failed_requests: int
    simulated_fault_count: int
    average_latency_ms: float
    p95_latency_ms: float
    start_time: datetime
    end_time: datetime
    http_error_count: int = 0
    timeout_count: int = 0
    connection_error_count: int = 0
    total_duration_ms: float = 0.0
    interrupted: bool = False
    outcomes: list[RequestOutcome] = field(default_factory=list)
    metadata: dict[str, Any] = field(default_factory=dict)

    @classmethod
    def from_outcomes(
        cls,
        scenario_name: str,
        outcomes: list[RequestOutcome],
        start_time: datetime,
        end_time: datetime,
        total_duration_ms: float | None = None,
        interrupted: bool = False,
        metadata: dict[str, Any] | None = None,
    ) -> ResilienceReport:
        """Construct an aggregated ResilienceReport directly from recorded outcomes.

        Latency metrics calculation policy:
        - All recorded outcomes (successful, HTTP error, timeout, simulated) are
          included in latency calculations because each represents an executed
          iteration with measured duration.
        - p95 latency is computed using the nearest-rank method over sorted
          latencies: index = ceil(0.95 * N) - 1. If outcomes is empty, p95 is 0.0.
        """
        total = len(outcomes)
        successful = sum(1 for o in outcomes if o.success)
        failed = sum(1 for o in outcomes if not o.success)
        simulated = sum(1 for o in outcomes if o.simulated_fault)
        http_errors = sum(1 for o in outcomes if o.failure_category == "http_error")
        timeouts = sum(1 for o in outcomes if o.failure_category == "timeout")
        conn_errors = sum(
            1 for o in outcomes if o.failure_category == "connection_error"
        )

        latencies = sorted(o.latency_ms for o in outcomes)
        if latencies:
            avg_lat = round(sum(latencies) / len(latencies), 2)
            p95_idx = max(
                0, min(math.ceil(0.95 * len(latencies)) - 1, len(latencies) - 1)
            )
            p95_lat = round(float(latencies[p95_idx]), 2)
        else:
            avg_lat = 0.0
            p95_lat = 0.0

        if total_duration_ms is None:
            diff = (end_time - start_time).total_seconds() * 1000.0
            calc_duration = round(max(0.0, diff), 2)
        else:
            calc_duration = round(float(total_duration_ms), 2)

        return cls(
            scenario_name=scenario_name,
            total_requests=total,
            successful_requests=successful,
            failed_requests=failed,
            simulated_fault_count=simulated,
            http_error_count=http_errors,
            timeout_count=timeouts,
            connection_error_count=conn_errors,
            average_latency_ms=avg_lat,
            p95_latency_ms=p95_lat,
            total_duration_ms=calc_duration,
            start_time=start_time,
            end_time=end_time,
            interrupted=interrupted,
            outcomes=list(outcomes),
            metadata=dict(metadata or {}),
        )

    def to_dict(self) -> dict[str, Any]:
        """Serialize report and outcomes to a JSON-compatible dictionary."""
        return {
            "scenario_name": self.scenario_name,
            "total_requests": self.total_requests,
            "successful_requests": self.successful_requests,
            "failed_requests": self.failed_requests,
            "simulated_fault_count": self.simulated_fault_count,
            "http_error_count": self.http_error_count,
            "timeout_count": self.timeout_count,
            "connection_error_count": self.connection_error_count,
            "average_latency_ms": round(float(self.average_latency_ms), 2),
            "p95_latency_ms": round(float(self.p95_latency_ms), 2),
            "total_duration_ms": round(float(self.total_duration_ms), 2),
            "interrupted": self.interrupted,
            "start_time": _serialize_datetime(self.start_time),
            "end_time": _serialize_datetime(self.end_time),
            "outcomes": [outcome.to_dict() for outcome in self.outcomes],
            "metadata": dict(self.metadata),
        }
