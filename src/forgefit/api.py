"""FastAPI backend application for ForgeFit resilience testing toolkit."""

from __future__ import annotations

import logging
import os
import re
import secrets
import threading
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from fastapi import Depends, FastAPI, Header, HTTPException, Query, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, PlainTextResponse
from fastapi.staticfiles import StaticFiles

from forgefit import __version__
from forgefit.engine import ResilienceEngine, SafetyViolationError
from forgefit.exporters import export_opentelemetry, export_prometheus
from forgefit.models import RequestOutcome, Scenario
from forgefit.reports import (
    compare_reports,
    generate_run_id,
    list_reports,
    load_report,
    sanitize_filename,
    save_report,
)

logger = logging.getLogger("forgefit.api")

app = FastAPI(
    title="ForgeFit API",
    description="Backend API for ForgeFit Resilience Testing Toolkit",
    version=__version__,
)

DEFAULT_CORS_ORIGINS = [
    "http://localhost:5173",
    "http://127.0.0.1:5173",
    "http://localhost:3000",
    "http://127.0.0.1:3000",
    "http://localhost:8000",
    "http://127.0.0.1:8000",
    "http://localhost:8001",
    "http://127.0.0.1:8001",
]


def get_cors_origins() -> list[str]:
    """Return explicit (non-wildcard) origins from FORGEFIT_CORS_ORIGINS.

    Falls back to local development origins when unset or empty.
    """
    raw = os.getenv("FORGEFIT_CORS_ORIGINS", "").strip()
    if not raw:
        return list(DEFAULT_CORS_ORIGINS)
    origins = [
        o.strip().rstrip("/") for o in raw.split(",") if o.strip() and "*" not in o
    ]
    return origins if origins else list(DEFAULT_CORS_ORIGINS)


def get_cors_origin_regex() -> str | None:
    """Return regex pattern for wildcard origins or explicit origin regex.

    Supports wildcard domain patterns like 'https://*.vercel.app' in
    FORGEFIT_CORS_ORIGINS and explicit regex in FORGEFIT_CORS_ORIGIN_REGEX.
    """
    regex_parts: list[str] = []

    explicit_regex = os.getenv("FORGEFIT_CORS_ORIGIN_REGEX", "").strip()
    if explicit_regex:
        regex_parts.append(f"(?:{explicit_regex})")

    raw = os.getenv("FORGEFIT_CORS_ORIGINS", "").strip()
    if raw:
        for entry in raw.split(","):
            cleaned = entry.strip().rstrip("/")
            if cleaned and cleaned != "*" and "*" in cleaned:
                pattern = rf"^{re.escape(cleaned).replace(r'\*', r'.*')}$"
                regex_parts.append(f"(?:{pattern})")

    if not regex_parts:
        return None
    return "|".join(regex_parts)


# Configure CORS with explicit allowed origins and wildcard pattern regex
app.add_middleware(
    CORSMiddleware,
    allow_origins=get_cors_origins(),
    allow_origin_regex=get_cors_origin_regex(),
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


def verify_api_key(
    x_forgefit_api_key: str | None = Header(None, alias="X-ForgeFit-API-Key"),
) -> None:
    """Verify shared API key authentication for protected operations.

    Active only when FORGEFIT_API_KEY is configured in the environment.
    Uses constant-time comparison to protect against timing attacks.
    """
    configured_key = os.getenv("FORGEFIT_API_KEY", "").strip()
    if not configured_key:
        return  # Unprotected when FORGEFIT_API_KEY is not set

    if not x_forgefit_api_key:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Missing required X-ForgeFit-API-Key header",
        )

    if not secrets.compare_digest(x_forgefit_api_key, configured_key):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid X-ForgeFit-API-Key header",
        )


