"""Tests for ForgeFit CLI interface."""

from __future__ import annotations

import http.server
import json
import socket
import threading
from pathlib import Path
from unittest.mock import patch

import pytest

from forgefit import __version__
from forgefit.cli import main
from forgefit.config import ResilienceConfig
from forgefit.models import RequestOutcome, ResilienceReport, Scenario
from forgefit.reports import save_report


class LocalCLIMockHandler(http.server.BaseHTTPRequestHandler):
    """Local HTTP mock server for exercising CLI run command safely."""

    def log_message(self, format: str, *args: object) -> None:
        return

    def do_GET(self) -> None:
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.end_headers()
        self.wfile.write(b'{"status": "ok"}')


@pytest.fixture(scope="module")
def cli_mock_server() -> tuple[http.server.ThreadingHTTPServer, str]:
    server = http.server.ThreadingHTTPServer(("127.0.0.1", 0), LocalCLIMockHandler)
    port = server.server_port
    base_url = f"http://127.0.0.1:{port}"

    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()

    yield server, base_url

    server.shutdown()
    server.server_close()


def test_cli_help(capsys: pytest.CaptureFixture[str]) -> None:
    """forgefit --help returns exit code 0 and prints usage instructions."""
    with pytest.raises(SystemExit) as exc:
        main(["--help"])
    assert exc.value.code == 0

    captured = capsys.readouterr()
    assert "ForgeFit: A Python-based API resilience testing toolkit" in captured.out
    assert "validate-config" in captured.out
    assert "run" in captured.out


def test_cli_no_args(capsys: pytest.CaptureFixture[str]) -> None:
    """forgefit without arguments displays help and returns exit code 0."""
    exit_code = main([])
    assert exit_code == 0
    captured = capsys.readouterr()
    assert "usage: forgefit" in captured.out


def test_cli_version(capsys: pytest.CaptureFixture[str]) -> None:
    """forgefit --version prints version string and exits cleanly."""
    with pytest.raises(SystemExit) as exc:
        main(["--version"])
    assert exc.value.code == 0

    captured = capsys.readouterr()
    assert f"forgefit {__version__}" in captured.out


