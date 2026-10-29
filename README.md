# ForgeFit

A Python-based API resilience testing toolkit for simulating service failures, injecting faults, evaluating application behavior under adverse conditions, and comparing execution runs.

ForgeFit is built for API developers, platform engineers, and reliability specialists who need to verify how client applications and upstream services behave when dependencies experience artificial latency, connection timeouts, or service degradation.

---

## Installation & Quick Start

### Prerequisites
- **Python**: 3.12 or higher
- **Node.js**: 18 or higher (only required if compiling the frontend production bundle from source)

### Installation
Clone the repository and install ForgeFit into a virtual environment:

```powershell
# Create and activate virtual environment
python -m venv .venv
.\.venv\Scripts\Activate.ps1

# Option 1: Core CLI & engine only (pure standard library, 0 external dependencies)
pip install -e .

# Option 2: Core + FastAPI interactive web server
pip install -e ".[web]"

# Option 3: Full development and test dependencies
pip install -e ".[dev,web]"
```

### Building the Frontend Production Bundle
The interactive React frontend is bundled in `frontend/dist`. To rebuild from TypeScript sources:

```powershell
cd frontend
npm install
npm run build
cd ..
```

### Launching the Application
```powershell
# Start the web interface on default http://127.0.0.1:8000
forgefit web

# If port 8000 is occupied, bind to an alternate port
forgefit web --port 8001
```

---

## v1.0.0 Architecture & Feature Overview

Milestone 5 introduces a complete, responsive, production-minded web interface and FastAPI backend for ForgeFit:

- **Interactive Developer Web Interface (`frontend/`)**:
  - **Landing Page**:
    - High-impact editorial hero with live interactive packet flow simulator.
    - Real-time adjustment of latency and failure rates with instant visual packet feedback.
    - Deep dives into resilient engineering principles, workflow steps, and safety guarantees.
  - **Scenario Builder**:
    - Visual forms for configuring target endpoints, iterations, deadlines, and socket timeouts.
    - Dedicated visual editors for **Adaptive Fault Schedules** (Constant, Step-based thresholds with dynamic row additions, and linearly Ramped progressions).
    - Pre-configured quick-launch templates (Localhost Baseline, Ramped Latency Stress, Sudden Degradation Spike, Deadline Clamping Probe).
    - One-click schema validation and live JSON inspection.
  - **Live Execution Monitor**:
    - Real-time polling and progress tracking without blocking UI interactions.
    - Prominent KPI summaries (Total Requests, Success Rate %, Mean Latency, p95 Latency, Simulated Faults, HTTP/Socket Errors).
    - Chronological outcomes breakdown table with latency visualizers and error classifications.
  - **Persisted Reports Explorer**:
    - Full search and filtering over saved execution artifacts.
    - Slide-over inspection modal displaying complete configuration summaries and raw report JSON.
    - One-click exports to Prometheus text format or OpenTelemetry JSON with clipboard copy and file download.
  - **Run Comparison Engine**:
    - Side-by-side run selector with automated workload divergence checks (target URL / timeout mismatches) and sample size advisories.
    - Full comparative metrics table with delta values, percentage differences, and directional assessment badges (`Improved`, `Degraded`, `Neutral`, `Unchanged`).
  - **Comprehensive About Page**:
    - Exhaustive architectural documentation covering cascading failures, retry storms, schedule boundaries, atomic report immutability, and verified creator credits (`shivkumar077`).

- **FastAPI Backend Integration (`forgefit.api`)**:
  - Exposes all core resilience capabilities over a clean, documented local REST API.
  - In-process thread-based worker manager (`JobManager`) tracking active execution states (`queued`, `running`, `completed`, `interrupted`, `failed`) with automatic fallback reconciliation to persisted disk reports.
  - Loopback-by-default safety enforcement returning HTTP 403 Forbidden on unacknowledged external targets.
  - Zero external network dependencies for offline operation.

- **CLI Web Launch Command**:
  - `forgefit web`: Instantly serves both the FastAPI API and the compiled React production frontend on `http://127.0.0.1:8000`.