def get_configured_reports_dir() -> Path:
    """Return the canonical reports directory configured by FORGEFIT_REPORTS_DIR.

    Defaults to 'reports' in the current working directory.
    Creates the directory if it does not exist.
    """
    raw = os.getenv("FORGEFIT_REPORTS_DIR", "").strip()
    if raw:
        path = Path(raw).resolve()
    else:
        path = (Path.cwd() / "reports").resolve()
    path.mkdir(parents=True, exist_ok=True)
    return path


def _resolve_reports_directory(requested_dir: str | Path | None = None) -> Path:
    """Resolve report directory safely.

    If FORGEFIT_REPORTS_DIR is explicitly configured in the environment
    (e.g. Render persistent disk), that canonical directory is strictly
    enforced and cannot be overridden by arbitrary browser-supplied
    filesystem paths.

    When FORGEFIT_REPORTS_DIR is not set (e.g. local development or pytest tmp_path):
    - Defaults to 'reports'.
    - If an alternative directory is requested, validates that it contains no
      directory traversal ('..') and resolves safely.
    """
    configured = os.getenv("FORGEFIT_REPORTS_DIR", "").strip()
    if configured:
        return get_configured_reports_dir()

    if (
        not requested_dir
        or not str(requested_dir).strip()
        or str(requested_dir).strip() == "reports"
    ):
        return get_configured_reports_dir()

    raw_str = str(requested_dir).strip()
    if ".." in raw_str:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Directory traversal is not permitted",
        )
    try:
        resolved = Path(raw_str).resolve()
        resolved.mkdir(parents=True, exist_ok=True)
        return resolved
    except Exception as err:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid directory path: {err}",
        )


def _validate_safe_run_id(run_id: str) -> str:
    """Validate run_id against path traversal attacks."""
    if not run_id or "/" in run_id or "\\" in run_id or ".." in run_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=(
                f"Invalid run_id '{run_id}': "
                "cannot contain path separators or traversal characters"
            ),
        )
    return sanitize_filename(run_id)


class JobManager:
    """In-memory thread-safe manager for tracking resilience test runs."""

    def __init__(self, max_concurrent: int = 5, max_history: int = 100) -> None:
        self._lock = threading.Lock()
        self._runs: dict[str, dict[str, Any]] = {}
        self._max_concurrent = max_concurrent
        self._max_history = max_history

    def create_run(self, scenario: Scenario, output_dir: str = "reports") -> str:
        """Create and register a new run in queued status with concurrency bounding."""
        with self._lock:
            active_count = sum(
                1
                for r in self._runs.values()
                if r.get("status") in ("queued", "running")
            )
            if active_count >= self._max_concurrent:
                raise HTTPException(
                    status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                    detail=(
                        f"Active run limit reached ({self._max_concurrent}). "
                        "Please wait for active runs to finish."
                    ),
                )

            # Evict oldest completed runs if history grows large
            if len(self._runs) >= self._max_history:
                inactive = [
                    k
                    for k, r in self._runs.items()
                    if r.get("status") in ("completed", "interrupted", "failed")
                ]
                for k in inactive[: len(self._runs) - self._max_history + 1]:
                    self._runs.pop(k, None)

            run_id = generate_run_id()
            self._runs[run_id] = {
                "run_id": run_id,
                "scenario_name": scenario.name,
                "status": "queued",
                "created_at": datetime.now(UTC).isoformat(),
                "progress": {"current": 0, "total": scenario.config.request_count},
                "report": None,
                "error": None,
                "output_dir": output_dir,
            }
        return run_id

    def update_progress(self, run_id: str, current: int, total: int) -> None:
        """Update the progress of an active run."""
        with self._lock:
            if run_id in self._runs:
                self._runs[run_id]["status"] = "running"
                self._runs[run_id]["progress"] = {"current": current, "total": total}

    def complete_run(
        self,
        run_id: str,
        report_data: dict[str, Any],
        interrupted: bool = False,
    ) -> None:
        """Mark a run as completed or interrupted."""
        with self._lock:
            if run_id in self._runs:
                self._runs[run_id]["status"] = (
                    "interrupted" if interrupted else "completed"
                )
                self._runs[run_id]["report"] = report_data

    def fail_run(self, run_id: str, error_message: str) -> None:
        """Mark a run as failed with an error message."""
        with self._lock:
            if run_id in self._runs:
                self._runs[run_id]["status"] = "failed"
                self._runs[run_id]["error"] = error_message

    def get_run(
        self,
        run_id: str,
        output_dir: str | Path = "reports",
    ) -> dict[str, Any] | None:
        """Retrieve run state by run_id, checking in-memory state then disk."""
        with self._lock:
            if run_id in self._runs:
                return dict(self._runs[run_id])

        # Fallback: check persisted reports in output_dir
        dir_path = Path(output_dir)
        if dir_path.is_dir():
            safe_id = sanitize_filename(run_id)
            for file_path in dir_path.glob(f"*{safe_id}*.json"):
                if file_path.name.startswith("."):
                    continue
                try:
                    loaded = load_report(file_path)
                    if loaded.get("run_id") == run_id:
                        return {
                            "run_id": run_id,
                            "scenario_name": loaded.get("scenario_name", "unknown"),
                            "status": "completed",
                            "created_at": loaded.get("created_at"),
                            "progress": {
                                "current": loaded.get("report", {}).get(
                                    "total_requests", 0
                                ),
                                "total": loaded.get("report", {}).get(
                                    "total_requests", 0
                                ),
                            },
                            "report": loaded.get("report"),
                            "error": None,
                            "output_dir": str(output_dir),
                        }
                except Exception:
                    continue

        return None


