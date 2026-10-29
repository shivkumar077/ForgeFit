"""Report persistence, listing, and comparison for ForgeFit resilience runs."""

from __future__ import annotations

import json
import os
import re
import uuid
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from forgefit.models import ResilienceReport, Scenario


def generate_run_id() -> str:
    """Generate a unique, human-readable run identifier with timestamp.

    Returns:
        Formatted run ID like 'run_20261030_120000_a1b2c3d4'.
    """
    now_str = datetime.now(UTC).strftime("%Y%m%d_%H%M%S")
    rand_hex = uuid.uuid4().hex[:8]
    return f"run_{now_str}_{rand_hex}"


def sanitize_filename(name: str) -> str:
    """Sanitize a scenario or run name for use in filesystem paths.

    Prevents path traversal and removes unsafe characters.

    Args:
        name: Raw name or identifier.

    Returns:
        Safe string containing only alphanumeric characters, underscores, and hyphens.
    """
    clean = re.sub(r"[^a-zA-Z0-9_\-]", "_", name.strip())
    clean = re.sub(r"_+", "_", clean).strip("_")
    return clean[:64] or "run"


def build_config_summary(
    scenario: Scenario | None,
    report: ResilienceReport,
) -> dict[str, Any]:
    """Extract a sanitized, serializable configuration summary.

    Avoids storing credentials, sensitive headers, or internal tokens.

    Args:
        scenario: Optional executed Scenario.
        report: ResilienceReport containing execution metadata.

    Returns:
        Dictionary of non-sensitive configuration parameters.
    """
    if scenario and scenario.config:
        cfg = scenario.config
        summary = {
            "target_url": cfg.target_url,
            "timeout_seconds": cfg.timeout_seconds,
            "request_count": cfg.request_count,
            "artificial_latency_ms": cfg.artificial_latency_ms,
            "failure_probability": cfg.failure_probability,
            "total_deadline_seconds": cfg.total_deadline_seconds,
            "is_loopback_target": cfg.is_loopback_target,
            "allow_external": cfg.allow_external,
            "seed": cfg.seed,
        }
        if scenario.schedule is not None:
            summary["schedule"] = scenario.schedule.to_dict()
        return summary

    # Fallback to metadata if scenario instance is not directly provided
    meta_cfg = report.metadata.get("config", {})
    if isinstance(meta_cfg, dict):
        return {
            "target_url": meta_cfg.get("target_url"),
            "timeout_seconds": meta_cfg.get("timeout_seconds"),
            "request_count": meta_cfg.get("request_count"),
            "artificial_latency_ms": meta_cfg.get("artificial_latency_ms"),
            "failure_probability": meta_cfg.get("failure_probability"),
            "total_deadline_seconds": meta_cfg.get("total_deadline_seconds"),
            "is_loopback_target": meta_cfg.get("is_loopback_target"),
            "allow_external": meta_cfg.get("allow_external", False),
            "seed": meta_cfg.get("seed"),
        }

    return {}


