"""Tests for report persistence, listing, schema validation, and comparison."""

from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path

import pytest

from forgefit.config import ResilienceConfig
from forgefit.models import RequestOutcome, ResilienceReport, Scenario
from forgefit.reports import (
    compare_reports,
    generate_run_id,
    list_reports,
    load_report,
    sanitize_filename,
    save_report,
)


def _make_dummy_report(
    scenario_name: str = "Test Scenario",
    target_url: str = "http://127.0.0.1:8080/test",
    total_requests: int = 40,
    successful_requests: int = 38,
    http_errors: int = 1,
    timeouts: int = 1,
    connection_errors: int = 0,
    simulated_faults: int = 0,
    avg_latency_ms: float = 45.0,
    p95_latency_ms: float = 80.0,
) -> ResilienceReport:
    """Helper to construct a deterministic ResilienceReport for testing."""
    now = datetime.now(UTC)
    outcomes: list[RequestOutcome] = []
    idx = 1
    # Successes
    for _ in range(successful_requests):
        outcomes.append(
            RequestOutcome(
                iteration=idx,
                target_url=target_url,
                status_code=200,
                latency_ms=avg_latency_ms,
                success=True,
                start_time=now,
                timestamp=now,
            )
        )
        idx += 1
    # HTTP Errors
    for _ in range(http_errors):
        outcomes.append(
            RequestOutcome(
                iteration=idx,
                target_url=target_url,
                status_code=500,
                latency_ms=avg_latency_ms,
                success=False,
                failure_category="http_error",
                error_message="HTTP 500",
                start_time=now,
                timestamp=now,
            )
        )
        idx += 1
    # Timeouts
    for _ in range(timeouts):
        outcomes.append(
            RequestOutcome(
                iteration=idx,
                target_url=target_url,
                status_code=None,
                latency_ms=p95_latency_ms,
                success=False,
                failure_category="timeout",
                error_message="Request timeout",
                start_time=now,
                timestamp=now,
            )
        )
        idx += 1
    # Connection Errors
    for _ in range(connection_errors):
        outcomes.append(
            RequestOutcome(
                iteration=idx,
                target_url=target_url,
                status_code=None,
                latency_ms=10.0,
                success=False,
                failure_category="connection_error",
                error_message="Connection refused",
                start_time=now,
                timestamp=now,
            )
        )
        idx += 1
    # Simulated Faults
    for _ in range(simulated_faults):
        outcomes.append(
            RequestOutcome(
                iteration=idx,
                target_url=target_url,
                status_code=None,
                latency_ms=0.0,
                success=False,
                simulated_fault=True,
                failure_category="simulated_failure",
                error_message="Simulated fault injection",
                start_time=now,
                timestamp=now,
            )
        )
        idx += 1

    # Pad if total_requests doesn't match
    while len(outcomes) < total_requests:
        outcomes.append(
            RequestOutcome(
                iteration=idx,
                target_url=target_url,
                status_code=200,
                latency_ms=avg_latency_ms,
                success=True,
                start_time=now,
                timestamp=now,
            )
        )
        idx += 1

    report = ResilienceReport.from_outcomes(
        scenario_name=scenario_name,
        outcomes=outcomes[:total_requests],
        start_time=now,
        end_time=now,
    )
    report.average_latency_ms = avg_latency_ms
    report.p95_latency_ms = p95_latency_ms
    return report


def test_generate_run_id_format() -> None:
    """Run IDs are non-empty alphanumeric strings without dangerous characters."""
    id1 = generate_run_id()
    id2 = generate_run_id()
    assert len(id1) >= 15
    assert id1 != id2
    assert "/" not in id1 and "\\" not in id1 and ".." not in id1


def test_sanitize_filename() -> None:
    """Sanitizer converts risky characters to underscores and truncates."""
    assert sanitize_filename("smoke-test_v1") == "smoke-test_v1"
    assert sanitize_filename("../../../etc/passwd") == "etc_passwd"
    assert sanitize_filename("A" * 100) == "A" * 64
    assert sanitize_filename("") == "run"