---

## Milestone 4 Features: Adaptive Fault Schedules & Metrics Export

Milestone 4 enhances ForgeFit with adaptive fault progression schedules and offline standard-format metrics exporters:

- **Adaptive Fault Schedules (`forgefit.schedules`)**:
  - Dynamically alter simulated latency and failure probability as request iterations progress.
  - Three practical schedule types:
    - **`constant`**: Configures a fixed latency and failure probability across all iterations.
    - **`step`**: Transitions latency and/or failure probability at specified request-count thresholds (e.g., normal latency up to 50 requests, then spike to 500ms at request 51). Steps must be strictly ascending by threshold.
    - **`ramped`**: Progressively increases or decreases latency and failure probability linearly across a defined number of requests (`ramp_requests`) beginning at `start_iteration`.
  - **Boundary Conditions & Clamping**:
    - Step schedules: Iterations prior to the first threshold clamp to the first step's values. Iterations at or beyond the maximum threshold remain clamped to the final step's values.
    - Ramped schedules: Iterations at or before `start_iteration` use starting values. Iterations at or beyond `start_iteration + ramp_requests - 1` clamp to the end values.
  - **Deterministic Seeded Simulation**:
    - When `seed` is configured on the scenario config, pseudo-random simulated failure injection is 100% deterministic and reproducible.
  - **Preserved Engine Safety**:
    - Dynamic artificial latencies are strictly bounded by the remaining total scenario deadline (`total_deadline_seconds`).
    - Socket timeouts remain dynamically clamped to the remaining execution budget.
    - Request execution remains strictly sequential, loopback-guarded, and offline.
  - **100% Backward Compatible**: Existing scenarios and flat configurations without a `schedule` block continue to operate seamlessly using static parameters.

- **Standardized Metrics Exporters (`forgefit.exporters`)**:
  - Converts saved execution reports into industry-standard monitoring and telemetry formats without external server dependencies:
    - **Prometheus Text Exposition Format (`prometheus`)**:
      - Conforms to Prometheus text format specs (`text/plain; version=0.0.4`).
      - Emits `# HELP` and `# TYPE` declarations for all metrics.
      - Standardized metric names and units: `forgefit_requests_total`, `forgefit_requests_success_total`, `forgefit_requests_failed_total`, `forgefit_requests_by_category_total`, `forgefit_request_latency_average_seconds`, `forgefit_request_latency_p95_seconds`, `forgefit_execution_duration_seconds`, and `forgefit_success_rate_ratio`.
      - Strict label escaping for backslashes, double quotes, and newlines.
    - **OpenTelemetry-Compatible JSON (`otel`, `opentelemetry`)**:
      - Conforms to OpenTelemetry OTLP JSON schema (`resourceMetrics` -> `scopeMetrics` -> `metrics`).
      - Populates resource attributes (`service.name`, `forgefit.scenario`, `forgefit.run_id`).
      - Emits Sum counters (monotonic) and Gauge metrics with epoch timestamps.
  - **Honest Handling of Missing Metrics**: Values are only exported if present in the report; missing or uncomputable metrics are omitted rather than fabricated.
  - **Zero External Dependencies & Offline Operation**: Pure Python standard library implementation suitable for CI/CD pipelines, container environments, and local execution.
  - **Output Flexibility**: Direct output to stdout (for Unix pipes) or an explicit output file via `--output`.

---

## Milestone 3 Features

Milestone 3 extends ForgeFit with structured scenario management, atomic persistent execution reports, and automated run comparison:

- **Named, Reusable Scenarios (`Scenario`)**:
  - Reusable JSON definitions with human-readable scenario names, descriptions, and tag classifications.
  - Strongly typed, validated `ResilienceConfig` embedded within scenario metadata.
  - Backward compatible with legacy flat configuration files (naming defaults to file stem).
  - Schema validation rejecting missing fields, malformed JSON, and invalid types before request dispatch.