def save_report(
    report: ResilienceReport,
    scenario: Scenario | None = None,
    output_dir: str | Path = "reports",
    run_id: str | None = None,
) -> Path:
    """Save a completed execution report to disk as JSON atomically.

    Guarantees:
    - Never silently overwrites an existing report file.
    - Prevents path traversal via scenario name or run ID.
    - Uses atomic write (temp file + replace) to prevent partial/corrupt files.
    - Omits sensitive request/response bodies and credentials.

    Args:
        report: Completed ResilienceReport to save.
        scenario: Optional Scenario that produced the report.
        output_dir: Directory where report will be persisted.
        run_id: Optional unique identifier. Generated automatically if omitted.

    Returns:
        Path to the saved report file.

    Raises:
        ValueError: If run_id contains invalid path characters or traversal.
        FileExistsError: If a report with the same filename already exists.
        IOError: If writing the report fails.
    """
    assigned_run_id = run_id or generate_run_id()
    if "/" in assigned_run_id or "\\" in assigned_run_id or ".." in assigned_run_id:
        raise ValueError(
            f"Invalid run_id '{assigned_run_id}': "
            "cannot contain path separators or '..'"
        )

    safe_scenario = sanitize_filename(report.scenario_name)
    safe_run_id = sanitize_filename(assigned_run_id)
    filename = f"report_{safe_scenario}_{safe_run_id}.json"

    out_dir_path = Path(output_dir).resolve()

    # Guard against path traversal
    target_path = (out_dir_path / filename).resolve()
    try:
        target_path.relative_to(out_dir_path)
    except ValueError as err:
        raise ValueError(
            f"Path traversal detected in report target path: {filename}"
        ) from err

    out_dir_path.mkdir(parents=True, exist_ok=True)

    if target_path.exists():
        raise FileExistsError(
            f"Report file already exists and will not be overwritten: {target_path}"
        )

    payload = {
        "schema_version": 1,
        "run_id": assigned_run_id,
        "scenario_name": report.scenario_name,
        "created_at": datetime.now(UTC).isoformat(),
        "config_summary": build_config_summary(scenario, report),
        "report": report.to_dict(),
    }

    # Atomic write pattern: write to hidden temp file, flush, sync, then replace
    temp_filename = f".{filename}.tmp_{uuid.uuid4().hex[:8]}"
    temp_path = out_dir_path / temp_filename

    try:
        with open(temp_path, "w", encoding="utf-8") as f:
            json.dump(payload, f, indent=2)
            f.write("\n")
            f.flush()
            os.fsync(f.fileno())

        os.replace(temp_path, target_path)
    except Exception as err:
        if temp_path.exists():
            temp_path.unlink(missing_ok=True)
        raise OSError(
            f"Failed to save execution report to '{target_path}': {err}"
        ) from err

    return target_path


def load_report(file_path: str | Path) -> dict[str, Any]:
    """Load and validate a saved execution report from JSON.

    Args:
        file_path: Path to the JSON report file.

    Returns:
        Validated report dictionary containing 'run_id', 'created_at', and 'report'.

    Raises:
        FileNotFoundError: If the specified file does not exist.
        ValueError: If file content is invalid JSON or does not match report schema.
    """
    path = Path(file_path)
    if not path.is_file():
        raise FileNotFoundError(f"Report file not found: {path}")

    try:
        with open(path, encoding="utf-8") as f:
            data = json.load(f)
    except json.JSONDecodeError as err:
        raise ValueError(f"Malformed JSON in report file '{path}': {err}") from err

    if not isinstance(data, dict):
        raise ValueError(
            f"Report root must be a JSON object, got {type(data).__name__}"
        )

    # Validate required top-level fields
    for field_name in ("run_id", "scenario_name", "created_at", "report"):
        if field_name not in data:
            raise ValueError(
                f"Invalid report schema in '{path}': "
                f"missing required field '{field_name}'"
            )

    report_data = data["report"]
    if not isinstance(report_data, dict):
        raise ValueError(
            f"Invalid report schema in '{path}': 'report' field must be a dictionary"
        )

    # Validate required metrics within report dictionary
    required_metrics = (
        "total_requests",
        "successful_requests",
        "failed_requests",
        "average_latency_ms",
        "p95_latency_ms",
        "outcomes",
    )
    for metric in required_metrics:
        if metric not in report_data:
            raise ValueError(
                f"Invalid report schema in '{path}': report missing metric '{metric}'"
            )

    return data


@dataclass(slots=True)
class ReportSummary:
    """Summary of a saved execution report for directory listings.

    Attributes:
        run_id: Unique execution run ID.
        scenario_name: Name of the executed scenario.
        created_at: ISO-8601 creation timestamp string.
        total_requests: Total number of requests executed.
        successful_requests: Number of successful requests (2xx).
        failed_requests: Number of failed requests.
        average_latency_ms: Average latency across outcomes.
        p95_latency_ms: 95th percentile latency.
        file_path: Filesystem path to the report artifact.
    """

    run_id: str
    scenario_name: str
    created_at: str
    total_requests: int
    successful_requests: int
    failed_requests: int
    average_latency_ms: float
    p95_latency_ms: float
    file_path: Path