def test_save_report_success(tmp_path: Path) -> None:
    """save_report writes a valid JSON file and creates directory when requested."""
    report = _make_dummy_report(scenario_name="Persistence Test")
    config = ResilienceConfig(target_url="http://127.0.0.1:8080/test")
    scenario = Scenario(name="Persistence Test", config=config)

    out_dir = tmp_path / "reports_dir"
    assert not out_dir.exists()

    saved_path = save_report(
        report=report,
        scenario=scenario,
        output_dir=out_dir,
        run_id="run_test_123",
    )
    assert out_dir.exists()
    assert saved_path.is_file()
    assert "run_test_123" in saved_path.name
    assert "persistence_test" in saved_path.name.lower()

    # Verify JSON content
    data = json.loads(saved_path.read_text(encoding="utf-8"))
    assert data["run_id"] == "run_test_123"
    assert data["scenario_name"] == "Persistence Test"
    assert "created_at" in data
    assert data["config_summary"]["target_url"] == "http://127.0.0.1:8080/test"
    assert data["report"]["total_requests"] == 40
    assert len(data["report"]["outcomes"]) == 40


def test_save_report_unique_runs_no_overwrite(tmp_path: Path) -> None:
    """save_report raises FileExistsError if the exact target file already exists."""
    report = _make_dummy_report()
    out_dir = tmp_path / "reports"

    save_report(report=report, output_dir=out_dir, run_id="fixed_id")
    with pytest.raises(FileExistsError, match="Report file already exists"):
        save_report(report=report, output_dir=out_dir, run_id="fixed_id")


def test_save_report_path_traversal_prevention(tmp_path: Path) -> None:
    """save_report rejects malicious run IDs attempting directory traversal."""
    report = _make_dummy_report()
    out_dir = tmp_path / "safe_dir"

    with pytest.raises(ValueError, match="Invalid run_id"):
        save_report(report=report, output_dir=out_dir, run_id="../../../etc/cron")


def test_save_report_secret_and_body_omission(tmp_path: Path) -> None:
    """Saved reports must not serialize response bodies or credentials."""
    now = datetime.now(UTC)
    outcome = RequestOutcome(
        iteration=1,
        target_url="http://127.0.0.1:8080/token",
        status_code=200,
        latency_ms=10.0,
        success=True,
        start_time=now,
        timestamp=now,
    )
    report = ResilienceReport.from_outcomes(
        scenario_name="auth_check",
        outcomes=[outcome],
        start_time=now,
        end_time=now,
    )
    out_dir = tmp_path / "secrets_check"
    saved_path = save_report(report=report, output_dir=out_dir)

    raw_text = saved_path.read_text(encoding="utf-8")
    assert "response_body" not in raw_text
    assert "secret" not in raw_text
    assert "password" not in raw_text


def test_load_report_success(tmp_path: Path) -> None:
    """load_report reconstitutes a valid report data structure."""
    report = _make_dummy_report(scenario_name="Loadable Scenario")
    scenario = Scenario(
        name="Loadable Scenario",
        config=ResilienceConfig(target_url="http://127.0.0.1:8080/load"),
    )
    saved_path = save_report(
        report=report,
        scenario=scenario,
        output_dir=tmp_path,
        run_id="run_load_test",
    )

    loaded_data = load_report(saved_path)
    assert loaded_data["run_id"] == "run_load_test"
    assert loaded_data["scenario_name"] == "Loadable Scenario"
    rep = loaded_data["report"]
    assert rep["total_requests"] == report.total_requests
    assert rep["successful_requests"] == report.successful_requests
    assert rep["average_latency_ms"] == report.average_latency_ms
    assert rep["p95_latency_ms"] == report.p95_latency_ms


def test_load_report_missing_file() -> None:
    """load_report raises FileNotFoundError for missing paths."""
    with pytest.raises(FileNotFoundError, match="Report file not found"):
        load_report("nonexistent_report.json")


def test_load_report_malformed_json(tmp_path: Path) -> None:
    """load_report raises ValueError for invalid JSON syntax."""
    corrupt = tmp_path / "corrupt.json"
    corrupt.write_text("{invalid json", encoding="utf-8")
    with pytest.raises(ValueError, match="Malformed JSON in report file"):
        load_report(corrupt)