job_manager = JobManager()


def _execute_run_thread(
    run_id: str,
    scenario: Scenario,
    save_to_disk: bool,
    output_dir: str,
) -> None:
    """Worker function executed in background thread."""
    engine = ResilienceEngine()

    def progress_callback(
        current: int,
        total: int,
        outcome: RequestOutcome,
    ) -> None:
        job_manager.update_progress(run_id, current, total)

    try:
        job_manager.update_progress(run_id, 0, scenario.config.request_count)
        report = engine.run_scenario(
            scenario=scenario,
            extra_metadata={"run_id": run_id},
            progress_callback=progress_callback,
        )

        saved_path = None
        if save_to_disk:
            saved_path = save_report(
                report=report,
                scenario=scenario,
                output_dir=output_dir,
                run_id=run_id,
            )

        report_dict = report.to_dict()
        if saved_path:
            report_dict["saved_path"] = str(saved_path)

        job_manager.complete_run(
            run_id,
            report_dict,
            interrupted=report.interrupted,
        )
    except SafetyViolationError as err:
        job_manager.fail_run(run_id, f"Safety violation: {err}")
    except Exception as err:
        logger.exception("Error executing run %s: %s", run_id, err)
        job_manager.fail_run(run_id, f"Execution failure: {err}")


@app.get("/api/status")
def get_status() -> dict[str, Any]:
    """Return health status, version, and supported feature capabilities."""
    api_key_configured = bool(os.getenv("FORGEFIT_API_KEY", "").strip())
    reports_dir = str(get_configured_reports_dir())
    return {
        "status": "ok",
        "version": __version__,
        "toolkit": "ForgeFit",
        "description": "API resilience testing toolkit",
        "features": [
            "scenarios",
            "fault_schedules",
            "persistent_reports",
            "report_comparison",
            "metrics_export",
        ],
        "supported_schedules": ["constant", "step", "ramped"],
        "supported_export_formats": ["prometheus", "opentelemetry", "otel"],
        "default_output_dir": reports_dir,
        "api_key_required": api_key_configured,
        "safety_controls": {
            "loopback_only_by_default": True,
            "external_requires_authorization": True,
            "deadline_clamping_enforced": True,
        },
    }


