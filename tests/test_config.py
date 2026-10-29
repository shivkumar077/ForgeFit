"""Tests for ForgeFit configuration validation."""

from __future__ import annotations

import json
import socket
from pathlib import Path
from unittest.mock import patch

import pytest

from forgefit.config import ResilienceConfig


def test_valid_default_config() -> None:
    """ResilienceConfig initializes with valid defaults."""
    cfg = ResilienceConfig(target_url="https://api.example.com/v1/health")
    assert cfg.target_url == "https://api.example.com/v1/health"
    assert cfg.timeout_seconds == 5.0
    assert cfg.request_count == 10
    assert cfg.artificial_latency_ms == 0
    assert cfg.failure_probability == 0.0


def test_valid_custom_config() -> None:
    """ResilienceConfig accepts custom valid parameters."""
    cfg = ResilienceConfig(
        target_url="http://localhost:8080/test",
        timeout_seconds=2.5,
        request_count=50,
        artificial_latency_ms=250,
        failure_probability=0.25,
    )
    assert cfg.target_url == "http://localhost:8080/test"
    assert cfg.timeout_seconds == 2.5
    assert cfg.request_count == 50
    assert cfg.artificial_latency_ms == 250
    assert cfg.failure_probability == 0.25


@pytest.mark.parametrize(
    "invalid_url, expected_err",
    [
        ("", "cannot be empty"),
        ("   ", "cannot be empty"),
        ("ftp://example.com/resource", "must have 'http' or 'https' scheme"),
        ("file:///path/to/file", "must have 'http' or 'https' scheme"),
        ("http://", "must contain a valid network location"),
        ("/relative/path/endpoint", "must have 'http' or 'https' scheme"),
        ("not-a-url", "must have 'http' or 'https' scheme"),
    ],
)
def test_invalid_urls(invalid_url: str, expected_err: str) -> None:
    """ResilienceConfig rejects malformed or non-HTTP/HTTPS URLs."""
    with pytest.raises(ValueError, match=expected_err):
        ResilienceConfig(target_url=invalid_url)


def test_invalid_url_type() -> None:
    """ResilienceConfig rejects non-string target_url."""
    with pytest.raises(TypeError, match="target_url must be a string"):
        ResilienceConfig(target_url=123)  # type: ignore[arg-type]


@pytest.mark.parametrize(
    "invalid_timeout",
    [
        0,
        0.0,
        -1,
        -0.001,
        float("nan"),
        float("inf"),
        float("-inf"),
    ],
)
def test_invalid_timeout_values(invalid_timeout: float) -> None:
    """ResilienceConfig rejects non-positive or non-finite timeouts."""
    with pytest.raises(ValueError):
        ResilienceConfig(
            target_url="https://example.com",
            timeout_seconds=invalid_timeout,
        )


@pytest.mark.parametrize("invalid_type", [True, False, "5.0", [5.0], None])
def test_invalid_timeout_types(invalid_type: object) -> None:
    """ResilienceConfig rejects booleans and non-numeric timeout types."""
    with pytest.raises(TypeError):
        ResilienceConfig(
            target_url="https://example.com",
            timeout_seconds=invalid_type,  # type: ignore[arg-type]
        )


@pytest.mark.parametrize("invalid_count", [0, -1, -100])
def test_invalid_request_counts(invalid_count: int) -> None:
    """ResilienceConfig rejects request counts below 1."""
    with pytest.raises(ValueError, match="request_count must be at least 1"):
        ResilienceConfig(
            target_url="https://example.com",
            request_count=invalid_count,
        )


@pytest.mark.parametrize("invalid_type", [True, False, 1.5, "10", None])
def test_invalid_request_count_types(invalid_type: object) -> None:
    """ResilienceConfig rejects booleans, floats, and non-ints for request_count."""
    with pytest.raises(TypeError):
        ResilienceConfig(
            target_url="https://example.com",
            request_count=invalid_type,  # type: ignore[arg-type]
        )