- **Atomic Persistent Execution Reports (`forgefit.reports`)**:
  - Automatically writes completed run results as deterministic JSON files.
  - Each run is assigned a unique run identifier (`run_<timestamp>_<uuid>`).
  - Output directory configurable via `--output-dir` (created only when report persistence is requested).
  - **Atomic File Writing**: Writes to hidden temporary files with OS-level `fsync` flush prior to replacement (`os.replace`) to guard against partial or corrupt report files during power loss or abrupt process termination.
  - **Guaranteed Immutability**: Never silently overwrites an existing report (`FileExistsError`).
  - **Path Traversal Protection**: Sanitizes scenario names and run IDs, verifying canonical paths remain bounded within the specified output directory.
  - **Secret & Body Omission**: Request and response bodies, authentication tokens, passwords, and sensitive headers are strictly omitted from persisted reports.

- **Report Listing & Inspection (`forgefit reports list`)**:
  - Quickly scan saved execution reports in any directory.
  - Displays a tabular overview with Run ID, Scenario Name, Creation Timestamp, Request Counts, Success Rates, and Latency metrics.
  - Gracefully skips corrupt or non-report JSON files without interrupting listings.

- **Execution Run Comparison (`forgefit reports compare`)**:
  - Compares two saved runs (baseline vs. comparison) across key resilience metrics.
  - Computes absolute differences and percentage changes.
  - **Directional Assessment**:
    - **Lower is favorable** (negative delta = improved): Average Latency, p95 Latency, HTTP Errors, Timeouts, Connection Errors, Failed Requests.
    - **Higher is favorable** (positive delta = improved): Success Rate, Successful Requests.
    - **Neutral**: Total Requests, Simulated Faults.
  - **Zero-Denominator Safety**: Safely renders percentage change as `N/A` when the baseline metric is zero to prevent division errors.
  - **Divergence Warnings**: Alerts the operator if baseline and comparison runs targeted different URLs, used different timeout settings, or executed different scenarios.
  - **Sample Size Notes**: Appends a clear advisory if either run executed fewer than 30 requests, preventing small sample variations from being mistaken for statistically significant differences.
  - Machine-readable JSON output option via `--json`.

- **Preserved Safety Controls**:
  - Loopback-by-default execution strictly restricted to `localhost`, `127.0.0.1`, `::1`.
  - Non-loopback targets require dual authorization flags (`--allow-external` and `--acknowledge-authorized`).
  - Per-request HTTP timeouts dynamically clamped to the remaining overall scenario deadline (`min(timeout_seconds, remaining_budget)`).
  - 100% offline, local testing with zero live external network calls.

---

## Scenario JSON Schema & Example

Scenarios are defined in standard JSON format:

```json
{
  "$schema": "http://json-schema.org/draft-07/schema#",
  "title": "ForgeFitScenario",
  "type": "object",
  "required": ["name", "config"],
  "properties": {
    "name": {
      "type": "string",
      "description": "Human-readable scenario identifier (non-empty)"
    },
    "description": {
      "type": "string",
      "description": "Optional scenario description and testing objectives"
    },
    "tags": {
      "type": "array",
      "items": { "type": "string" },
      "description": "Optional list of string tags for filtering and grouping"
    },
    "config": {
      "type": "object",
      "required": ["target_url"],
      "properties": {
        "target_url": { "type": "string", "format": "uri" },
        "timeout_seconds": { "type": "number", "minimum": 0.001, "default": 5.0 },
        "request_count": { "type": "integer", "minimum": 1, "default": 10 },
        "artificial_latency_ms": { "type": "integer", "minimum": 0, "default": 0 },
        "failure_probability": { "type": "number", "minimum": 0.0, "maximum": 1.0, "default": 0.0 },
        "total_deadline_seconds": { "type": "number", "minimum": 0.001, "default": 30.0 },
        "allow_external": { "type": "boolean", "default": false },
        "authorized_acknowledgement": { "type": "boolean", "default": false },
        "seed": { "type": ["integer", "null"], "default": null }
      }
    }
  }
}
```

### Documented Example Scenario (`examples/sample_scenario.json`)

