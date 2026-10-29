"""Tests for Scenario configuration loading, validation, and serialization."""

import json
from pathlib import Path
from urllib.parse import urlsplit

import pytest

from forgefit.config import ResilienceConfig, is_loopback_host
from forgefit.models import Scenario


def test_scenario_valid_instantiation() -> None:
    """A scenario can be created directly with valid fields."""
    config = ResilienceConfig(target_url="http://127.0.0.1:8080/test")
    scenario = Scenario(
        name="Test Scenario",
        config=config,
        description="A test description",
        tags=["smoke", "v1"],
    )
    assert scenario.name == "Test Scenario"
    assert scenario.description == "A test description"
    assert scenario.tags == ["smoke", "v1"]
    assert scenario.config.target_url == "http://127.0.0.1:8080/test"


def test_scenario_from_dict_full() -> None:
    """Scenario.from_dict correctly parses a complete scenario dictionary."""
    data = {
        "name": "Load Test",
        "description": "Stress testing local endpoint",
        "tags": ["stress", "load"],
        "config": {
            "target_url": "http://127.0.0.1:9000/api",
            "request_count": 50,
            "timeout_seconds": 1.5,
            "artificial_latency_ms": 25,
            "failure_probability": 0.1,
            "total_deadline_seconds": 15.0,
            "seed": 12345,
        },
    }
    scenario = Scenario.from_dict(data)
    assert scenario.name == "Load Test"
    assert scenario.description == "Stress testing local endpoint"
    assert scenario.tags == ["stress", "load"]
    assert scenario.config.target_url == "http://127.0.0.1:9000/api"
    assert scenario.config.request_count == 50
    assert scenario.config.seed == 12345


def test_scenario_to_dict_and_roundtrip() -> None:
    """Scenario can serialize to dict and round-trip faithfully."""
    config = ResilienceConfig(
        target_url="http://localhost:5000/ping",
        request_count=10,
        timeout_seconds=3.0,
    )
    original = Scenario(
        name="Ping Scenario",
        config=config,
        description="Ping check",
        tags=["ping"],
    )
    data = original.to_dict()
    assert data["name"] == "Ping Scenario"
    assert data["description"] == "Ping check"
    assert data["tags"] == ["ping"]
    assert data["config"]["target_url"] == "http://localhost:5000/ping"

    reconstructed = Scenario.from_dict(data)
    assert reconstructed.name == original.name
    assert reconstructed.description == original.description
    assert reconstructed.tags == original.tags
    assert reconstructed.config.target_url == original.config.target_url
    assert reconstructed.config.request_count == original.config.request_count


def test_scenario_file_roundtrip(tmp_path: Path) -> None:
    """Scenario can be written to file and reloaded identically."""
    config = ResilienceConfig(
        target_url="http://127.0.0.1:8080/data",
        request_count=25,
    )
    scenario = Scenario(
        name="File Roundtrip Test",
        config=config,
        description="Verifying file persistence",
        tags=["io"],
    )
    file_path = tmp_path / "scenario.json"
    scenario.to_json_file(file_path)

    loaded = Scenario.from_json_file(file_path)
    assert loaded.name == scenario.name
    assert loaded.description == scenario.description
    assert loaded.tags == scenario.tags
    assert loaded.config.target_url == scenario.config.target_url
    assert loaded.config.request_count == scenario.config.request_count


def test_scenario_from_dict_missing_config() -> None:
    """Reject scenario dictionaries that do not have a 'config' mapping."""
    with pytest.raises(ValueError, match="must contain a 'config' mapping"):
        Scenario.from_dict({"name": "No Config"})


def test_scenario_from_dict_invalid_root_type() -> None:
    """Reject non-dict objects passed to from_dict."""
    with pytest.raises(TypeError, match="Scenario data must be a dictionary"):
        Scenario.from_dict(["not", "a", "dict"])  # type: ignore[arg-type]