@pytest.mark.parametrize("invalid_latency", [-1, -500])
def test_invalid_latency_values(invalid_latency: int) -> None:
    """ResilienceConfig rejects negative artificial latency."""
    with pytest.raises(ValueError, match="artificial_latency_ms must be non-negative"):
        ResilienceConfig(
            target_url="https://example.com",
            artificial_latency_ms=invalid_latency,
        )


@pytest.mark.parametrize("invalid_type", [True, False, 100.5, "200", None])
def test_invalid_latency_types(invalid_type: object) -> None:
    """ResilienceConfig rejects booleans, floats, and non-ints for latency."""
    with pytest.raises(TypeError):
        ResilienceConfig(
            target_url="https://example.com",
            artificial_latency_ms=invalid_type,  # type: ignore[arg-type]
        )


@pytest.mark.parametrize(
    "invalid_prob",
    [-0.01, -1.0, 1.01, 2.0, float("nan"), float("inf"), float("-inf")],
)
def test_invalid_failure_probabilities(invalid_prob: float) -> None:
    """ResilienceConfig rejects out-of-range and non-finite probabilities."""
    with pytest.raises(ValueError):
        ResilienceConfig(
            target_url="https://example.com",
            failure_probability=invalid_prob,
        )


@pytest.mark.parametrize("invalid_type", [True, False, "0.5", None])
def test_invalid_failure_probability_types(invalid_type: object) -> None:
    """ResilienceConfig rejects booleans and non-numeric probability types."""
    with pytest.raises(TypeError):
        ResilienceConfig(
            target_url="https://example.com",
            failure_probability=invalid_type,  # type: ignore[arg-type]
        )


def test_dict_serialization_roundtrip() -> None:
    """ResilienceConfig serializes to dict and parses back identically."""
    cfg = ResilienceConfig(
        target_url="https://api.test.org/v2/items",
        timeout_seconds=3.0,
        request_count=25,
        artificial_latency_ms=100,
        failure_probability=0.15,
    )
    data = cfg.to_dict()
    assert data == {
        "target_url": "https://api.test.org/v2/items",
        "timeout_seconds": 3.0,
        "request_count": 25,
        "artificial_latency_ms": 100,
        "failure_probability": 0.15,
        "total_deadline_seconds": 30.0,
        "allow_external": False,
        "authorized_acknowledgement": False,
        "seed": None,
    }
    restored = ResilienceConfig.from_dict(data)
    assert restored == cfg


def test_from_dict_missing_target_url() -> None:
    """from_dict raises ValueError when target_url is missing."""
    with pytest.raises(ValueError, match="missing required field: 'target_url'"):
        ResilienceConfig.from_dict({"timeout_seconds": 5.0})


def test_from_dict_non_dict_input() -> None:
    """from_dict raises TypeError when input is not a dictionary."""
    with pytest.raises(TypeError, match="must be a dictionary"):
        ResilienceConfig.from_dict(["not", "a", "dict"])  # type: ignore[arg-type]


def test_from_json_file_success(tmp_path: Path) -> None:
    """from_json_file successfully parses a valid JSON file."""
    config_file = tmp_path / "valid_config.json"
    payload = {
        "target_url": "https://service.internal/api",
        "timeout_seconds": 4.5,
        "request_count": 15,
        "artificial_latency_ms": 50,
        "failure_probability": 0.05,
    }
    config_file.write_text(json.dumps(payload), encoding="utf-8")

    cfg = ResilienceConfig.from_json_file(config_file)
    assert cfg.target_url == "https://service.internal/api"
    assert cfg.timeout_seconds == 4.5
    assert cfg.request_count == 15
    assert cfg.artificial_latency_ms == 50
    assert cfg.failure_probability == 0.05


def test_from_json_file_not_found(tmp_path: Path) -> None:
    """from_json_file raises ValueError if file does not exist."""
    missing_file = tmp_path / "nonexistent.json"
    with pytest.raises(ValueError, match="Configuration file not found"):
        ResilienceConfig.from_json_file(missing_file)