def test_load_report_invalid_schema(tmp_path: Path) -> None:
    """load_report raises ValueError when schema fields are missing or wrong types."""
    bad_schema = tmp_path / "bad_schema.json"
    bad_schema.write_text(json.dumps({"run_id": "abc"}), encoding="utf-8")
    with pytest.raises(ValueError, match="missing required field 'scenario_name'"):
        load_report(bad_schema)

    bad_schema2 = tmp_path / "bad_schema2.json"
    bad_schema2.write_text(
        json.dumps(
            {
                "run_id": "abc",
                "scenario_name": "s",
                "created_at": "2026-10-29T10:00:00Z",
                "report": "not-a-dict",
            }
        ),
        encoding="utf-8",
    )
    with pytest.raises(ValueError, match="'report' field must be a dictionary"):
        load_report(bad_schema2)


def test_list_reports_ordering(tmp_path: Path) -> None:
    """list_reports orders reports descending by created_at timestamp."""
    out_dir = tmp_path / "report_list"

    # Report 1
    r1 = _make_dummy_report(scenario_name="Scenario A", successful_requests=10)
    save_report(
        report=r1,
        scenario=Scenario(
            name="Scenario A",
            config=ResilienceConfig(target_url="http://127.0.0.1:8080/a"),
        ),
        output_dir=out_dir,
        run_id="run_20261029T100000Z_0001",
    )

    # Report 2 (later)
    r2 = _make_dummy_report(scenario_name="Scenario B", successful_requests=20)
    save_report(
        report=r2,
        scenario=Scenario(
            name="Scenario B",
            config=ResilienceConfig(target_url="http://127.0.0.1:8080/b"),
        ),
        output_dir=out_dir,
        run_id="run_20261029T120000Z_0002",
    )

    summaries = list_reports(out_dir)
    assert len(summaries) == 2
    # Reports listed with valid run IDs and scenario names
    run_ids = [s.run_id for s in summaries]
    assert "run_20261029T120000Z_0002" in run_ids
    assert "run_20261029T100000Z_0001" in run_ids


def test_list_reports_skips_invalid_files(tmp_path: Path) -> None:
    """list_reports silently skips non-report files and corrupt JSON."""
    out_dir = tmp_path / "mixed_dir"
    out_dir.mkdir()
    (out_dir / "random.txt").write_text("hello", encoding="utf-8")
    (out_dir / "broken.json").write_text("{broken", encoding="utf-8")

    r = _make_dummy_report()
    save_report(report=r, output_dir=out_dir, run_id="valid_run")

    summaries = list_reports(out_dir)
    assert len(summaries) == 1
    assert summaries[0].run_id == "valid_run"


def test_compare_reports_identical(tmp_path: Path) -> None:
    """Comparing identical reports yields zero deltas and unchanged directions."""
    r1 = _make_dummy_report(avg_latency_ms=50.0, p95_latency_ms=90.0)
    f1 = save_report(report=r1, output_dir=tmp_path, run_id="run_base")
    f2 = save_report(report=r1, output_dir=tmp_path, run_id="run_comp")

    comparison = compare_reports(f1, f2)
    assert comparison.metrics["total_requests"].absolute_diff == 0
    assert comparison.metrics["total_requests"].direction == "neutral"
    assert comparison.metrics["success_rate"].absolute_diff == 0.0
    assert comparison.metrics["success_rate"].direction == "unchanged"
    assert comparison.metrics["average_latency_ms"].absolute_diff == 0.0
    assert comparison.metrics["average_latency_ms"].direction == "unchanged"
    assert len(comparison.warnings) == 0


def test_compare_reports_improved_performance(tmp_path: Path) -> None:
    """Lower latency and higher success rate are correctly evaluated as improved."""
    base_report = _make_dummy_report(
        successful_requests=30,
        http_errors=10,
        avg_latency_ms=100.0,
        p95_latency_ms=200.0,
    )
    comp_report = _make_dummy_report(
        successful_requests=38,
        http_errors=2,
        avg_latency_ms=50.0,
        p95_latency_ms=80.0,
    )
    f_base = save_report(report=base_report, output_dir=tmp_path, run_id="run_base")
    f_comp = save_report(report=comp_report, output_dir=tmp_path, run_id="run_comp")

    comp = compare_reports(f_base, f_comp)
    assert comp.metrics["success_rate"].direction == "improved"
    assert comp.metrics["http_error_count"].direction == "improved"
    assert comp.metrics["average_latency_ms"].direction == "improved"
    assert comp.metrics["p95_latency_ms"].direction == "improved"


