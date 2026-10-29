import type {
  ApiStatus,
  ComparisonResult,
  ReportSummary,
  ResilienceReport,
  RunState,
  Scenario,
} from './types';

const API_BASE = '/api';

export async function fetchApiStatus(): Promise<ApiStatus> {
  const res = await fetch(`${API_BASE}/status`);
  if (!res.ok) {
    throw new Error(`Failed to fetch API status (${res.status})`);
  }
  return res.json();
}

export async function validateScenario(
  payload: Scenario | Record<string, any>
): Promise<{ valid: boolean; scenario?: Scenario; error?: string }> {
  const res = await fetch(`${API_BASE}/scenarios/validate`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(payload),
  });
  if (!res.ok) {
    const errData = await res.json().catch(() => ({}));
    return { valid: false, error: errData.detail || `HTTP ${res.status}` };
  }
  return res.json();
}

export async function startRun(
  scenario: Scenario,
  saveReport = true,
  outputDir = 'reports'
): Promise<RunState> {
  const res = await fetch(`${API_BASE}/runs`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({
      scenario,
      save_report: saveReport,
      output_dir: outputDir,
    }),
  });
  if (!res.ok) {
    const errData = await res.json().catch(() => ({}));
    throw new Error(errData.detail || `Failed to start run (HTTP ${res.status})`);
  }
  return res.json();
}

export async function fetchRunStatus(
  runId: string,
  outputDir = 'reports'
): Promise<RunState> {
  const res = await fetch(
    `${API_BASE}/runs/${encodeURIComponent(runId)}?output_dir=${encodeURIComponent(outputDir)}`
  );
  if (!res.ok) {
    const errData = await res.json().catch(() => ({}));
    throw new Error(errData.detail || `Run ${runId} not found`);
  }
  return res.json();
}

export async function fetchSavedReports(
  directory = 'reports'
): Promise<ReportSummary[]> {
  const res = await fetch(
    `${API_BASE}/reports?directory=${encodeURIComponent(directory)}`
  );
  if (!res.ok) {
    throw new Error(`Failed to fetch reports (${res.status})`);
  }
  return res.json();
}

export async function fetchSingleReport(
  runId: string,
  directory = 'reports'
): Promise<{ run_id: string; scenario_name: string; created_at: string; report: ResilienceReport; config?: any }> {
  const res = await fetch(
    `${API_BASE}/reports/${encodeURIComponent(runId)}?directory=${encodeURIComponent(directory)}`
  );
  if (!res.ok) {
    const errData = await res.json().catch(() => ({}));
    throw new Error(errData.detail || `Report ${runId} not found`);
  }
  return res.json();
}

export async function compareSavedReports(
  baselineRunId: string,
  comparisonRunId: string,
  directory = 'reports'
): Promise<ComparisonResult> {
  const res = await fetch(`${API_BASE}/reports/compare`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({
      baseline_run_id: baselineRunId,
      comparison_run_id: comparisonRunId,
      directory,
    }),
  });
  if (!res.ok) {
    const errData = await res.json().catch(() => ({}));
    throw new Error(errData.detail || `Comparison failed (${res.status})`);
  }
  return res.json();
}

export async function exportSavedReport(
  runId: string,
  format: 'prometheus' | 'otel' | 'opentelemetry',
  directory = 'reports'
): Promise<string> {
  const res = await fetch(
    `${API_BASE}/reports/${encodeURIComponent(runId)}/export?format=${format}&directory=${encodeURIComponent(directory)}`
  );
  if (!res.ok) {
    const errData = await res.json().catch(() => ({}));
    throw new Error(errData.detail || `Export failed (${res.status})`);
  }
  if (format === 'prometheus') {
    return res.text();
  } else {
    const json = await res.json();
    return JSON.stringify(json, null, 2);
  }
}