@app.post("/api/scenarios/validate")
def validate_scenario(payload: dict[str, Any]) -> dict[str, Any]:
    """Validate scenario JSON structure, fields, and fault schedule."""
    if not isinstance(payload, dict):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Payload must be a JSON object",
        )
    try:
        scenario = Scenario.from_dict(payload)
        return {
            "valid": True,
            "scenario": scenario.to_dict(),
        }
    except Exception as err:
        return {
            "valid": False,
            "error": str(err),
        }


@app.post("/api/runs")
def start_run(
    payload: dict[str, Any],
    _: None = Depends(verify_api_key),
) -> dict[str, Any]:
    """Initiate a controlled resilience test run in the background."""
    if not isinstance(payload, dict):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Payload must be a JSON object",
        )

    scenario_raw = payload.get("scenario")
    if not scenario_raw:
        scenario_raw = payload.get("config") or payload

    if not isinstance(scenario_raw, dict):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid scenario data provided",
        )

    try:
        scenario = Scenario.from_dict(scenario_raw)
    except Exception as err:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Scenario validation error: {err}",
        ) from err

    # Web safety guard: bound request_count to prevent runaway memory usage
    if scenario.config.request_count > 1000:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="request_count exceeds web execution maximum of 1000",
        )

    # Mandatory loopback authorization enforcement
    if not scenario.config.is_loopback_target:
        if (
            not scenario.config.allow_external
            or not scenario.config.authorized_acknowledgement
        ):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=(
                    "Target URL is not a local loopback address (localhost/127.0.0.1). "
                    "External execution requires both allow_external=True and "
                    "authorized_acknowledgement=True."
                ),
            )

    save_report_flag = bool(payload.get("save_report", True))
    raw_output_dir = payload.get("output_dir")
    safe_output_dir = _resolve_reports_directory(raw_output_dir)

    run_id = job_manager.create_run(scenario, output_dir=str(safe_output_dir))

    # Launch execution thread
    thread = threading.Thread(
        target=_execute_run_thread,
        args=(run_id, scenario, save_report_flag, str(safe_output_dir)),
        daemon=True,
    )
    thread.start()

    return {
        "run_id": run_id,
        "scenario_name": scenario.name,
        "status": "queued",
        "created_at": datetime.now(UTC).isoformat(),
        "planned_requests": scenario.config.request_count,
    }


@app.get("/api/runs/{run_id}")
def get_run_status(
    run_id: str,
    output_dir: str = Query("reports"),
) -> dict[str, Any]:
    """Retrieve execution status and completed report for a run."""
    safe_id = _validate_safe_run_id(run_id)
    safe_dir = _resolve_reports_directory(output_dir)
    run_state = job_manager.get_run(safe_id, output_dir=safe_dir)
    if not run_state:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Run '{run_id}' not found",
        )
    return run_state


@app.get("/api/reports")
def get_reports(directory: str = Query("reports")) -> list[dict[str, Any]]:
    """List saved execution reports in the specified directory."""
    safe_dir = _resolve_reports_directory(directory)
    if not safe_dir.is_dir():
        return []

    summaries = list_reports(safe_dir)
    return [
        {
            "run_id": s.run_id,
            "scenario_name": s.scenario_name,
            "created_at": s.created_at,
            "total_requests": s.total_requests,
            "successful_requests": s.successful_requests,
            "failed_requests": s.failed_requests,
            "average_latency_ms": s.average_latency_ms,
            "p95_latency_ms": s.p95_latency_ms,
            "file_path": str(s.file_path),
        }
        for s in summaries
    ]