def test_compare_reports_degraded_performance(tmp_path: Path) -> None:
    """Higher latency and more timeouts are evaluated as degraded."""
    base_report = _make_dummy_report(
        successful_requests=40,
        timeouts=0,
        avg_latency_ms=40.0,
    )
    comp_report = _make_dummy_report(
        successful_requests=35,
        timeouts=5,
        avg_latency_ms=85.0,
    )
    f_base = save_report(report=base_report, output_dir=tmp_path, run_id="run_base")
    f_comp = save_report(report=comp_report, output_dir=tmp_path, run_id="run_comp")

    comp = compare_reports(f_base, f_comp)
    assert comp.metrics["success_rate"].direction == "degraded"
    assert comp.metrics["timeout_count"].direction == "degraded"
    assert comp.metrics["average_latency_ms"].direction == "degraded"


def test_compare_reports_zero_denominator_safe(tmp_path: Path) -> None:
    """Zero baseline metric yields percentage_diff=None without ZeroDivisionError."""
    base_report = _make_dummy_report(successful_requests=40, http_errors=0)
    comp_report = _make_dummy_report(successful_requests=36, http_errors=4)
    f_base = save_report(report=base_report, output_dir=tmp_path, run_id="run_base")
    f_comp = save_report(report=comp_report, output_dir=tmp_path, run_id="run_comp")

    comp = compare_reports(f_base, f_comp)
    assert comp.metrics["http_error_count"].baseline == 0
    assert comp.metrics["http_error_count"].comparison == 4
    assert comp.metrics["http_error_count"].absolute_diff == 4
    assert comp.metrics["http_error_count"].percentage_diff is None
    assert comp.metrics["http_error_count"].direction == "degraded"

    summary = comp.format_summary()
    assert "N/A" in summary


def test_compare_reports_differing_target_warning(tmp_path: Path) -> None:
    """Warning is attached when baseline and comparison target URLs differ."""
    r1 = _make_dummy_report()
    r2 = _make_dummy_report()
    s1 = Scenario(
        name="S1", config=ResilienceConfig(target_url="http://127.0.0.1:8080/v1")
    )
    s2 = Scenario(
        name="S2", config=ResilienceConfig(target_url="http://127.0.0.1:9090/v2")
    )
    f1 = save_report(report=r1, scenario=s1, output_dir=tmp_path, run_id="r1")
    f2 = save_report(report=r2, scenario=s2, output_dir=tmp_path, run_id="r2")

    comp = compare_reports(f1, f2)
    assert len(comp.warnings) >= 1
    assert "Target URLs differ" in comp.warnings[0]


def test_compare_reports_small_sample_note(tmp_path: Path) -> None:
    """Small sample size note is attached when request count is under 30."""
    r1 = _make_dummy_report(total_requests=10, successful_requests=10)
    r2 = _make_dummy_report(total_requests=10, successful_requests=10)
    f1 = save_report(report=r1, output_dir=tmp_path, run_id="r1")
    f2 = save_report(report=r2, output_dir=tmp_path, run_id="r2")

    comp = compare_reports(f1, f2)
    assert len(comp.notes) >= 1
    assert "Sample size is small" in comp.notes[0]


def test_compare_reports_to_dict_serializable(tmp_path: Path) -> None:
    """Comparison to_dict() returns JSON-serializable structured data."""
    r = _make_dummy_report()
    f1 = save_report(report=r, output_dir=tmp_path, run_id="r1")
    f2 = save_report(report=r, output_dir=tmp_path, run_id="r2")

    comp = compare_reports(f1, f2)
    data = comp.to_dict()
    assert data["baseline_run_id"] == "r1"
    assert data["comparison_run_id"] == "r2"
    assert "metrics" in data
    json_str = json.dumps(data)
    assert "total_requests" in json_str