def test_cli_validate_config_success(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """forgefit validate-config with a valid file returns 0 and displays parameters."""
    config_file = tmp_path / "valid.json"
    config_file.write_text(
        json.dumps(
            {
                "target_url": "https://api.testservice.com/health",
                "timeout_seconds": 3.5,
                "request_count": 20,
                "artificial_latency_ms": 100,
                "failure_probability": 0.1,
            }
        ),
        encoding="utf-8",
    )

    exit_code = main(["validate-config", str(config_file)])
    assert exit_code == 0

    captured = capsys.readouterr()
    assert "Configuration is valid:" in captured.out
    assert "https://api.testservice.com/health" in captured.out
    assert "100 ms" in captured.out


def test_cli_validate_config_invalid_data(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """forgefit validate-config with invalid parameters returns 1 and reports error."""
    invalid_file = tmp_path / "invalid.json"
    invalid_file.write_text(
        json.dumps(
            {
                "target_url": "invalid-url",
                "timeout_seconds": -5,
            }
        ),
        encoding="utf-8",
    )

    exit_code = main(["validate-config", str(invalid_file)])
    assert exit_code == 1

    captured = capsys.readouterr()
    assert "Error: Invalid configuration:" in captured.err


def test_cli_validate_config_missing_file(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """forgefit validate-config with a non-existent file returns 1."""
    missing_file = tmp_path / "does_not_exist.json"

    exit_code = main(["validate-config", str(missing_file)])
    assert exit_code == 1

    captured = capsys.readouterr()
    assert "Error: Invalid configuration: Configuration file not found" in captured.err


def test_cli_no_network_calls(tmp_path: Path) -> None:
    """CLI commands never invoke network sockets during config validation."""
    valid_file = tmp_path / "test.json"
    valid_file.write_text(
        json.dumps({"target_url": "https://unreachable.external.site/v1"}),
        encoding="utf-8",
    )

    with patch.object(
        socket.socket, "connect", side_effect=AssertionError("Network attempted by CLI")
    ):
        exit_code = main(["validate-config", str(valid_file)])
        assert exit_code == 0


def test_cli_run_local_mock(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
    cli_mock_server: tuple[http.server.ThreadingHTTPServer, str],
) -> None:
    """forgefit run executes against a local mock server and prints summary."""
    _, base_url = cli_mock_server
    config_file = tmp_path / "local_run.json"
    config_file.write_text(
        json.dumps(
            {
                "target_url": f"{base_url}/status",
                "request_count": 3,
                "timeout_seconds": 2.0,
            }
        ),
        encoding="utf-8",
    )

    exit_code = main(["run", str(config_file)])
    assert exit_code == 0

    captured = capsys.readouterr()
    assert "Initiating scenario:" in captured.out
    assert "Execution Summary:" in captured.out
    assert "Total Requests:         3" in captured.out
    assert "Successful (2xx):       3" in captured.out


def test_cli_run_json_output(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
    cli_mock_server: tuple[http.server.ThreadingHTTPServer, str],
) -> None:
    """forgefit run --json outputs a valid JSON report."""
    _, base_url = cli_mock_server
    config_file = tmp_path / "json_run.json"
    config_file.write_text(
        json.dumps(
            {
                "target_url": f"{base_url}/data",
                "request_count": 2,
            }
        ),
        encoding="utf-8",
    )

    exit_code = main(["run", str(config_file), "--json"])
    assert exit_code == 0

    captured = capsys.readouterr()
    data = json.loads(captured.out)
    assert data["scenario_name"] == "json_run"
    assert data["total_requests"] == 2
    assert len(data["outcomes"]) == 2


def test_cli_run_external_denied(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    """forgefit run against external URL fails without authorization flags."""
    config_file = tmp_path / "ext_denied.json"
    config_file.write_text(
        json.dumps({"target_url": "https://api.external.com/v1"}),
        encoding="utf-8",
    )

    exit_code = main(["run", str(config_file)])
    assert exit_code == 1

    captured = capsys.readouterr()
    assert "Safety Violation:" in captured.err
    assert "allow_external=True" in captured.err


def test_cli_run_missing_file(capsys: pytest.CaptureFixture[str]) -> None:
    """forgefit run returns 1 when config file does not exist."""
    exit_code = main(["run", "missing_config.json"])
    assert exit_code == 1
    captured = capsys.readouterr()
    assert "Error: Invalid configuration:" in captured.err


def test_cli_scenario_validate_valid(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    """forgefit scenario validate succeeds with valid scenario file."""
    scenario_path = tmp_path / "valid_scenario.json"
    scenario_path.write_text(
        json.dumps(
            {
                "name": "CLI Validation Test",
                "config": {
                    "target_url": "http://127.0.0.1:8080/health",
                    "request_count": 5,
                },
            }
        ),
        encoding="utf-8",
    )
    exit_code = main(["scenario", "validate", str(scenario_path)])
    assert exit_code == 0
    captured = capsys.readouterr()
    assert "Scenario configuration is valid: CLI Validation Test" in captured.out


def test_cli_scenario_validate_invalid(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    """forgefit scenario validate fails with invalid scenario configuration."""
    scenario_path = tmp_path / "invalid_scenario.json"
    scenario_path.write_text(
        json.dumps(
            {
                "name": "Invalid Scenario",
                "config": {
                    "target_url": "http://127.0.0.1:8080/health",
                    "request_count": -1,
                },
            }
        ),
        encoding="utf-8",
    )
    exit_code = main(["scenario", "validate", str(scenario_path)])
    assert exit_code == 1
    captured = capsys.readouterr()
    assert "Error: Invalid scenario:" in captured.err


def test_cli_scenario_validate_missing_file(
    capsys: pytest.CaptureFixture[str],
) -> None:
    """forgefit scenario validate fails when file does not exist."""
    exit_code = main(["scenario", "validate", "nonexistent_scenario.json"])
    assert exit_code == 1
    captured = capsys.readouterr()
    assert "Error: File not found:" in captured.err


def test_cli_run_with_output_dir(
    cli_mock_server: tuple[http.server.ThreadingHTTPServer, str],
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    """forgefit run persists report when --output-dir is specified."""
    _, base_url = cli_mock_server
    scenario_file = tmp_path / "scenario.json"
    scenario_file.write_text(
        json.dumps(
            {
                "name": "Persist Scenario",
                "config": {
                    "target_url": f"{base_url}/test",
                    "request_count": 3,
                },
            }
        ),
        encoding="utf-8",
    )
    out_dir = tmp_path / "persisted_reports"
    exit_code = main(["run", str(scenario_file), "--output-dir", str(out_dir)])
    assert exit_code == 0
    captured = capsys.readouterr()
    assert "Report Saved:" in captured.out
    report_files = list(out_dir.glob("*.json"))
    assert len(report_files) == 1
    assert str(report_files[0]) in captured.out
    report_data = json.loads(report_files[0].read_text(encoding="utf-8"))
    assert report_data["scenario_name"] == "Persist Scenario"


def test_cli_reports_list(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    """forgefit reports list displays formatted table of saved reports."""
    from datetime import UTC, datetime

    now = datetime.now(UTC)
    outcome = RequestOutcome(
        iteration=1,
        target_url="http://127.0.0.1:8080/ping",
        status_code=200,
        latency_ms=12.5,
        success=True,
        start_time=now,
        timestamp=now,
    )
    report = ResilienceReport.from_outcomes(
        scenario_name="List Demo",
        outcomes=[outcome],
        start_time=now,
        end_time=now,
    )
    save_report(
        report=report,
        scenario=Scenario(
            name="List Demo",
            config=ResilienceConfig(target_url="http://127.0.0.1:8080/ping"),
        ),
        output_dir=tmp_path,
        run_id="run_demo_list_01",
    )

    exit_code = main(["reports", "list", "--directory", str(tmp_path)])
    assert exit_code == 0
    captured = capsys.readouterr()
    assert "run_demo_list_01" in captured.out
    assert "List Demo" in captured.out


def test_cli_reports_list_empty(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    """forgefit reports list indicates when no reports are found."""
    empty_dir = tmp_path / "empty_dir"
    empty_dir.mkdir()
    exit_code = main(["reports", "list", "--directory", str(empty_dir)])
    assert exit_code == 0
    captured = capsys.readouterr()
    assert "No saved reports found" in captured.out


def test_cli_reports_compare_summary(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    """forgefit reports compare prints formatted comparison table."""
    from datetime import UTC, datetime

    now = datetime.now(UTC)
    outcome1 = RequestOutcome(
        iteration=1,
        target_url="http://127.0.0.1:8080/api",
        status_code=200,
        latency_ms=50.0,
        success=True,
        start_time=now,
        timestamp=now,
    )
    outcome2 = RequestOutcome(
        iteration=1,
        target_url="http://127.0.0.1:8080/api",
        status_code=200,
        latency_ms=25.0,
        success=True,
        start_time=now,
        timestamp=now,
    )
    rep1 = ResilienceReport.from_outcomes(
        scenario_name="API Test", outcomes=[outcome1], start_time=now, end_time=now
    )
    rep2 = ResilienceReport.from_outcomes(
        scenario_name="API Test", outcomes=[outcome2], start_time=now, end_time=now
    )
    p1 = save_report(report=rep1, output_dir=tmp_path, run_id="run_base")
    p2 = save_report(report=rep2, output_dir=tmp_path, run_id="run_comp")

    exit_code = main(["reports", "compare", str(p1), str(p2)])
    assert exit_code == 0
    captured = capsys.readouterr()
    assert "ForgeFit Resilience Run Comparison" in captured.out
    assert "Baseline:" in captured.out
    assert "Comparison:" in captured.out


def test_cli_reports_compare_json(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    """forgefit reports compare --json prints JSON structured comparison."""
    from datetime import UTC, datetime

    now = datetime.now(UTC)
    outcome = RequestOutcome(
        iteration=1,
        target_url="http://127.0.0.1:8080/api",
        status_code=200,
        latency_ms=30.0,
        success=True,
        start_time=now,
        timestamp=now,
    )
    rep = ResilienceReport.from_outcomes(
        scenario_name="JSON Comp", outcomes=[outcome], start_time=now, end_time=now
    )
    p1 = save_report(report=rep, output_dir=tmp_path, run_id="r1")
    p2 = save_report(report=rep, output_dir=tmp_path, run_id="r2")

    exit_code = main(["reports", "compare", str(p1), str(p2), "--json"])
    assert exit_code == 0
    captured = capsys.readouterr()
    data = json.loads(captured.out)
    assert data["baseline_run_id"] == "r1"
    assert data["comparison_run_id"] == "r2"
    assert "metrics" in data


def test_cli_reports_compare_missing_file(
    capsys: pytest.CaptureFixture[str],
) -> None:
    """forgefit reports compare fails when baseline or comparison is missing."""
    exit_code = main(["reports", "compare", "missing_b.json", "missing_c.json"])
    assert exit_code == 1
    captured = capsys.readouterr()
    assert "Error loading baseline report" in captured.err


def test_cli_subcommand_helps(capsys: pytest.CaptureFixture[str]) -> None:
    """Subcommands without action print help and exit 0."""
    code1 = main(["scenario"])
    assert code1 == 0
    out1 = capsys.readouterr().out
    assert "usage:" in out1

    code2 = main(["reports"])
    assert code2 == 0
    out2 = capsys.readouterr().out
    assert "usage:" in out2


def test_cli_reports_export_prometheus(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    """forgefit reports export --format prometheus prints valid exposition text."""
    from datetime import UTC, datetime

    now = datetime.now(UTC)
    outcome = RequestOutcome(
        iteration=1,
        target_url="http://127.0.0.1:8080/test",
        status_code=200,
        latency_ms=15.0,
        success=True,
        start_time=now,
        timestamp=now,
    )
    report = ResilienceReport.from_outcomes(
        scenario_name="Export Demo",
        outcomes=[outcome],
        start_time=now,
        end_time=now,
    )
    saved_path = save_report(
        report=report,
        output_dir=tmp_path,
        run_id="run_export_01",
    )

    exit_code = main(["reports", "export", str(saved_path), "--format", "prometheus"])
    assert exit_code == 0
    captured = capsys.readouterr()
    assert "forgefit_requests_total{" in captured.out
    assert "forgefit_requests_success_total{" in captured.out


def test_cli_reports_export_otel_to_file(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    """forgefit reports export --format otel --output <file> writes valid OTel JSON."""
    from datetime import UTC, datetime

    now = datetime.now(UTC)
    outcome = RequestOutcome(
        iteration=1,
        target_url="http://127.0.0.1:8080/test",
        status_code=200,
        latency_ms=25.0,
        success=True,
        start_time=now,
        timestamp=now,
    )
    report = ResilienceReport.from_outcomes(
        scenario_name="OTel Demo",
        outcomes=[outcome],
        start_time=now,
        end_time=now,
    )
    saved_path = save_report(
        report=report,
        output_dir=tmp_path,
        run_id="run_otel_01",
    )
    out_file = tmp_path / "otel_metrics.json"

    exit_code = main(
        [
            "reports",
            "export",
            str(saved_path),
            "--format",
            "otel",
            "--output",
            str(out_file),
        ]
    )
    assert exit_code == 0
    captured = capsys.readouterr()
    assert "Exported otel metrics to:" in captured.out
    assert out_file.is_file()
    data = json.loads(out_file.read_text(encoding="utf-8"))
    assert "resourceMetrics" in data


def test_cli_reports_export_invalid_format(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    """forgefit reports export fails with invalid format."""
    # Argparse choices will reject it with exit code 2
    with pytest.raises(SystemExit) as exc_info:
        main(["reports", "export", "dummy.json", "--format", "invalid_fmt"])
    assert exc_info.value.code != 0


def test_cli_scenario_validate_with_schedule(
    capsys: pytest.CaptureFixture[str],
) -> None:
    """forgefit scenario validate displays fault schedule when configured."""
    example_path = Path("examples/scheduled_scenario.json")
    assert example_path.is_file()
    exit_code = main(["scenario", "validate", str(example_path)])
    assert exit_code == 0
    captured = capsys.readouterr()
    assert "Fault schedule:         ramped" in captured.out


def test_cli_web_help(capsys: pytest.CaptureFixture[str]) -> None:
    """forgefit web --help displays web server options."""
    with pytest.raises(SystemExit) as exc_info:
        main(["web", "--help"])
    assert exc_info.value.code == 0
    captured = capsys.readouterr()
    assert "Start the local ForgeFit web API" in captured.out
    assert "--port" in captured.out