@app.get("/api/reports/{run_id}")
def get_single_report(
    run_id: str,
    directory: str = Query("reports"),
) -> dict[str, Any]:
    """Load a single persisted report by run_id."""
    safe_id = _validate_safe_run_id(run_id)
    safe_dir = _resolve_reports_directory(directory)
    if not safe_dir.is_dir():
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Report directory '{directory}' does not exist",
        )

    matched_file: Path | None = None
    for file_path in safe_dir.glob(f"*{safe_id}*.json"):
        if file_path.name.startswith("."):
            continue
        try:
            loaded = load_report(file_path)
            if loaded.get("run_id") == run_id:
                matched_file = file_path
                break
        except Exception:
            continue

    if not matched_file:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Report with run_id '{run_id}' not found",
        )

    try:
        return load_report(matched_file)
    except Exception as err:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to load report: {err}",
        ) from err


@app.post("/api/reports/compare")
def compare_saved_reports(payload: dict[str, Any]) -> dict[str, Any]:
    """Compare two saved reports by run_id or direct report objects."""
    if not isinstance(payload, dict):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Payload must be a JSON object",
        )

    directory = str(payload.get("directory", "reports"))
    safe_dir = _resolve_reports_directory(directory)
    raw_baseline_id = payload.get("baseline_run_id")
    raw_comparison_id = payload.get("comparison_run_id")

    if not raw_baseline_id or not raw_comparison_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Both 'baseline_run_id' and 'comparison_run_id' are required",
        )

    baseline_id = _validate_safe_run_id(str(raw_baseline_id))
    comparison_id = _validate_safe_run_id(str(raw_comparison_id))

    if not safe_dir.is_dir():
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Directory '{directory}' does not exist",
        )

    # Resolve baseline report
    baseline_report: dict[str, Any] | None = None
    comparison_report: dict[str, Any] | None = None

    for file_path in safe_dir.glob("*.json"):
        if file_path.name.startswith("."):
            continue
        try:
            data = load_report(file_path)
            rid = data.get("run_id")
            if rid == baseline_id:
                baseline_report = data
            if rid == comparison_id:
                comparison_report = data
        except Exception:
            continue

    if not baseline_report:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Baseline report '{baseline_id}' not found",
        )
    if not comparison_report:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Comparison report '{comparison_id}' not found",
        )

    try:
        comparison_res = compare_reports(baseline_report, comparison_report)
        return comparison_res.to_dict()
    except Exception as err:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Comparison error: {err}",
        ) from err


@app.get("/api/reports/{run_id}/export")
def export_saved_report(
    run_id: str,
    format: str = Query("prometheus"),
    directory: str = Query("reports"),
) -> Any:
    """Export a saved report to Prometheus text or OpenTelemetry JSON format."""
    safe_id = _validate_safe_run_id(run_id)
    safe_dir = _resolve_reports_directory(directory)
    if not safe_dir.is_dir():
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Directory '{directory}' not found",
        )

    matched_file: Path | None = None
    for file_path in safe_dir.glob(f"*{safe_id}*.json"):
        if file_path.name.startswith("."):
            continue
        try:
            loaded = load_report(file_path)
            if loaded.get("run_id") == run_id:
                matched_file = file_path
                break
        except Exception:
            continue

    if not matched_file:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Report '{run_id}' not found",
        )

    try:
        report_data = load_report(matched_file)
    except Exception as err:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error reading report: {err}",
        ) from err

    fmt_lower = format.lower().strip()
    if fmt_lower == "prometheus":
        text_prom = export_prometheus(report_data)
        return PlainTextResponse(
            text_prom,
            media_type="text/plain; version=0.0.4; charset=utf-8",
        )
    elif fmt_lower in ("otel", "opentelemetry"):
        otel_json = export_opentelemetry(report_data)
        return JSONResponse(otel_json)
    else:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=(
                f"Unsupported export format '{format}'. Supported formats: "
                "prometheus, otel, opentelemetry"
            ),
        )


# Serve frontend static assets if built
frontend_dist = Path(__file__).resolve().parent.parent.parent / "frontend" / "dist"
if frontend_dist.is_dir():
    app.mount("/", StaticFiles(directory=str(frontend_dist), html=True), name="static")