def list_reports(directory: str | Path = "reports") -> list[ReportSummary]:
    """Scan a directory for saved reports and return summaries ordered by creation date.

    Args:
        directory: Directory to search for report JSON files.

    Returns:
        List of ReportSummary objects, sorted newest to oldest.
    """
    dir_path = Path(directory)
    if not dir_path.is_dir():
        return []

    summaries: list[ReportSummary] = []
    for file_path in dir_path.glob("*.json"):
        if file_path.name.startswith("."):
            continue
        try:
            data = load_report(file_path)
            rep = data["report"]
            summary = ReportSummary(
                run_id=str(data.get("run_id", "")),
                scenario_name=str(data.get("scenario_name", "unknown")),
                created_at=str(data.get("created_at", "")),
                total_requests=int(rep.get("total_requests", 0)),
                successful_requests=int(rep.get("successful_requests", 0)),
                failed_requests=int(rep.get("failed_requests", 0)),
                average_latency_ms=float(rep.get("average_latency_ms", 0.0)),
                p95_latency_ms=float(rep.get("p95_latency_ms", 0.0)),
                file_path=file_path,
            )
            summaries.append(summary)
        except Exception:
            # Skip files that are not valid ForgeFit reports
            continue

    # Sort descending by creation timestamp (newest first)
    summaries.sort(key=lambda s: s.created_at, reverse=True)
    return summaries


@dataclass(slots=True)
class MetricDelta:
    """Detailed comparison of a single metric between baseline and comparison runs.

    Attributes:
        metric_name: Label of the metric.
        baseline: Value recorded in baseline run.
        comparison: Value recorded in comparison run.
        absolute_diff: Absolute change (comparison - baseline).
        percentage_diff: Percentage change relative to baseline, or None
            if baseline was 0.
        direction: Evaluated direction: 'improved', 'degraded', 'unchanged',
            or 'neutral'.
        interpretation: Human-readable explanation of what the change signifies.
    """

    metric_name: str
    baseline: float | int
    comparison: float | int
    absolute_diff: float
    percentage_diff: float | None
    direction: str
    interpretation: str

    def to_dict(self) -> dict[str, Any]:
        """Serialize delta to dictionary."""
        return {
            "metric_name": self.metric_name,
            "baseline": self.baseline,
            "comparison": self.comparison,
            "absolute_diff": round(self.absolute_diff, 2),
            "percentage_diff": (
                round(self.percentage_diff, 2)
                if self.percentage_diff is not None
                else None
            ),
            "direction": self.direction,
            "interpretation": self.interpretation,
        }


@dataclass(slots=True)
class ReportComparison:
    """Comprehensive comparison between baseline and comparison execution reports.

    Attributes:
        baseline_run_id: Identifier of the baseline run.
        comparison_run_id: Identifier of the comparison run.
        baseline_scenario: Name of baseline scenario.
        comparison_scenario: Name of comparison scenario.
        warnings: List of caveats or warnings (e.g. differing targets or configs).
        notes: List of general analytical notes (e.g. small sample size caveats).
        metrics: Dictionary mapping metric keys to MetricDelta instances.
    """

    baseline_run_id: str
    comparison_run_id: str
    baseline_scenario: str
    comparison_scenario: str
    warnings: list[str]
    notes: list[str]
    metrics: dict[str, MetricDelta]

    def to_dict(self) -> dict[str, Any]:
        """Serialize comparison to JSON-compatible dictionary."""
        return {
            "baseline_run_id": self.baseline_run_id,
            "comparison_run_id": self.comparison_run_id,
            "baseline_scenario": self.baseline_scenario,
            "comparison_scenario": self.comparison_scenario,
            "warnings": list(self.warnings),
            "notes": list(self.notes),
            "metrics": {k: m.to_dict() for k, m in self.metrics.items()},
        }

    def format_summary(self) -> str:
        """Format comparison as an aligned human-readable text table."""
        header_fmt = (
            f"{'Metric':<24} {'Baseline':<12} {'Comparison':<12} "
            f"{'Diff':<10} {'Change %':<10} {'Assessment':<14}"
        )
        lines: list[str] = [
            "=" * 84,
            "ForgeFit Resilience Run Comparison",
            "=" * 84,
            f"Baseline:   {self.baseline_run_id} ({self.baseline_scenario})",
            f"Comparison: {self.comparison_run_id} ({self.comparison_scenario})",
            "",
            header_fmt,
            "-" * 84,
        ]

        for _, m in self.metrics.items():
            b_str = (
                f"{m.baseline:.2f}"
                if isinstance(m.baseline, float)
                else str(m.baseline)
            )
            c_str = (
                f"{m.comparison:.2f}"
                if isinstance(m.comparison, float)
                else str(m.comparison)
            )

            sign = "+" if m.absolute_diff > 0 else ""
            diff_str = (
                f"{sign}{m.absolute_diff:.2f}"
                if isinstance(m.absolute_diff, float)
                else f"{sign}{m.absolute_diff}"
            )
            if m.metric_name.endswith("(%)"):
                diff_str += "%"

            if m.percentage_diff is not None:
                p_sign = "+" if m.percentage_diff > 0 else ""
                pct_str = f"{p_sign}{m.percentage_diff:.1f}%"
            else:
                pct_str = "N/A"

            assess_str = m.direction.capitalize()
            row = (
                f"{m.metric_name:<24} {b_str:<12} {c_str:<12} "
                f"{diff_str:<10} {pct_str:<10} {assess_str:<14}"
            )
            lines.append(row)

        lines.append("=" * 84)

        if self.warnings:
            lines.append("Warnings:")
            for w in self.warnings:
                lines.append(f"  * {w}")
            lines.append("")

        if self.notes:
            lines.append("Notes:")
            for n in self.notes:
                lines.append(f"  * {n}")
            lines.append("")

        lines.append("Metric Direction Rules:")
        lines.append("  * Latency: Lower is favorable (negative delta = improved).")
        lines.append(
            "  * Success Rate: Higher is favorable (positive delta = improved)."
        )
        lines.append(
            "  * Failures/Errors: Lower is favorable (negative delta = improved)."
        )
        return "\n".join(lines)