```json
{
  "name": "Localhost Baseline Healthcheck",
  "description": "Standard resilience evaluation against local healthcheck endpoint with 50ms artificial latency and 5% simulated fault injection.",
  "tags": [
    "smoke",
    "local",
    "baseline"
  ],
  "config": {
    "target_url": "http://127.0.0.1:8080/health",
    "request_count": 20,
    "timeout_seconds": 2.0,
    "artificial_latency_ms": 50,
    "failure_probability": 0.05,
    "total_deadline_seconds": 30.0,
    "seed": 42
  }
}
```

### Scheduled Fault Scenario Example (`examples/scheduled_scenario.json`)

Scenarios can optionally include an explicit `schedule` block to alter simulated latency and failure probability over the course of the test run:

```json
{
  "name": "Progressive Resilience Ramp",
  "description": "Gradually ramps latency from 20ms to 200ms and failure probability from 0% to 30% across 20 iterations.",
  "tags": [
    "ramp",
    "stress",
    "adaptive"
  ],
  "schedule": {
    "schedule_type": "ramped",
    "start_latency_ms": 20,
    "end_latency_ms": 200,
    "start_failure_probability": 0.0,
    "end_failure_probability": 0.3,
    "ramp_requests": 20,
    "start_iteration": 1
  },
  "config": {
    "target_url": "http://127.0.0.1:8080/api",
    "request_count": 25,
    "timeout_seconds": 2.0,
    "total_deadline_seconds": 30.0,
    "seed": 100
  }
}
```

#### Supported Schedule Types:
- **`constant`**: Configures static `latency_ms` and `failure_probability`.
- **`step`**: Configures an array of `steps` (each with `requests_threshold`, `latency_ms`, `failure_probability`). Thresholds must be in strictly ascending order. Clamps to the first step before the lowest threshold, and to the last step at or beyond the highest threshold.
- **`ramped`**: Linearly interpolates latency and failure probability across `ramp_requests` beginning at `start_iteration`. Clamps to start values before `start_iteration` and to end values at or beyond `start_iteration + ramp_requests - 1`.


---

## CLI Usage

### Check Version & Help

```powershell
# Display installed version
forgefit --version

# Display main help
forgefit --help

# Display help for scenario subcommands
forgefit scenario --help

# Display help for reports subcommands
forgefit reports --help
```

### Launch Interactive Web Application (`forgefit web`)

Start the local ForgeFit interactive web application and REST API:

```powershell
# Launch web interface on default http://127.0.0.1:8000
forgefit web

# Bind to a custom port
forgefit web --port 8080
```


### Validate a Scenario

Validate scenario metadata, syntax, and nested resilience configuration before executing requests:

```powershell
forgefit scenario validate examples/sample_scenario.json
```

Output:
```text
Scenario configuration is valid: Localhost Baseline Healthcheck
  Name:                   Localhost Baseline Healthcheck
  Description:            Standard resilience evaluation against local healthcheck endpoint with 50ms artificial latency and 5% simulated fault injection.
  Tags:                   smoke, local, baseline
  Target URL:             http://127.0.0.1:8080/health
  Loopback target:        True
  Timeout (seconds):      2.0
  Request count:          20
  Artificial latency:     50 ms
  Failure probability:    0.05
  Total deadline:         30.0 s
```

*(Legacy flat configuration files may also be validated via `forgefit validate-config path/to/config.json`)*

### Execute a Scenario & Save Report

Execute requests and persist an atomic execution report:

```powershell
# Run scenario and save report to the ./reports directory
forgefit run examples/sample_scenario.json --output-dir ./reports

# Run scenario and output execution summary as raw JSON to stdout
forgefit run examples/sample_scenario.json --json
```

