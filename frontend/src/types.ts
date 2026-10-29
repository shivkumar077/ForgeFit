export type ScheduleType = 'constant' | 'step' | 'ramped';

export interface StepEntry {
  requests_threshold: number;
  latency_ms: number;
  failure_probability: number;
}

export interface ConstantSchedule {
  schedule_type: 'constant';
  latency_ms: number;
  failure_probability: number;
}

export interface StepSchedule {
  schedule_type: 'step';
  steps: StepEntry[];
}

export interface RampedSchedule {
  schedule_type: 'ramped';
  start_latency_ms: number;
  end_latency_ms: number;
  start_failure_probability: number;
  end_failure_probability: number;
  ramp_requests: number;
  start_iteration?: number;
}

export type FaultSchedule = ConstantSchedule | StepSchedule | RampedSchedule;

export interface ResilienceConfig {
  target_url: string;
  timeout_seconds: number;
  request_count: number;
  artificial_latency_ms: number;
  failure_probability: number;
  total_deadline_seconds: number;
  allow_external?: boolean;
  authorized_acknowledgement?: boolean;
  seed?: number | null;
  is_loopback_target?: boolean;
}

export interface Scenario {
  name: string;
  description?: string;
  tags?: string[];
  config: ResilienceConfig;
  schedule?: FaultSchedule | null;
}

export interface RequestOutcome {
  iteration: number;
  target_url: string;
  status_code: number | null;
  latency_ms: number;
  success: boolean;
  simulated_fault: boolean;
  failure_category: string | null;
  error_message: string | null;
  start_time: string | null;
  timestamp: string;
}

export interface ResilienceReport {
  scenario_name: string;
  total_requests: number;
  successful_requests: number;
  failed_requests: number;
  simulated_fault_count: number;
  http_error_count: number;
  timeout_count: number;
  connection_error_count: number;
  average_latency_ms: number;
  p95_latency_ms: number;
  total_duration_ms: number;
  interrupted: boolean;
  start_time: string;
  end_time: string;
  outcomes: RequestOutcome[];
  metadata?: Record<string, any>;
  saved_path?: string;
}

export interface ReportSummary {
  run_id: string;
  scenario_name: string;
  created_at: string;
  total_requests: number;
  successful_requests: number;
  failed_requests: number;
  average_latency_ms: number;
  p95_latency_ms: number;
  file_path: string;
}

export interface MetricDelta {
  metric_name: string;
  baseline: number;
  comparison: number;
  absolute_diff: number;
  percentage_diff: number | null;
  direction: 'improved' | 'degraded' | 'neutral' | 'unchanged';
}

export interface ComparisonResult {
  baseline_run_id: string;
  baseline_scenario: string;
  comparison_run_id: string;
  comparison_scenario: string;
  warnings: string[];
  notes: string[];
  metrics: Record<string, MetricDelta>;
}

export interface RunState {
  run_id: string;
  scenario_name: string;
  status: 'queued' | 'running' | 'completed' | 'failed' | 'interrupted';
  created_at: string;
  progress?: {
    current: number;
    total: number;
  };
  report?: ResilienceReport | null;
  error?: string | null;
  output_dir?: string;
}

export interface ApiStatus {
  status: string;
  version: string;
  toolkit: string;
  features: string[];
  supported_schedules: string[];
  supported_export_formats: string[];
  safety_controls: {
    loopback_only_by_default: boolean;
    external_requires_authorization: boolean;
    deadline_clamping_enforced: boolean;
  };
  api_key_required?: boolean;
}