def _calc_delta(
    name: str,
    baseline: float | int,
    comparison: float | int,
    lower_is_better: bool | None = None,
) -> MetricDelta:
    """Compute difference, percentage change, and directional evaluation."""
    diff = round(float(comparison) - float(baseline), 2)

    if baseline != 0:
        pct = round(((comparison - baseline) / abs(baseline)) * 100.0, 2)
    else:
        pct = None

    if lower_is_better is True:
        if diff < 0:
            direction = "improved"
            interp = f"{name} decreased by {abs(diff)} (improved)"
        elif diff > 0:
            direction = "degraded"
            interp = f"{name} increased by {diff} (degraded)"
        else:
            direction = "unchanged"
            interp = f"{name} remained identical"
    elif lower_is_better is False:
        if diff > 0:
            direction = "improved"
            interp = f"{name} increased by {diff} (improved)"
        elif diff < 0:
            direction = "degraded"
            interp = f"{name} decreased by {abs(diff)} (degraded)"
        else:
            direction = "unchanged"
            interp = f"{name} remained identical"
    else:
        direction = "neutral"
        if diff == 0:
            interp = f"{name} remained identical"
        elif diff > 0:
            interp = f"{name} increased by {diff}"
        else:
            interp = f"{name} decreased by {abs(diff)}"

    return MetricDelta(
        metric_name=name,
        baseline=baseline,
        comparison=comparison,
        absolute_diff=diff,
        percentage_diff=pct,
        direction=direction,
        interpretation=interp,
    )