def test_scenario_from_dict_invalid_name_type() -> None:
    """Reject non-string name fields."""
    with pytest.raises(TypeError, match="'name' must be a string"):
        Scenario.from_dict({"name": 123, "config": {"target_url": "http://localhost"}})


def test_scenario_from_dict_empty_name() -> None:
    """Reject empty or whitespace-only name fields."""
    with pytest.raises(ValueError, match="'name' cannot be empty or whitespace"):
        Scenario.from_dict(
            {"name": "   ", "config": {"target_url": "http://localhost"}}
        )


def test_scenario_from_dict_invalid_description_type() -> None:
    """Reject non-string description fields."""
    with pytest.raises(TypeError, match="'description' must be a string"):
        Scenario.from_dict(
            {
                "name": "Valid",
                "description": 1234,
                "config": {"target_url": "http://localhost"},
            }
        )


def test_scenario_from_dict_invalid_tags_type() -> None:
    """Reject non-list tags or non-string tag items."""
    with pytest.raises(TypeError, match="'tags' must be a list of strings"):
        Scenario.from_dict(
            {
                "name": "Valid",
                "tags": "not-a-list",
                "config": {"target_url": "http://localhost"},
            }
        )
    with pytest.raises(TypeError, match="Scenario tag item must be a string"):
        Scenario.from_dict(
            {
                "name": "Valid",
                "tags": [123, 456],
                "config": {"target_url": "http://localhost"},
            }
        )


def test_scenario_from_dict_invalid_nested_config() -> None:
    """Validation errors inside ResilienceConfig propagate cleanly."""
    with pytest.raises(ValueError, match="request_count must be at least 1"):
        Scenario.from_dict(
            {
                "name": "Invalid Config",
                "config": {
                    "target_url": "http://127.0.0.1:8080/test",
                    "request_count": -5,
                },
            }
        )


def test_scenario_from_dict_legacy_flat_config() -> None:
    """Legacy flat config without 'config' key is parsed with compatibility."""
    flat_data = {
        "target_url": "http://127.0.0.1:8080/legacy",
        "request_count": 15,
        "timeout_seconds": 2.0,
    }
    scenario = Scenario.from_dict(flat_data)
    assert scenario.name == "default"
    assert scenario.config.target_url == "http://127.0.0.1:8080/legacy"
    assert scenario.config.request_count == 15


def test_scenario_from_json_file_legacy_names_from_stem(tmp_path: Path) -> None:
    """Loading a legacy flat config file names the scenario from the file stem."""
    flat_data = {
        "target_url": "http://127.0.0.1:8080/legacy-stem",
        "request_count": 5,
    }
    file_path = tmp_path / "legacy_test_run.json"
    file_path.write_text(json.dumps(flat_data), encoding="utf-8")

    scenario = Scenario.from_json_file(file_path)
    assert scenario.name == "legacy_test_run"
    assert scenario.config.target_url == "http://127.0.0.1:8080/legacy-stem"


def test_scenario_from_json_file_missing_file() -> None:
    """Nonexistent scenario file raises FileNotFoundError."""
    with pytest.raises(
        FileNotFoundError, match="Scenario configuration file not found"
    ):
        Scenario.from_json_file("nonexistent_path_scenario.json")


def test_scenario_from_json_file_malformed_json(tmp_path: Path) -> None:
    """Malformed JSON syntax raises ValueError with file name."""
    bad_file = tmp_path / "malformed.json"
    bad_file.write_text("{not: valid: json", encoding="utf-8")
    with pytest.raises(ValueError, match="Malformed JSON in scenario file"):
        Scenario.from_json_file(bad_file)


def test_sample_scenario_example_valid() -> None:
    """The committed example scenario file loads and validates cleanly."""
    example_path = Path("examples/sample_scenario.json")
    assert example_path.is_file(), "examples/sample_scenario.json must exist"
    scenario = Scenario.from_json_file(example_path)
    assert scenario.name == "Localhost Baseline Healthcheck"
    assert is_loopback_host(urlsplit(scenario.config.target_url).hostname) is True
    assert scenario.config.request_count == 20
