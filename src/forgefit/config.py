"""Configuration model and validation for ForgeFit resilience scenarios."""

from __future__ import annotations

import ipaddress
import json
import math
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any
from urllib.parse import urlsplit


def is_loopback_host(hostname: str | None) -> bool:
    """Determine whether a hostname resolves strictly to a local loopback target."""
    if not hostname:
        return False

    cleaned = hostname.strip().lower()
    if cleaned in ("localhost", "127.0.0.1", "::1", "[::1]"):
        return True

    # Strip IPv6 square brackets if present
    if cleaned.startswith("[") and cleaned.endswith("]"):
        cleaned = cleaned[1:-1]

    try:
        ip = ipaddress.ip_address(cleaned)
        return ip.is_loopback
    except ValueError:
        return False


@dataclass(slots=True)
class ResilienceConfig:
    """Validated configuration for API resilience testing scenarios.

    Attributes:
        target_url: Absolute HTTP or HTTPS URL of the target API.
        timeout_seconds: Maximum per-request timeout in seconds (must be > 0).
        request_count: Total requests/iterations to execute (integer >= 1).
        artificial_latency_ms: Artificial delay in ms to inject (integer >= 0).
        failure_probability: Probability (0.0 to 1.0) of simulating a failure.
        total_deadline_seconds: Total wall-clock deadline for run (must be > 0).
        allow_external: Must be True to execute requests against non-loopback hosts.
        authorized_acknowledgement: Explicit acknowledgement that operator is
            authorized to target non-loopback hosts.
        seed: Optional integer seed for reproducible pseudo-random fault decisions.
    """

    target_url: str
    timeout_seconds: float = 5.0
    request_count: int = 10
    artificial_latency_ms: int = 0
    failure_probability: float = 0.0
    total_deadline_seconds: float = 30.0
    allow_external: bool = False
    authorized_acknowledgement: bool = False
    seed: int | None = None

    def __post_init__(self) -> None:
        """Validate configuration parameters immediately upon initialization."""
        self.validate()

    @property
    def is_loopback_target(self) -> bool:
        """Check whether target_url points to a local loopback address."""
        parsed = urlsplit(self.target_url)
        return is_loopback_host(parsed.hostname)

    def validate(self) -> None:
        """Validate all configuration attributes against strict constraints.

        Raises:
            TypeError: If an attribute has an invalid type (including booleans
                passed for numeric values).
            ValueError: If an attribute value fails validation checks.
        """
        # 1. Target URL validation
        if not isinstance(self.target_url, str):
            raise TypeError(
                f"target_url must be a string, got {type(self.target_url).__name__}"
            )

        trimmed_url = self.target_url.strip()
        if not trimmed_url:
            raise ValueError("target_url cannot be empty")

        parsed = urlsplit(trimmed_url)
        if parsed.scheme.lower() not in ("http", "https"):
            raise ValueError(
                f"target_url must have 'http' or 'https' scheme, got '{parsed.scheme}'"
            )

        if not parsed.netloc:
            raise ValueError("target_url must contain a valid network location (host)")

        # 2. Timeout seconds validation
        # Python bool is an int subclass; reject booleans explicitly.
        if isinstance(self.timeout_seconds, bool) or not isinstance(
            self.timeout_seconds, (int, float)
        ):
            t_name = type(self.timeout_seconds).__name__
            raise TypeError(f"timeout_seconds must be a finite number, got {t_name}")

        if not math.isfinite(self.timeout_seconds):
            raise ValueError(
                "timeout_seconds must be a finite number, cannot be NaN or infinity"
            )

        if self.timeout_seconds <= 0:
            msg = (
                f"timeout_seconds must be strictly greater than 0, "
                f"got {self.timeout_seconds}"
            )
            raise ValueError(msg)

        # 3. Request count validation
        if isinstance(self.request_count, bool) or not isinstance(
            self.request_count, int
        ):
            c_name = type(self.request_count).__name__
            raise TypeError(f"request_count must be an integer, got {c_name}")

        if self.request_count < 1:
            raise ValueError(
                f"request_count must be at least 1, got {self.request_count}"
            )

        # 4. Artificial latency validation
        if isinstance(self.artificial_latency_ms, bool) or not isinstance(
            self.artificial_latency_ms, int
        ):
            l_name = type(self.artificial_latency_ms).__name__
            msg = f"artificial_latency_ms must be an integer milliseconds, got {l_name}"
            raise TypeError(msg)

        if self.artificial_latency_ms < 0:
            msg = (
                f"artificial_latency_ms must be non-negative (>= 0), "
                f"got {self.artificial_latency_ms}"
            )
            raise ValueError(msg)

        # 5. Failure probability validation
        if isinstance(self.failure_probability, bool) or not isinstance(
            self.failure_probability, (int, float)
        ):
            p_name = type(self.failure_probability).__name__
            msg = (
                f"failure_probability must be a finite number in range [0.0, 1.0], "
                f"got {p_name}"
            )
            raise TypeError(msg)

        if not math.isfinite(self.failure_probability):
            raise ValueError(
                "failure_probability must be finite, cannot be NaN or infinity"
            )

        if not (0.0 <= float(self.failure_probability) <= 1.0):
            msg = (
                f"failure_probability must be between 0.0 and 1.0 inclusive, "
                f"got {self.failure_probability}"
            )
            raise ValueError(msg)

        # 6. Total deadline validation
        if isinstance(self.total_deadline_seconds, bool) or not isinstance(
            self.total_deadline_seconds, (int, float)
        ):
            d_name = type(self.total_deadline_seconds).__name__
            msg = f"total_deadline_seconds must be a finite number, got {d_name}"
            raise TypeError(msg)

        if not math.isfinite(self.total_deadline_seconds):
            raise ValueError(
                "total_deadline_seconds must be a finite number, "
                "cannot be NaN or infinity"
            )

        if self.total_deadline_seconds <= 0:
            msg = (
                f"total_deadline_seconds must be strictly greater than 0, "
                f"got {self.total_deadline_seconds}"
            )
            raise ValueError(msg)

        # 7. Safety flags validation
        if not isinstance(self.allow_external, bool):
            a_name = type(self.allow_external).__name__
            raise TypeError(f"allow_external must be a boolean, got {a_name}")

        if not isinstance(self.authorized_acknowledgement, bool):
            k_name = type(self.authorized_acknowledgement).__name__
            raise TypeError(
                f"authorized_acknowledgement must be a boolean, got {k_name}"
            )

        # 8. Seed validation
        if self.seed is not None:
            if isinstance(self.seed, bool) or not isinstance(self.seed, int):
                s_name = type(self.seed).__name__
                raise TypeError(f"seed must be an integer, got {s_name}")

    def to_dict(self) -> dict[str, Any]:
        """Convert configuration to a clean dictionary of JSON primitives."""
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> ResilienceConfig:
        """Create a ResilienceConfig instance from a dictionary.

        Args:
            data: Dictionary containing configuration keys.

        Returns:
            Validated ResilienceConfig instance.

        Raises:
            TypeError: If data is not a dict.
            ValueError: If missing required fields or containing invalid values.
        """
        if not isinstance(data, dict):
            t_name = type(data).__name__
            raise TypeError(f"Configuration data must be a dictionary, got {t_name}")

        if "target_url" not in data:
            raise ValueError("Configuration missing required field: 'target_url'")

        known_fields = {
            "target_url",
            "timeout_seconds",
            "request_count",
            "artificial_latency_ms",
            "failure_probability",
            "total_deadline_seconds",
            "allow_external",
            "authorized_acknowledgement",
            "seed",
        }

        kwargs: dict[str, Any] = {}
        for key in known_fields:
            if key in data:
                kwargs[key] = data[key]

        return cls(**kwargs)

    @classmethod
    def from_json_file(cls, path: str | Path) -> ResilienceConfig:
        """Load and validate configuration from a JSON file.

        Args:
            path: Path to the JSON configuration file.

        Returns:
            Validated ResilienceConfig instance.

        Raises:
            ValueError: If file cannot be read, has invalid JSON, or fails validation.
        """
        file_path = Path(path)
        if not file_path.is_file():
            raise ValueError(f"Configuration file not found: {file_path}")

        try:
            content = file_path.read_text(encoding="utf-8")
        except OSError as err:
            raise ValueError(f"Failed to read configuration file: {err}") from err

        try:
            parsed = json.loads(content)
        except json.JSONDecodeError as err:
            msg = (
                f"Configuration file contains invalid JSON: "
                f"{err.msg} at line {err.lineno}"
            )
            raise ValueError(msg) from err

        if not isinstance(parsed, dict):
            t_name = type(parsed).__name__
            msg = f"Configuration JSON root must be an object, got {t_name}"
            raise ValueError(msg)

        return cls.from_dict(parsed)