def test_from_json_file_invalid_syntax(tmp_path: Path) -> None:
    """from_json_file raises ValueError if file contains malformed JSON."""
    broken_file = tmp_path / "broken.json"
    broken_file.write_text("{ target_url: unquoted }", encoding="utf-8")
    with pytest.raises(ValueError, match="invalid JSON"):
        ResilienceConfig.from_json_file(broken_file)


def test_from_json_file_non_dict_root(tmp_path: Path) -> None:
    """from_json_file raises ValueError if JSON root is a list."""
    list_file = tmp_path / "list.json"
    list_file.write_text(json.dumps(["item1", "item2"]), encoding="utf-8")
    with pytest.raises(ValueError, match="root must be an object"):
        ResilienceConfig.from_json_file(list_file)


def test_no_network_calls_during_config(tmp_path: Path) -> None:
    """Configuration validation and loading perform zero network calls."""
    config_file = tmp_path / "offline_config.json"
    config_file.write_text(
        json.dumps({"target_url": "https://unreachable.domain.example/api"}),
        encoding="utf-8",
    )

    with patch.object(
        socket.socket, "connect", side_effect=AssertionError("Network call attempted")
    ):
        cfg = ResilienceConfig.from_json_file(config_file)
        assert cfg.target_url == "https://unreachable.domain.example/api"
        cfg.validate()


@pytest.mark.parametrize(
    "url, expected_loopback",
    [
        ("http://localhost:8080/v1", True),
        ("http://127.0.0.1:3000/health", True),
        ("http://[::1]:9000/api", True),
        ("https://api.github.com/zen", False),
        ("http://192.168.1.50:8000/test", False),
    ],
)
def test_loopback_target_detection(url: str, expected_loopback: bool) -> None:
    """ResilienceConfig correctly identifies loopback vs external host targets."""
    cfg = ResilienceConfig(target_url=url)
    assert cfg.is_loopback_target is expected_loopback


@pytest.mark.parametrize(
    "invalid_deadline",
    [0, 0.0, -1, -5.0, float("nan"), float("inf"), float("-inf")],
)
def test_invalid_total_deadline_values(invalid_deadline: float) -> None:
    """ResilienceConfig rejects non-positive or non-finite deadlines."""
    with pytest.raises(ValueError):
        ResilienceConfig(
            target_url="http://localhost",
            total_deadline_seconds=invalid_deadline,
        )


@pytest.mark.parametrize("invalid_type", [True, False, "30.0", None])
def test_invalid_total_deadline_types(invalid_type: object) -> None:
    """ResilienceConfig rejects booleans and non-numeric deadline types."""
    with pytest.raises(TypeError):
        ResilienceConfig(
            target_url="http://localhost",
            total_deadline_seconds=invalid_type,  # type: ignore[arg-type]
        )


def test_safety_flags_type_validation() -> None:
    """ResilienceConfig ensures safety flags are strictly booleans."""
    with pytest.raises(TypeError, match="allow_external must be a boolean"):
        ResilienceConfig(
            target_url="http://localhost",
            allow_external="yes",  # type: ignore[arg-type]
        )

    with pytest.raises(TypeError, match="authorized_acknowledgement must be a boolean"):
        ResilienceConfig(
            target_url="http://localhost",
            authorized_acknowledgement=1,  # type: ignore[arg-type]
        )


def test_seed_type_validation() -> None:
    """ResilienceConfig ensures seed is an integer and not a boolean."""
    with pytest.raises(TypeError, match="seed must be an integer"):
        ResilienceConfig(target_url="http://localhost", seed=True)  # type: ignore[arg-type]

    with pytest.raises(TypeError, match="seed must be an integer"):
        ResilienceConfig(target_url="http://localhost", seed="123")  # type: ignore[arg-type]
