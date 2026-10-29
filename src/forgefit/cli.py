"""Command-line interface for ForgeFit."""

from __future__ import annotations

import argparse
import json
import sys
from collections.abc import Sequence
from pathlib import Path

from forgefit import __version__
from forgefit.config import ResilienceConfig
from forgefit.engine import ResilienceEngine, SafetyViolationError
from forgefit.exporters import export_report
from forgefit.models import Scenario
from forgefit.reports import (
    compare_reports,
    list_reports,
    load_report,
    save_report,
)


def create_parser() -> argparse.ArgumentParser:
    """Create the top-level argument parser for the ForgeFit CLI."""
    parser = argparse.ArgumentParser(
        prog="forgefit",
        description=(
            "ForgeFit: A Python-based API resilience testing toolkit.\n"
            "Simulates service failures, injects faults, and evaluates behavior.\n\n"
            "Milestone 3 adds scenario management, persistent reports, "
            "and run comparison.\n"
            "Live external requests require explicit opt-in and operator authorization."
        ),
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument(
        "-v",
        "--version",
        action="version",
        version=f"forgefit {__version__}",
        help="Show package version and exit.",
    )

    subparsers = parser.add_subparsers(dest="command", help="Available subcommands")

    # Subcommand: validate-config (backward compatibility)
    validate_parser = subparsers.add_parser(
        "validate-config",
        help="Validate a scenario configuration JSON file without network calls.",
        description=(
            "Load and validate a ForgeFit configuration file against "
            "resilience constraints."
        ),
    )
    validate_parser.add_argument(
        "config_file",
        help="Path to the JSON configuration file to validate.",
    )

    # Subcommand: scenario
    scenario_parser = subparsers.add_parser(
        "scenario",
        help="Scenario management commands.",
        description="Validate and manage named resilience test scenarios.",
    )
    scenario_subparsers = scenario_parser.add_subparsers(
        dest="scenario_action", help="Scenario actions"
    )
    scenario_val_parser = scenario_subparsers.add_parser(
        "validate",
        help="Validate a scenario JSON file.",
        description="Load and validate a scenario definition and its configuration.",
    )
    scenario_val_parser.add_argument(
        "scenario_file",
        help="Path to the scenario JSON file to validate.",
    )

    # Subcommand: run
    run_parser = subparsers.add_parser(
        "run",
        help="Execute a controlled resilience scenario from a configuration file.",
        description=(
            "Execute bounded, sequential resilience testing requests. "
            "Defaults to local loopback targets."
        ),
    )
    run_parser.add_argument(
        "config_file",
        help="Path to the scenario or configuration JSON file.",
    )
    run_parser.add_argument(
        "--allow-external",
        action="store_true",
        help="Explicitly permit targeting non-loopback external hosts.",
    )
    run_parser.add_argument(
        "--acknowledge-authorized",
        action="store_true",
        help="Acknowledge explicit operator authorization to test target host.",
    )
    run_parser.add_argument(
        "--json",
        dest="json_output",
        action="store_true",
        help="Output the final ResilienceReport in JSON format.",
    )
    run_parser.add_argument(
        "--output-dir",
        default=None,
        help="Directory where the execution report will be saved as JSON.",
    )

    # Subcommand: reports
    reports_parser = subparsers.add_parser(
        "reports",
        help="Saved report management and comparison.",
        description="List saved reports and compare performance across runs.",
    )
    reports_subparsers = reports_parser.add_subparsers(
        dest="reports_action", help="Reports actions"
    )

    # reports list
    list_parser = reports_subparsers.add_parser(
        "list",
        help="List saved execution reports.",
        description="List execution reports stored in a directory.",
    )
    list_parser.add_argument(
        "--directory",
        "-d",
        default="reports",
        help="Directory containing report files (default: reports).",
    )

    # reports compare
    compare_parser = reports_subparsers.add_parser(
        "compare",
        help="Compare two saved execution reports.",
        description=(
            "Compare metrics between a baseline report and a comparison report."
        ),
    )
    compare_parser.add_argument(
        "baseline_report",
        help="Path to the baseline report JSON file.",
    )
    compare_parser.add_argument(
        "comparison_report",
        help="Path to the comparison report JSON file.",
    )
    compare_parser.add_argument(
        "--json",
        dest="json_output",
        action="store_true",
        help="Output comparison result in JSON format.",
    )

    # reports export
    export_parser = reports_subparsers.add_parser(
        "export",
        help="Export a saved report to Prometheus or OpenTelemetry format.",
        description=(
            "Export report metrics to Prometheus text exposition format or "
            "OpenTelemetry-compatible JSON."
        ),
    )
    export_parser.add_argument(
        "report_file",
        help="Path to the saved report JSON file.",
    )
    export_parser.add_argument(
        "--format",
        "-f",
        dest="export_format",
        choices=["prometheus", "otel", "opentelemetry"],
        default="prometheus",
        help="Export format (default: prometheus).",
    )
    export_parser.add_argument(
        "--output",
        "-o",
        dest="output_file",
        default=None,
        help="Optional destination file path (defaults to stdout).",
    )

    # Subcommand: web
    web_parser = subparsers.add_parser(
        "web",
        help="Launch the ForgeFit interactive web application.",
        description="Start the local ForgeFit web API and user interface.",
    )
    web_parser.add_argument(
        "--host",
        default="127.0.0.1",
        help="Bind host (default: 127.0.0.1).",
    )
    web_parser.add_argument(
        "--port",
        "-p",
        type=int,
        default=8000,
        help="Bind port (default: 8000).",
    )
    web_parser.add_argument(
        "--reload",
        action="store_true",
        help="Enable auto-reload for development.",
    )

    return parser


def handle_validate_config(config_file: str) -> int:
    """Handle the validate-config subcommand.

    Args:
        config_file: Path to configuration file.

    Returns:
        0 if configuration is valid, 1 if invalid.
    """
    try:
        config = ResilienceConfig.from_json_file(config_file)
    except (ValueError, TypeError, FileNotFoundError) as err:
        sys.stderr.write(f"Error: Invalid configuration: {err}\n")
        return 1

    sys.stdout.write("Configuration is valid:\n")
    sys.stdout.write(f"  Target URL:             {config.target_url}\n")
    sys.stdout.write(f"  Loopback target:        {config.is_loopback_target}\n")
    sys.stdout.write(f"  Timeout (seconds):      {config.timeout_seconds}\n")
    sys.stdout.write(f"  Request count:          {config.request_count}\n")
    sys.stdout.write(f"  Artificial latency:     {config.artificial_latency_ms} ms\n")
    sys.stdout.write(f"  Failure probability:    {config.failure_probability}\n")
    sys.stdout.write(f"  Total deadline:         {config.total_deadline_seconds} s\n")
    return 0


def handle_scenario_validate(scenario_file: str) -> int:
    """Handle the scenario validate subcommand.

    Args:
        scenario_file: Path to scenario JSON file.

    Returns:
        0 if scenario is valid, 1 if invalid.
    """
    try:
        scenario = Scenario.from_json_file(scenario_file)
    except FileNotFoundError as err:
        sys.stderr.write(f"Error: File not found: {err}\n")
        return 1
    except (ValueError, TypeError) as err:
        sys.stderr.write(f"Error: Invalid scenario: {err}\n")
        return 1

    cfg = scenario.config
    sys.stdout.write(f"Scenario configuration is valid: {scenario.name}\n")
    sys.stdout.write(f"  Name:                   {scenario.name}\n")
    if scenario.description:
        sys.stdout.write(f"  Description:            {scenario.description}\n")
    if scenario.tags:
        sys.stdout.write(f"  Tags:                   {', '.join(scenario.tags)}\n")
    sys.stdout.write(f"  Target URL:             {cfg.target_url}\n")
    sys.stdout.write(f"  Loopback target:        {cfg.is_loopback_target}\n")
    sys.stdout.write(f"  Timeout (seconds):      {cfg.timeout_seconds}\n")
    sys.stdout.write(f"  Request count:          {cfg.request_count}\n")
    sys.stdout.write(f"  Artificial latency:     {cfg.artificial_latency_ms} ms\n")
    sys.stdout.write(f"  Failure probability:    {cfg.failure_probability}\n")
    sys.stdout.write(f"  Total deadline:         {cfg.total_deadline_seconds} s\n")
    if scenario.schedule is not None:
        sys.stdout.write(
            f"  Fault schedule:         {scenario.schedule.schedule_type}\n"
        )
    return 0


def handle_run(
    config_file: str,
    allow_external: bool,
    acknowledge_authorized: bool,
    json_output: bool,
    output_dir: str | None = None,
) -> int:
    """Handle the run subcommand with explicit safety constraints and persistence.

    Args:
        config_file: Path to scenario or configuration file.
        allow_external: Operator flag permitting external host targeting.
        acknowledge_authorized: Operator authorization acknowledgement.
        json_output: Whether to print results as raw JSON.
        output_dir: Optional directory to save the report artifact.

    Returns:
        0 if test run completes, 1 on validation/safety error.
    """
    try:
        scenario = Scenario.from_json_file(config_file)
    except (FileNotFoundError, ValueError, TypeError) as err:
        sys.stderr.write(f"Error: Invalid configuration: {err}\n")
        return 1

    config = scenario.config
    # Apply CLI override flags if provided
    if allow_external:
        config.allow_external = True
    if acknowledge_authorized:
        config.authorized_acknowledgement = True

    if not json_output:
        sys.stdout.write(f"Initiating scenario:     {scenario.name}\n")
        sys.stdout.write(f"  Target URL:            {config.target_url}\n")
        sys.stdout.write(f"  Loopback target:       {config.is_loopback_target}\n")
        sys.stdout.write(f"  Planned requests:      {config.request_count}\n")
        sys.stdout.write(f"  Per-request timeout:   {config.timeout_seconds} s\n")
        sys.stdout.write(
            f"  Total run deadline:    {config.total_deadline_seconds} s\n"
        )
        sys.stdout.write(
            f"  Artificial latency:    {config.artificial_latency_ms} ms\n"
        )
        sys.stdout.write(f"  Failure probability:   {config.failure_probability}\n")
        sys.stdout.write("Running sequentially...\n\n")

    engine = ResilienceEngine()
    try:
        report = engine.run_scenario(scenario)
    except SafetyViolationError as err:
        sys.stderr.write(f"Safety Violation: {err}\n")
        return 1
    except Exception as err:
        sys.stderr.write(f"Execution Error: {err}\n")
        return 1

    saved_path: Path | None = None
    if output_dir:
        try:
            saved_path = save_report(
                report=report, scenario=scenario, output_dir=output_dir
            )
        except Exception as err:
            sys.stderr.write(f"Error: Failed to save execution report: {err}\n")
            return 1

    if json_output:
        sys.stdout.write(json.dumps(report.to_dict(), indent=2) + "\n")
        return 0

    sys.stdout.write("Execution Summary:\n")
    sys.stdout.write(f"  Scenario:               {report.scenario_name}\n")
    sys.stdout.write(f"  Total Requests:         {report.total_requests}\n")
    sys.stdout.write(f"  Successful (2xx):       {report.successful_requests}\n")
    sys.stdout.write(f"  Failed Requests:        {report.failed_requests}\n")
    sys.stdout.write(f"    - HTTP Errors:        {report.http_error_count}\n")
    sys.stdout.write(f"    - Timeouts:           {report.timeout_count}\n")
    sys.stdout.write(f"    - Connection Errors:  {report.connection_error_count}\n")
    sys.stdout.write(f"    - Simulated Faults:   {report.simulated_fault_count}\n")
    sys.stdout.write(f"  Average Latency:        {report.average_latency_ms} ms\n")
    sys.stdout.write(f"  p95 Latency:            {report.p95_latency_ms} ms\n")
    sys.stdout.write(f"  Total Duration:         {report.total_duration_ms} ms\n")
    sys.stdout.write(f"  Interrupted by Deadline:{report.interrupted}\n")
    if saved_path:
        sys.stdout.write(f"  Report Saved:           {saved_path}\n")
    return 0


def handle_reports_list(directory: str) -> int:
    """Handle reports list subcommand.

    Args:
        directory: Directory containing saved report JSON files.

    Returns:
        0 on success.
    """
    reports = list_reports(directory)
    if not reports:
        sys.stdout.write(f"No saved reports found in '{directory}'.\n")
        return 0

    sys.stdout.write(f"Saved Reports (directory: {directory}):\n")
    header = (
        f"{'Run ID':<34} {'Scenario':<18} {'Created At':<22} "
        f"{'Total':<8} {'Success':<8} {'Failed':<8} {'Avg(ms)':<10} {'p95(ms)':<10}"
    )
    sys.stdout.write(f"{header}\n")
    sys.stdout.write(f"{'-' * len(header)}\n")
    for r in reports:
        created_short = r.created_at[:19].replace("T", " ")
        row = (
            f"{r.run_id:<34} {r.scenario_name:<18} {created_short:<22} "
            f"{r.total_requests:<8} {r.successful_requests:<8} {r.failed_requests:<8} "
            f"{r.average_latency_ms:<10.2f} {r.p95_latency_ms:<10.2f}"
        )
        sys.stdout.write(f"{row}\n")
    return 0


def handle_reports_compare(
    baseline_path: str,
    comparison_path: str,
    json_output: bool,
) -> int:
    """Handle reports compare subcommand.

    Args:
        baseline_path: Path to baseline report file.
        comparison_path: Path to comparison report file.
        json_output: Whether to format comparison as JSON.

    Returns:
        0 on success, 1 on file error.
    """
    try:
        baseline_data = load_report(baseline_path)
    except (FileNotFoundError, ValueError) as err:
        sys.stderr.write(f"Error loading baseline report '{baseline_path}': {err}\n")
        return 1

    try:
        comparison_data = load_report(comparison_path)
    except (FileNotFoundError, ValueError) as err:
        sys.stderr.write(
            f"Error loading comparison report '{comparison_path}': {err}\n"
        )
        return 1

    comparison = compare_reports(baseline_data, comparison_data)

    if json_output:
        sys.stdout.write(json.dumps(comparison.to_dict(), indent=2) + "\n")
        return 0

    sys.stdout.write(comparison.format_summary() + "\n")
    return 0


def handle_reports_export(
    report_file: str,
    export_format: str,
    output_file: str | None = None,
) -> int:
    """Handle the reports export subcommand.

    Args:
        report_file: Path to report JSON file.
        export_format: Target format ('prometheus', 'otel', etc.).
        output_file: Optional path where exported output will be written.

    Returns:
        0 on success, 1 on error.
    """
    try:
        exported_text = export_report(report_file, format=export_format)
    except (FileNotFoundError, ValueError, TypeError) as err:
        sys.stderr.write(f"Error exporting report: {err}\n")
        return 1

    if output_file:
        out_path = Path(output_file)
        out_path.parent.mkdir(parents=True, exist_ok=True)
        try:
            out_path.write_text(exported_text, encoding="utf-8")
        except OSError as err:
            sys.stderr.write(f"Error writing export output to '{output_file}': {err}\n")
            return 1
        sys.stdout.write(f"Exported {export_format} metrics to: {out_path}\n")
        return 0

    sys.stdout.write(exported_text)
    return 0


def main(args: Sequence[str] | None = None) -> int:
    """Main CLI entry point.

    Args:
        args: Optional list of command-line arguments. Defaults to sys.argv[1:].

    Returns:
        Exit code (0 on success, non-zero on failure).
    """
    parser = create_parser()
    parsed_args = parser.parse_args(args)

    if parsed_args.command == "validate-config":
        return handle_validate_config(parsed_args.config_file)

    if parsed_args.command == "scenario":
        action = getattr(parsed_args, "scenario_action", None)
        if action == "validate":
            return handle_scenario_validate(parsed_args.scenario_file)
        try:
            parser.parse_args(["scenario", "--help"])
        except SystemExit:
            pass
        return 0

    if parsed_args.command == "run":
        return handle_run(
            config_file=parsed_args.config_file,
            allow_external=parsed_args.allow_external,
            acknowledge_authorized=parsed_args.acknowledge_authorized,
            json_output=parsed_args.json_output,
            output_dir=parsed_args.output_dir,
        )

    if parsed_args.command == "reports":
        action = getattr(parsed_args, "reports_action", None)
        if action == "list":
            return handle_reports_list(parsed_args.directory)
        if action == "compare":
            return handle_reports_compare(
                baseline_path=parsed_args.baseline_report,
                comparison_path=parsed_args.comparison_report,
                json_output=parsed_args.json_output,
            )
        if action == "export":
            return handle_reports_export(
                report_file=parsed_args.report_file,
                export_format=parsed_args.export_format,
                output_file=parsed_args.output_file,
            )
        try:
            parser.parse_args(["reports", "--help"])
        except SystemExit:
            pass
        return 0

    if parsed_args.command == "web":
        return handle_web(
            host=parsed_args.host,
            port=parsed_args.port,
            reload=parsed_args.reload,
        )

    # If no subcommand was provided, display help and exit cleanly
    parser.print_help()
    return 0


def handle_web(host: str, port: int, reload: bool = False) -> int:
    """Launch the ForgeFit FastAPI server via uvicorn."""
    try:
        import uvicorn
    except ImportError:
        sys.stderr.write(
            "Error: 'uvicorn' is required to run the ForgeFit web application.\n"
            "Install it via: pip install 'forgefit[web]' or pip install uvicorn\n"
        )
        return 1

    sys.stdout.write(f"Starting ForgeFit Web Application on http://{host}:{port}\n")
    uvicorn.run("forgefit.api:app", host=host, port=port, reload=reload)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