Output:
```text
Initiating scenario:     Localhost Baseline Healthcheck
  Target URL:            http://127.0.0.1:8080/health
  Loopback target:       True
  Planned requests:      20
  Per-request timeout:   2.0 s
  Total run deadline:    30.0 s
  Artificial latency:    50 ms
  Failure probability:   0.05
Running sequentially...

Execution Summary:
  Scenario:               Localhost Baseline Healthcheck
  Total Requests:         20
  Successful (2xx):       19
  Failed Requests:        1
    - HTTP Errors:        0
    - Timeouts:           0
    - Connection Errors:  0
    - Simulated Faults:   1
  Average Latency:        51.24 ms
  p95 Latency:            52.10 ms
  Total Duration:         1052.80 ms
  Interrupted by Deadline:False
  Report Saved:           reports/report_Localhost_Baseline_Healthcheck_run_20261030_032000_1a2b3c4d.json
```

### List Saved Execution Reports

List all reports preserved in a directory sorted by creation timestamp (newest first):

```powershell
forgefit reports list --directory ./reports
```

Output:
```text
Saved Execution Reports in './reports':
Run ID                        Created (UTC)        Scenario                       Requests  Success Rate  Avg Latency  p95 Latency
---------------------------------------------------------------------------------------------------------------------------------
run_20261030_032000_1a2b3c4d  2026-10-30T03:20:00Z Localhost Baseline Healthcheck 20        95.00%        51.24 ms     52.10 ms
run_20261030_021500_9e8d7c6b  2026-10-30T02:15:00Z Localhost Baseline Healthcheck 20        100.00%       68.45 ms     74.20 ms
```

### Compare Two Execution Runs

Compare performance and resilience characteristics between a baseline run and a comparison run:

```powershell
forgefit reports compare reports/baseline.json reports/comparison.json
```

Sample Comparison Output:
```text
====================================================================================
ForgeFit Resilience Run Comparison
====================================================================================
Baseline:   run_20261030_021500_9e8d7c6b (Localhost Baseline Healthcheck)
Comparison: run_20261030_032000_1a2b3c4d (Localhost Baseline Healthcheck)

Metric                   Baseline     Comparison   Diff       Change %   Assessment
------------------------------------------------------------------------------------
Total Requests           20           20           0.00       0.0%       Neutral
Successful Requests      20           19           -1.00      -5.0%      Degraded
Failed Requests          0            1            1.00       N/A        Degraded
Success Rate (%)         100.00       95.00        -5.00%     -5.0%      Degraded
HTTP Errors              0            0            0.00       N/A        Unchanged
Timeouts                 0            0            0.00       N/A        Unchanged
Connection Errors        0            0            0.00       N/A        Unchanged
Simulated Faults         0            1            1.00       N/A        Neutral
Average Latency (ms)     68.45        51.24        -17.21     -25.1%     Improved
p95 Latency (ms)         74.20        52.10        -22.10     -29.8%     Improved
====================================================================================
Notes:
  * Sample size is small (baseline=20, comparison=20 requests). Differences should be validated across larger runs and not presumed statistically significant.

Metric Direction Rules:
  * Latency: Lower is favorable (negative delta = improved).
  * Success Rate: Higher is favorable (positive delta = improved).
  * Failures/Errors: Lower is favorable (negative delta = improved).
```

For automated CI/CD pipelines, output machine-readable JSON using `--json`:
```powershell
forgefit reports compare reports/baseline.json reports/comparison.json --json
```

### Export Execution Reports (`forgefit reports export`)

Export completed reports to industry-standard Prometheus text exposition format or OpenTelemetry OTLP-compatible JSON:

```powershell
# Export report metrics in Prometheus text exposition format to stdout
forgefit reports export reports/report_example.json --format prometheus

# Export report metrics to a Prometheus text file
forgefit reports export reports/report_example.json --format prometheus --output metrics.prom

# Export report metrics in OpenTelemetry JSON format to stdout
forgefit reports export reports/report_example.json --format otel

# Export report metrics in OpenTelemetry JSON format to a file
forgefit reports export reports/report_example.json --format otel --output metrics.json
```

