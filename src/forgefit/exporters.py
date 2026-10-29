"""Metrics exporters for ForgeFit reports (Prometheus & OpenTelemetry)."""

from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from forgefit.reports import load_report


def _escape_prometheus_label(val: Any) -> str:
    """Escape label values according to Prometheus text format standards."""
    s = str(val)
    return s.replace("\\", "\\\\").replace('"', '\\"').replace("\n", "\\n")


def _parse_time_unix_nano(iso_str: str | None) -> int:
    """Parse ISO timestamp to Unix timestamp in nanoseconds, default to now."""
    if not iso_str:
        return int(datetime.now(UTC).timestamp() * 1_000_000_000)
    try:
        dt = datetime.fromisoformat(iso_str.replace("Z", "+00:00"))
        return int(dt.timestamp() * 1_000_000_000)
    except Exception:
        return int(datetime.now(UTC).timestamp() * 1_000_000_000)


def export_prometheus(report_data: dict[str, Any]) -> str:
    """Export report metrics to Prometheus text exposition format.

    Args:
        report_data: Validated ForgeFit report dictionary.

    Returns:
        String formatted in Prometheus text exposition format.

    Raises:
        ValueError: If report dictionary is missing required structure.
    """
    if not isinstance(report_data, dict) or "report" not in report_data:
        raise ValueError("Invalid report structure: missing 'report' data")

    run_id = str(report_data.get("run_id", "unknown"))
    scenario_name = str(report_data.get("scenario_name", "unknown"))
    rep = report_data["report"]
    if not isinstance(rep, dict):
        raise ValueError("Invalid report structure: 'report' must be a dictionary")

    esc_run_id = _escape_prometheus_label(run_id)
    esc_scenario = _escape_prometheus_label(scenario_name)
    base_labels = f'run_id="{esc_run_id}",scenario="{esc_scenario}"'

    lines: list[str] = [
        "# HELP forgefit_requests_total Total resilience requests executed.",
        "# TYPE forgefit_requests_total counter",
    ]

    total_requests = rep.get("total_requests")
    if total_requests is not None:
        lines.append(f"forgefit_requests_total{{{base_labels}}} {int(total_requests)}")

    successful = rep.get("successful_requests")
    if successful is not None:
        lines.extend(
            [
                "# HELP forgefit_requests_success_total Total successful requests.",
                "# TYPE forgefit_requests_success_total counter",
                f"forgefit_requests_success_total{{{base_labels}}} {int(successful)}",
            ]
        )

    failed = rep.get("failed_requests")
    if failed is not None:
        lines.extend(
            [
                "# HELP forgefit_requests_failed_total Total failed requests.",
                "# TYPE forgefit_requests_failed_total counter",
                f"forgefit_requests_failed_total{{{base_labels}}} {int(failed)}",
            ]
        )

    # Failure category breakdown
    lines.extend(
        [
            "# HELP forgefit_requests_by_category_total Requests by failure category.",
            "# TYPE forgefit_requests_by_category_total counter",
        ]
    )
    categories = [
        ("http_error", rep.get("http_error_count", 0)),
        ("timeout", rep.get("timeout_count", 0)),
        ("connection_error", rep.get("connection_error_count", 0)),
        ("simulated_fault", rep.get("simulated_fault_count", 0)),
    ]
    for cat, count in categories:
        if count is not None:
            lbl = f'{base_labels},category="{cat}"'
            lines.append(f"forgefit_requests_by_category_total{{{lbl}}} {int(count)}")

    # Latencies in seconds (Prometheus standard base unit)
    avg_latency = rep.get("average_latency_ms")
    if avg_latency is not None:
        avg_s = round(float(avg_latency) / 1000.0, 6)
        lines.extend(
            [
                "# HELP forgefit_request_latency_average_seconds Mean latency in s.",
                "# TYPE forgefit_request_latency_average_seconds gauge",
                f"forgefit_request_latency_average_seconds{{{base_labels}}} {avg_s}",
            ]
        )

    p95_latency = rep.get("p95_latency_ms")
    if p95_latency is not None:
        p95_s = round(float(p95_latency) / 1000.0, 6)
        lines.extend(
            [
                "# HELP forgefit_request_latency_p95_seconds 95th percentile in s.",
                "# TYPE forgefit_request_latency_p95_seconds gauge",
                f"forgefit_request_latency_p95_seconds{{{base_labels}}} {p95_s}",
            ]
        )

    duration = rep.get("total_duration_ms")
    if duration is not None:
        duration_s = round(float(duration) / 1000.0, 4)
        lines.extend(
            [
                "# HELP forgefit_execution_duration_seconds Total duration in s.",
                "# TYPE forgefit_execution_duration_seconds gauge",
                f"forgefit_execution_duration_seconds{{{base_labels}}} {duration_s}",
            ]
        )

    # Success rate ratio (0.0 to 1.0)
    if total_requests and int(total_requests) > 0 and successful is not None:
        rate_ratio = round(float(successful) / float(total_requests), 4)
        lines.extend(
            [
                "# HELP forgefit_success_rate_ratio Successful request ratio.",
                "# TYPE forgefit_success_rate_ratio gauge",
                f"forgefit_success_rate_ratio{{{base_labels}}} {rate_ratio}",
            ]
        )

    return "\n".join(lines) + "\n"


