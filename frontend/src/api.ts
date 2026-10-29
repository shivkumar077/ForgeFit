import type {
  ApiStatus,
  ComparisonResult,
  ReportSummary,
  ResilienceReport,
  RunState,
  Scenario,
} from './types';

/**
 * Return normalized API base URL.
 * Defaults to '/api' for local same-origin development.
 * If VITE_API_BASE_URL is configured (e.g. on Vercel), normalizes trailing slashes
 * and ensures the path routes to the backend's /api endpoint.
 */
export function getApiBaseUrl(): string {
  const envUrl = (import.meta.env.VITE_API_BASE_URL as string | undefined)?.trim();
  if (!envUrl) {
    return '/api';
  }
  const trimmed = envUrl.replace(/\/+$/, '');
  if (!trimmed.endsWith('/api')) {
    return `${trimmed}/api`;
  }
  return trimmed;
}

const API_KEY_SESSION_KEY = 'forgefit_api_key';
let inMemoryApiKey = '';

/**
 * Retrieve session API key from memory or sessionStorage.
 * Never persists across browser restarts and is not stored in localStorage.
 */
export function getStoredApiKey(): string {
  if (inMemoryApiKey) return inMemoryApiKey;
  try {
    const val = sessionStorage.getItem(API_KEY_SESSION_KEY);
    if (val) {
      inMemoryApiKey = val;
      return val;
    }
  } catch {
    // sessionStorage not available (e.g. sandboxed iframe or private browsing)
  }
  return '';
}

/**
 * Store or clear API key in session memory and sessionStorage only.
 */
export function setStoredApiKey(key: string): void {
  const trimmed = key.trim();
  inMemoryApiKey = trimmed;
  try {
    if (trimmed) {
      sessionStorage.setItem(API_KEY_SESSION_KEY, trimmed);
    } else {
      sessionStorage.removeItem(API_KEY_SESSION_KEY);
    }
  } catch {
    // sessionStorage not available
  }
}

/**
 * Construct request headers, including X-ForgeFit-API-Key if a key is stored.
 * Only dispatched to the configured ForgeFit API origin.
 */
function getHeaders(extra: Record<string, string> = {}): Record<string, string> {
  const headers: Record<string, string> = { ...extra };
  const key = getStoredApiKey();
  if (key) {
    headers['X-ForgeFit-API-Key'] = key;
  }
  return headers;
}

export async function fetchApiStatus(): Promise<ApiStatus> {
  const base = getApiBaseUrl();
  const res = await fetch(`${base}/status`, {
    headers: getHeaders(),
  });
  if (!res.ok) {
    throw new Error(`Failed to fetch API status (${res.status})`);
  }
  return res.json();
}

export async function validateScenario(
  payload: Scenario | Record<string, any>
): Promise<{ valid: boolean; scenario?: Scenario; error?: string }> {
  const base = getApiBaseUrl();
  const res = await fetch(`${base}/scenarios/validate`, {
    method: 'POST',
    headers: getHeaders({ 'Content-Type': 'application/json' }),
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
  const base = getApiBaseUrl();
  const res = await fetch(`${base}/runs`, {
    method: 'POST',
    headers: getHeaders({ 'Content-Type': 'application/json' }),
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
  const base = getApiBaseUrl();
  const res = await fetch(
    `${base}/runs/${encodeURIComponent(runId)}?output_dir=${encodeURIComponent(outputDir)}`,
    { headers: getHeaders() }
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
  const base = getApiBaseUrl();
  const res = await fetch(
    `${base}/reports?directory=${encodeURIComponent(directory)}`,
    { headers: getHeaders() }
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
  const base = getApiBaseUrl();
  const res = await fetch(
    `${base}/reports/${encodeURIComponent(runId)}?directory=${encodeURIComponent(directory)}`,
    { headers: getHeaders() }
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
  const base = getApiBaseUrl();
  const res = await fetch(`${base}/reports/compare`, {
    method: 'POST',
    headers: getHeaders({ 'Content-Type': 'application/json' }),
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
  const base = getApiBaseUrl();
  const res = await fetch(
    `${base}/reports/${encodeURIComponent(runId)}/export?format=${format}&directory=${encodeURIComponent(directory)}`,
    { headers: getHeaders() }
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