def compare_reports(
    baseline: str | Path | dict[str, Any],
    comparison: str | Path | dict[str, Any],
) -> ReportComparison:
    """Compare two execution reports (paths or loaded dicts) and evaluate deltas.

    Args:
        baseline: File path or loaded dictionary for the baseline report.
        comparison: File path or loaded dictionary for the comparison report.

    Returns:
        Structured ReportComparison instance.
    """
    baseline_data = (
        load_report(baseline) if isinstance(baseline, (str, Path)) else baseline
    )
    comparison_data = (
        load_report(comparison) if isinstance(comparison, (str, Path)) else comparison
    )
    b_rep = baseline_data["report"]
    c_rep = comparison_data["report"]

    b_total = int(b_rep.get("total_requests", 0))
    c_total = int(c_rep.get("total_requests", 0))

    b_succ = int(b_rep.get("successful_requests", 0))
    c_succ = int(c_rep.get("successful_requests", 0))

    b_failed = int(b_rep.get("failed_requests", 0))
    c_failed = int(c_rep.get("failed_requests", 0))

    b_rate = round((b_succ / b_total * 100.0), 2) if b_total > 0 else 0.0
    c_rate = round((c_succ / c_total * 100.0), 2) if c_total > 0 else 0.0

    metrics: dict[str, MetricDelta] = {
        "total_requests": _calc_delta(
            "Total Requests", b_total, c_total, lower_is_better=None
        ),
        "successful_requests": _calc_delta(
            "Successful Requests", b_succ, c_succ, lower_is_better=False
        ),
        "failed_requests": _calc_delta(
            "Failed Requests", b_failed, c_failed, lower_is_better=True
        ),
        "success_rate": _calc_delta(
            "Success Rate (%)", b_rate, c_rate, lower_is_better=False
        ),
        "http_error_count": _calc_delta(
            "HTTP Errors",
            int(b_rep.get("http_error_count", 0)),
            int(c_rep.get("http_error_count", 0)),
            lower_is_better=True,
        ),
        "timeout_count": _calc_delta(
            "Timeouts",
            int(b_rep.get("timeout_count", 0)),
            int(c_rep.get("timeout_count", 0)),
            lower_is_better=True,
        ),
        "connection_error_count": _calc_delta(
            "Connection Errors",
            int(b_rep.get("connection_error_count", 0)),
            int(c_rep.get("connection_error_count", 0)),
            lower_is_better=True,
        ),
        "simulated_fault_count": _calc_delta(
            "Simulated Faults",
            int(b_rep.get("simulated_fault_count", 0)),
            int(c_rep.get("simulated_fault_count", 0)),
            lower_is_better=None,
        ),
        "average_latency_ms": _calc_delta(
            "Average Latency (ms)",
            float(b_rep.get("average_latency_ms", 0.0)),
            float(c_rep.get("average_latency_ms", 0.0)),
            lower_is_better=True,
        ),
        "p95_latency_ms": _calc_delta(
            "p95 Latency (ms)",
            float(b_rep.get("p95_latency_ms", 0.0)),
            float(c_rep.get("p95_latency_ms", 0.0)),
            lower_is_better=True,
        ),
    }

    warnings: list[str] = []
    notes: list[str] = []

    # Check for scenario and target divergence
    b_cfg = baseline_data.get("config_summary", {})
    c_cfg = comparison_data.get("config_summary", {})
    if b_cfg and c_cfg:
        if b_cfg.get("target_url") != c_cfg.get("target_url"):
            warnings.append(
                f"Target URLs differ between runs: baseline targeted "
                f"'{b_cfg.get('target_url')}' while comparison targeted "
                f"'{c_cfg.get('target_url')}'."
            )
        if b_cfg.get("timeout_seconds") != c_cfg.get("timeout_seconds"):
            warnings.append(
                f"Timeout settings differ: {b_cfg.get('timeout_seconds')}s "
                f"vs {c_cfg.get('timeout_seconds')}s."
            )
        if b_cfg.get("artificial_latency_ms") != c_cfg.get("artificial_latency_ms"):
            warnings.append(
                f"Artificial latency settings differ: "
                f"{b_cfg.get('artificial_latency_ms')}ms vs "
                f"{c_cfg.get('artificial_latency_ms')}ms."
            )
        if b_cfg.get("failure_probability") != c_cfg.get("failure_probability"):
            warnings.append(
                f"Failure probability settings differ: "
                f"{b_cfg.get('failure_probability')} vs "
                f"{c_cfg.get('failure_probability')}."
            )

    b_name = baseline_data.get("scenario_name", "baseline")
    c_name = comparison_data.get("scenario_name", "comparison")
    if b_name != c_name:
        warnings.append(
            f"Scenario names differ: '{b_name}' vs '{c_name}'. "
            "Results may represent different workloads."
        )

    # Note small sample size if applicable
    if b_total < 30 or c_total < 30:
        notes.append(
            f"Sample size is small (baseline={b_total}, "
            f"comparison={c_total} requests). Differences should be validated "
            "across larger runs and not presumed statistically significant."
        )

    return ReportComparison(
        baseline_run_id=str(baseline_data.get("run_id", "baseline")),
        comparison_run_id=str(comparison_data.get("run_id", "comparison")),
        baseline_scenario=b_name,
        comparison_scenario=c_name,
        warnings=warnings,
        notes=notes,
        metrics=metrics,
    )