Prometheus Text Format Sample Output:
```text
# HELP forgefit_requests_total Total number of simulated requests executed.
# TYPE forgefit_requests_total counter
forgefit_requests_total{scenario="Progressive Resilience Ramp"} 25
# HELP forgefit_requests_success_total Number of successful HTTP requests (2xx).
# TYPE forgefit_requests_success_total counter
forgefit_requests_success_total{scenario="Progressive Resilience Ramp"} 22
# HELP forgefit_requests_failed_total Total number of failed requests.
# TYPE forgefit_requests_failed_total counter
forgefit_requests_failed_total{scenario="Progressive Resilience Ramp"} 3
# HELP forgefit_requests_by_category_total Request failures categorized by error type.
# TYPE forgefit_requests_by_category_total counter
forgefit_requests_by_category_total{category="http_error",scenario="Progressive Resilience Ramp"} 0
forgefit_requests_by_category_total{category="timeout",scenario="Progressive Resilience Ramp"} 0
forgefit_requests_by_category_total{category="connection_error",scenario="Progressive Resilience Ramp"} 0
forgefit_requests_by_category_total{category="simulated_fault",scenario="Progressive Resilience Ramp"} 3
# HELP forgefit_request_latency_average_seconds Average request latency in seconds.
# TYPE forgefit_request_latency_average_seconds gauge
forgefit_request_latency_average_seconds{scenario="Progressive Resilience Ramp"} 0.1142
# HELP forgefit_request_latency_p95_seconds 95th percentile request latency in seconds.
# TYPE forgefit_request_latency_p95_seconds gauge
forgefit_request_latency_p95_seconds{scenario="Progressive Resilience Ramp"} 0.1985
# HELP forgefit_execution_duration_seconds Total execution wall clock duration in seconds.
# TYPE forgefit_execution_duration_seconds gauge
forgefit_execution_duration_seconds{scenario="Progressive Resilience Ramp"} 2.8540
# HELP forgefit_success_rate_ratio Ratio of successful requests to total requests.
# TYPE forgefit_success_rate_ratio gauge
forgefit_success_rate_ratio{scenario="Progressive Resilience Ramp"} 0.8800
```

---

## Comparison Metrics & Directional Assessment Rules

When comparing resilience runs, ForgeFit assesses metric deltas based on clear directional rules:

| Metric | Direction Favorable | Interpretation |
| :--- | :--- | :--- |
| **Total Requests** | `Neutral` | Operational volume; delta is informational. |
| **Successful Requests** | `Higher` | More successful transactions indicates higher availability. |
| **Failed Requests** | `Lower` | Fewer failed transactions indicates higher service reliability. |
| **Success Rate (%)** | `Higher` | Higher success percentage indicates superior availability. |
| **HTTP Errors (3xx–5xx)** | `Lower` | Fewer HTTP error responses indicates better upstream health. |
| **Timeouts** | `Lower` | Fewer socket timeouts indicates responsiveness within SLOs. |
| **Connection Errors** | `Lower` | Fewer connection refusals indicates server accessibility. |
| **Simulated Faults** | `Neutral` | Local injection test condition; reflects configured probability. |
| **Average Latency (ms)** | `Lower` | Lower mean response time indicates improved performance. |
| **p95 Latency (ms)** | `Lower` | Lower tail latency indicates consistent response times. |

### Special Comparison Handling
- **Zero Denominators**: When a baseline metric is 0 (e.g., 0 baseline timeouts) and the comparison reports >0 timeouts, percentage change cannot be computed mathematically. ForgeFit records `percentage_diff = None` and displays `N/A`, while correctly classifying the absolute increase as `Degraded`.
- **Workload Mismatch Warnings**: If baseline and comparison runs targeted different URLs (`target_url`), used different socket timeouts, or tested different scenario names, ForgeFit prints explicit warning banners so operators do not misinterpret incomparable test workloads.
- **Small Sample Advisory**: If either run executed fewer than 30 requests, ForgeFit attaches an advisory reminding operators that small sample differences should not be presumed statistically significant.

---

## Safety Controls & Execution Safeguards

1. **Loopback Target Authorization**:
   - Out of the box, ForgeFit only allows requests to local loopback hosts (`localhost`, `127.0.0.1`, `[::1]`).
   - Requests to external hosts require explicit operator authorization via both `--allow-external` and `--acknowledge-authorized`.