def export_opentelemetry(report_data: dict[str, Any]) -> dict[str, Any]:
    """Export report metrics to OpenTelemetry-compatible JSON metrics structure.

    Conforms to OpenTelemetry Metrics Data Model (OTLP JSON).

    Args:
        report_data: Validated ForgeFit report dictionary.

    Returns:
        Dictionary conforming to OpenTelemetry JSON metrics structure.

    Raises:
        ValueError: If report dictionary is missing required structure.
    """
    if not isinstance(report_data, dict) or "report" not in report_data:
        raise ValueError("Invalid report structure: missing 'report' data")

    run_id = str(report_data.get("run_id", "unknown"))
    scenario_name = str(report_data.get("scenario_name", "unknown"))
    created_at = report_data.get("created_at")
    time_nano = _parse_time_unix_nano(created_at)

    rep = report_data["report"]
    if not isinstance(rep, dict):
        raise ValueError("Invalid report structure: 'report' must be a dictionary")

    metrics_list: list[dict[str, Any]] = []

    total_requests = rep.get("total_requests")
    if total_requests is not None:
        metrics_list.append(
            {
                "name": "forgefit.requests.total",
                "description": "Total number of resilience requests executed",
                "unit": "{requests}",
                "sum": {
                    "aggregationTemporality": "AGGREGATION_TEMPORALITY_CUMULATIVE",
                    "isMonotonic": True,
                    "dataPoints": [
                        {
                            "asInt": int(total_requests),
                            "timeUnixNano": time_nano,
                        }
                    ],
                },
            }
        )

    successful = rep.get("successful_requests")
    if successful is not None:
        metrics_list.append(
            {
                "name": "forgefit.requests.success",
                "description": "Total successful (2xx, no fault) requests",
                "unit": "{requests}",
                "sum": {
                    "aggregationTemporality": "AGGREGATION_TEMPORALITY_CUMULATIVE",
                    "isMonotonic": True,
                    "dataPoints": [
                        {
                            "asInt": int(successful),
                            "timeUnixNano": time_nano,
                        }
                    ],
                },
            }
        )

    failed = rep.get("failed_requests")
    if failed is not None:
        metrics_list.append(
            {
                "name": "forgefit.requests.failed",
                "description": "Total failed requests across all failure categories",
                "unit": "{requests}",
                "sum": {
                    "aggregationTemporality": "AGGREGATION_TEMPORALITY_CUMULATIVE",
                    "isMonotonic": True,
                    "dataPoints": [
                        {
                            "asInt": int(failed),
                            "timeUnixNano": time_nano,
                        }
                    ],
                },
            }
        )

    # Category breakdown data points
    category_data_points = []
    categories = [
        ("http_error", rep.get("http_error_count", 0)),
        ("timeout", rep.get("timeout_count", 0)),
        ("connection_error", rep.get("connection_error_count", 0)),
        ("simulated_fault", rep.get("simulated_fault_count", 0)),
    ]
    for cat, count in categories:
        if count is not None:
            category_data_points.append(
                {
                    "asInt": int(count),
                    "timeUnixNano": time_nano,
                    "attributes": [{"key": "category", "value": {"stringValue": cat}}],
                }
            )

    if category_data_points:
        metrics_list.append(
            {
                "name": "forgefit.requests.by_category",
                "description": "Requests partitioned by failure category",
                "unit": "{requests}",
                "sum": {
                    "aggregationTemporality": "AGGREGATION_TEMPORALITY_CUMULATIVE",
                    "isMonotonic": True,
                    "dataPoints": category_data_points,
                },
            }
        )

    # Latencies in seconds
    avg_latency = rep.get("average_latency_ms")
    if avg_latency is not None:
        metrics_list.append(
            {
                "name": "forgefit.request.latency.average",
                "description": "Mean request response latency in seconds",
                "unit": "s",
                "gauge": {
                    "dataPoints": [
                        {
                            "asDouble": round(float(avg_latency) / 1000.0, 6),
                            "timeUnixNano": time_nano,
                        }
                    ]
                },
            }
        )

    p95_latency = rep.get("p95_latency_ms")
    if p95_latency is not None:
        metrics_list.append(
            {
                "name": "forgefit.request.latency.p95",
                "description": "95th percentile request latency in seconds",
                "unit": "s",
                "gauge": {
                    "dataPoints": [
                        {
                            "asDouble": round(float(p95_latency) / 1000.0, 6),
                            "timeUnixNano": time_nano,
                        }
                    ]
                },
            }
        )

    duration = rep.get("total_duration_ms")
    if duration is not None:
        metrics_list.append(
            {
                "name": "forgefit.execution.duration",
                "description": "Total scenario execution duration in seconds",
                "unit": "s",
                "gauge": {
                    "dataPoints": [
                        {
                            "asDouble": round(float(duration) / 1000.0, 4),
                            "timeUnixNano": time_nano,
                        }
                    ]
                },
            }
        )

    if total_requests and int(total_requests) > 0 and successful is not None:
        metrics_list.append(
            {
                "name": "forgefit.success_rate",
                "description": "Ratio of successful requests (0.0 to 1.0)",
                "unit": "1",
                "gauge": {
                    "dataPoints": [
                        {
                            "asDouble": round(
                                float(successful) / float(total_requests), 4
                            ),
                            "timeUnixNano": time_nano,
                        }
                    ]
                },
            }
        )

    return {
        "resourceMetrics": [
            {
                "resource": {
                    "attributes": [
                        {"key": "service.name", "value": {"stringValue": "forgefit"}},
                        {"key": "forgefit.run_id", "value": {"stringValue": run_id}},
                        {
                            "key": "forgefit.scenario_name",
                            "value": {"stringValue": scenario_name},
                        },
                    ]
                },
                "scopeMetrics": [
                    {
                        "scope": {
                            "name": "forgefit.resilience",
                            "version": "1.0.0",
                        },
                        "metrics": metrics_list,
                    }
                ],
            }
        ]
    }


def export_report(
    report_input: dict[str, Any] | str | Path,
    format: str = "prometheus",
) -> str:
    """Export a ForgeFit execution report to the specified metrics exposition format.

    Args:
        report_input: Loaded report dictionary or file path to report JSON.
        format: Export format: 'prometheus' or 'otel' / 'opentelemetry'.

    Returns:
        Formatted string (Prometheus text or OpenTelemetry JSON).

    Raises:
        FileNotFoundError: If a report path is specified and does not exist.
        ValueError: If format is unsupported or report content is invalid.
    """
    if isinstance(report_input, (str, Path)):
        data = load_report(report_input)
    elif isinstance(report_input, dict):
        data = report_input
    else:
        t = type(report_input).__name__
        raise TypeError(f"report_input must be a dict, str, or Path, got {t}")

    fmt = format.strip().lower()
    if fmt in ("prometheus", "prom"):
        return export_prometheus(data)

    if fmt in ("otel", "opentelemetry"):
        otel_data = export_opentelemetry(data)
        return json.dumps(otel_data, indent=2) + "\n"

    raise ValueError(
        f"Unsupported export format '{format}'. "
        "Supported formats are: 'prometheus', 'otel'."
    )