2. **Execution Deadline Clamping**:
   - Total scenario wall-clock time is strictly bounded by `total_deadline_seconds`.
   - Before dispatching any request, the effective socket timeout is clamped to `min(timeout_seconds, remaining_budget)`.
   - If the total deadline is exhausted during execution or artificial latency delay, request scheduling halts immediately.
3. **Bounded Transport & Privacy**:
   - Response bodies are capped at 4KB and never persisted to disk or included in reports.
   - Redirects (301, 302, 303, 307, 308) are never silently followed to third-party hosts.
   - Credentials, Authorization headers, and sensitive tokens are strictly excluded from report summaries.

---

## Development, Testing & Verification

ForgeFit uses `pytest` for unit testing and `Ruff` for linting and formatting.

### Run Tests
```powershell
# Run the complete test suite offline
pytest -v
```
All 185 automated tests execute entirely offline using local mock servers and temporary directories. Zero external network calls are made.

### Run Linter & Formatter
```powershell
# Verify lint rules
ruff check src tests

# Verify formatting
ruff format --check src tests

# Auto-format codebase
ruff format src tests
```

---

## Cloud Deployment Guide (Render + Vercel Split Architecture)

ForgeFit supports a secure split deployment architecture:
- **Backend API**: Hosted on [Render](https://render.com) (Python 3.12+ FastAPI Web Service with persistent disk for JSON reports).
- **Frontend UI**: Hosted on [Vercel](https://vercel.com) (Static Vite React SPA with client-side routing).

> [!NOTE]
> This repository contains deployment preparation, configuration files, and local build verification. No live deployment to external cloud accounts has been executed.

### Architecture & Security Overview

```
┌─────────────────────────────────┐           ┌─────────────────────────────────┐
│     Vercel Frontend (SPA)       │           │      Render Backend (FastAPI)   │
│  - Vite React client            │           │  - Uvicorn / Python 3.12        │
│  - VITE_API_BASE_URL            │  HTTPS    │  - FORGEFIT_CORS_ORIGINS        │
│  - X-ForgeFit-API-Key (session) ├──────────►│  - FORGEFIT_API_KEY (optional) │
│  - Session-only storage         │           │  - Persistent Disk (/var/data)  │
└─────────────────────────────────┘           └────────────────┬────────────────┘
                                                               │
                                                               ▼
                                                  ┌─────────────────────────────┐
                                                  │ Atomic JSON Report Storage  │
                                                  │ (/var/data/reports)         │
                                                  └─────────────────────────────┘
```

### Environment Variables Reference

| Variable | Target | Purpose | Default / Example |
| :--- | :--- | :--- | :--- |
| `VITE_API_BASE_URL` | Frontend (Vercel) | Full base URL of the backend API (including `/api`) | `https://your-service.onrender.com/api` (Local default: `/api`) |
| `FORGEFIT_CORS_ORIGINS` | Backend (Render) | Comma-separated allowed frontend origins or wildcards | `https://*.vercel.app` (catches all Vercel deploys) |
| `FORGEFIT_API_KEY` | Backend (Render) | Shared secret protecting `POST /api/runs` | Random secret token (e.g. `sk_live_...`). If unset, authentication is disabled. |
| `FORGEFIT_REPORTS_DIR` | Backend (Render) | Directory path for atomic JSON report persistence | `/var/data/reports` (Local default: `reports`) |
| `PORT` | Backend (Render) | Port for Uvicorn server | Set automatically by Render runtime |

---

### Backend Deployment (Render)

1. **Create Web Service**:
   - In the Render Dashboard, choose **New + > Web Service** and connect your ForgeFit repository.
   - Alternatively, deploy using the included [`render.yaml`](file:///c:/Users/sk699/OneDrive/Desktop/ForgeFit/render.yaml) Blueprint.
2. **Service Settings**:
   - **Environment**: `Python 3`
   - **Python Version**: `3.12.6` (configured via `PYTHON_VERSION` environment variable)
   - **Root Directory**: `.` (repository root)
   - **Build Command**: `pip install ".[web]"`
   - **Start Command**: `uvicorn forgefit.api:app --host 0.0.0.0 --port $PORT`
   - **Health Check Path**: `/api/status`
3. **Persistent Disk (Critical for Report Retention)**:
   - Attach a Render Persistent Disk:
     - **Name**: `forgefit-data`
     - **Mount Path**: `/var/data`
     - **Size**: 1 GB (or as required)
   - Set environment variable: `FORGEFIT_REPORTS_DIR=/var/data/reports`.
   - When configured, ForgeFit automatically creates and locks this directory for all run reports, listing, comparisons, and exports, preventing arbitrary client path manipulation.
4. **Environment Variables**:
   - `FORGEFIT_CORS_ORIGINS`: Add `https://*.vercel.app` to automatically match all Vercel URLs (including preview branches, project URLs, and production domains), or set your exact domain (e.g. `https://forgefit.vercel.app`).
   - `FORGEFIT_API_KEY`: Set a cryptographically strong secret token. When set, `POST /api/runs` requires the `X-ForgeFit-API-Key` header with constant-time verification.

---

### Frontend Deployment (Vercel)

1. **Import Project**:
   - In the Vercel Dashboard, click **Add New... > Project** and import your ForgeFit repository.
2. **Project Settings**:
   - **Root Directory**: `frontend`
   - **Framework Preset**: `Vite`
   - **Build Command**: `npm run build`
   - **Output Directory**: `dist`
3. **Environment Variables**:
   - `VITE_API_BASE_URL`: `https://YOUR-RENDER-SERVICE.onrender.com/api` (ensure it points to your Render backend).
4. **SPA Routing**:
   - Handled automatically by [`frontend/vercel.json`](file:///c:/Users/sk699/OneDrive/Desktop/ForgeFit/frontend/vercel.json) using client-side rewrites to `/index.html`.

---

### Hosted API Security & API Key Management

- **No Public Run Launch**: A hosted resilience-testing backend should never be exposed as an open, unauthenticated stress-testing tool. Setting `FORGEFIT_API_KEY` locks execution behind authentication.
- **Constant-Time Verification**: Uses `secrets.compare_digest` to prevent timing attacks.
- **Zero Secret Exposure**: The key is never returned by `/api/status`, never written to reports or logs, and never baked into client bundles.
- **Session-Only Operator Entry**: When connecting to a protected backend, operators enter their key via the web interface's **API Key** control modal. The key is held strictly in `sessionStorage` or in-memory state for the active browser session, clearing automatically when the tab is closed.
- **Safety Flags Maintained**: The engine's loopback-by-default rules and dual authorization requirements for external hosts (`allow_external` and `authorized_acknowledgement`) remain strictly enforced regardless of deployment mode.

---

## System Limitations & Persistence Model

ForgeFit v1.0.0 is an offline-capable, local resilience testing toolkit designed for predictable developer workflows without external infrastructure dependencies:

- **Sequential Execution**: Requests are executed sequentially to ensure deterministic latency measurement and strict fault schedule progression. Concurrent worker pools and parallel probe dispatch are intentionally not included.
- **Local JSON Report Persistence**: Completed runs are persisted as atomic, immutable JSON files in the local filesystem (`reports/` by default). ForgeFit intentionally avoids external SQL databases, PostgreSQL, Neon, or cloud persistence.
- **In-Memory Active Run State**: The backend `JobManager` tracks active execution progress in memory. If the web server process restarts, in-progress runs terminate, while all previously completed and saved JSON reports remain fully intact on disk and discoverable upon restart.
- **Single-User / Local Developer Tool**: ForgeFit does not include multi-user authentication, tenant isolation, or distributed workers.
- **Zero Third-Party Services**: No Redis, Celery, or cloud message brokers are required; execution runs on native Python worker threads.
- **Strict Network Isolation**: All testing is loopback-only (`localhost`, `127.0.0.1`, `[::1]`) by default. External targets require explicit dual authorization flags.
