import React, { useState } from 'react';
import {
  Play,
  CheckCircle2,
  AlertTriangle,
  Code2,
  Plus,
  Trash2,
  Layers,
  ShieldAlert,
  Clock,
  Flame,
  Shuffle
} from 'lucide-react';
import type { FaultSchedule, Scenario, StepEntry } from '../types';
import { validateScenario, startRun } from '../api';

interface ScenarioBuilderProps {
  onRunStarted: (runId: string) => void;
  initialPreset?: string | null;
}

export const ScenarioBuilderView: React.FC<ScenarioBuilderProps> = ({
  onRunStarted,
  initialPreset,
}) => {
  // Scenario Fields
  const [name, setName] = useState('Localhost Resilience Healthcheck');
  const [description, setDescription] = useState(
    'Sequential resilience test against local healthcheck with controlled latency and fault injection.'
  );
  const [tags, setTags] = useState('smoke, local, baseline');
  const [targetUrl, setTargetUrl] = useState('http://127.0.0.1:8080/health');
  const [requestCount, setRequestCount] = useState(20);
  const [timeoutSeconds, setTimeoutSeconds] = useState(2.0);
  const [totalDeadlineSeconds, setTotalDeadlineSeconds] = useState(30.0);
  const [artificialLatencyMs, setArtificialLatencyMs] = useState(50);
  const [failureProbability, setFailureProbability] = useState(0.05);
  const [seed, setSeed] = useState<string>('42');
  const [allowExternal, setAllowExternal] = useState(false);
  const [authorizedAck, setAuthorizedAck] = useState(false);

  // Schedule Type
  const [scheduleMode, setScheduleMode] = useState<'none' | 'constant' | 'step' | 'ramped'>('none');

  // Constant schedule state
  const [constLatency, setConstLatency] = useState(100);
  const [constFailureProb, setConstFailureProb] = useState(0.1);

  // Step schedule state
  const [steps, setSteps] = useState<StepEntry[]>([
    { requests_threshold: 10, latency_ms: 20, failure_probability: 0.0 },
    { requests_threshold: 20, latency_ms: 250, failure_probability: 0.4 },
  ]);

  // Ramped schedule state
  const [rampStartLatency, setRampStartLatency] = useState(20);
  const [rampEndLatency, setRampEndLatency] = useState(200);
  const [rampStartFail, setRampStartFail] = useState(0.0);
  const [rampEndFail, setRampEndFail] = useState(0.3);
  const [rampRequests, setRampRequests] = useState(20);
  const [rampStartIteration, setRampStartIteration] = useState(1);

  // UI state
  const [showJson, setShowJson] = useState(false);
  const [isValidating, setIsValidating] = useState(false);
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [validationResult, setValidationResult] = useState<{ valid: boolean; error?: string } | null>(null);

  // Apply presets if triggered
  React.useEffect(() => {
    if (initialPreset === 'baseline') {
      setName('Localhost Baseline Healthcheck');
      setTargetUrl('http://127.0.0.1:8080/health');
      setRequestCount(20);
      setArtificialLatencyMs(50);
      setFailureProbability(0.05);
      setScheduleMode('none');
    } else if (initialPreset === 'ramped') {
      setName('Progressive Latency Ramp');
      setTargetUrl('http://127.0.0.1:8080/api');
      setRequestCount(25);
      setScheduleMode('ramped');
      setRampStartLatency(20);
      setRampEndLatency(200);
      setRampStartFail(0.0);
      setRampEndFail(0.3);
      setRampRequests(20);
    } else if (initialPreset === 'step') {
      setName('Sudden Degradation Spike');
      setTargetUrl('http://127.0.0.1:8080/api');
      setRequestCount(30);
      setScheduleMode('step');
      setSteps([
        { requests_threshold: 15, latency_ms: 20, failure_probability: 0.0 },
        { requests_threshold: 30, latency_ms: 400, failure_probability: 0.5 },
      ]);
    } else if (initialPreset === 'timeout') {
      setName('Deadline Clamping Probe');
      setTargetUrl('http://127.0.0.1:8080/health');
      setRequestCount(15);
      setTimeoutSeconds(1.5);
      setTotalDeadlineSeconds(10.0);
      setScheduleMode('none');
    }
  }, [initialPreset]);

  // Determine if target URL is loopback
  const isLoopback =
    targetUrl.includes('localhost') ||
    targetUrl.includes('127.0.0.1') ||
    targetUrl.includes('[::1]') ||
    targetUrl.includes('::1');

  // Build the complete scenario payload
  const buildScenario = (): Scenario => {
    let schedule: FaultSchedule | null = null;
    if (scheduleMode === 'constant') {
      schedule = {
        schedule_type: 'constant',
        latency_ms: Number(constLatency),
        failure_probability: Number(constFailureProb),
      };
    } else if (scheduleMode === 'step') {
      schedule = {
        schedule_type: 'step',
        steps: steps.map((s) => ({
          requests_threshold: Number(s.requests_threshold),
          latency_ms: Number(s.latency_ms),
          failure_probability: Number(s.failure_probability),
        })),
      };
    } else if (scheduleMode === 'ramped') {
      schedule = {
        schedule_type: 'ramped',
        start_latency_ms: Number(rampStartLatency),
        end_latency_ms: Number(rampEndLatency),
        start_failure_probability: Number(rampStartFail),
        end_failure_probability: Number(rampEndFail),
        ramp_requests: Number(rampRequests),
        start_iteration: Number(rampStartIteration),
      };
    }

    const parsedTags = tags
      .split(',')
      .map((t) => t.trim())
      .filter(Boolean);

    return {
      name: name.trim() || 'Untitled Scenario',
      description: description.trim(),
      tags: parsedTags,
      config: {
        target_url: targetUrl.trim(),
        request_count: Number(requestCount),
        timeout_seconds: Number(timeoutSeconds),
        total_deadline_seconds: Number(totalDeadlineSeconds),
        artificial_latency_ms: Number(artificialLatencyMs),
        failure_probability: Number(failureProbability),
        seed: seed.trim() ? Number(seed) : null,
        allow_external: allowExternal,
        authorized_acknowledgement: authorizedAck,
      },
      schedule,
    };
  };

  const handleValidate = async () => {
    setIsValidating(true);
    setValidationResult(null);
    try {
      const scenario = buildScenario();
      const res = await validateScenario(scenario);
      setValidationResult(res);
    } catch (err: any) {
      setValidationResult({ valid: false, error: err.message || 'Validation request failed' });
    } finally {
      setIsValidating(false);
    }
  };

  const handleStartRun = async () => {
    setIsSubmitting(true);
    setValidationResult(null);
    try {
      const scenario = buildScenario();
      const runState = await startRun(scenario, true, 'reports');
      onRunStarted(runState.run_id);
    } catch (err: any) {
      setValidationResult({ valid: false, error: err.message || 'Failed to start execution run' });
    } finally {
      setIsSubmitting(false);
    }
  };

  const handleAddStep = () => {
    const lastThreshold = steps.length > 0 ? steps[steps.length - 1].requests_threshold : 10;
    setSteps([
      ...steps,
      {
        requests_threshold: lastThreshold + 10,
        latency_ms: 100,
        failure_probability: 0.2,
      },
    ]);
  };

  const handleRemoveStep = (index: number) => {
    setSteps(steps.filter((_, i) => i !== index));
  };

  const handleStepChange = (index: number, field: keyof StepEntry, val: number) => {
    const newSteps = [...steps];
    newSteps[index] = { ...newSteps[index], [field]: val };
    setSteps(newSteps);
  };

  const currentScenarioJson = JSON.stringify(buildScenario(), null, 2);

  return (
    <div className="view-content" style={{ animation: 'fadeIn 0.2s ease-out' }}>
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '24px', flexWrap: 'wrap', gap: '16px' }}>
        <div>
          <h1 style={{ fontSize: '1.8rem', fontWeight: 800, letterSpacing: '-0.02em', marginBottom: '6px' }}>
            Resilience Test Configuration
          </h1>
          <p style={{ color: 'var(--text-secondary)', fontSize: '0.95rem' }}>
            Define endpoints, timeouts, artificial delays, and adaptive fault schedules.
          </p>
        </div>
        <div style={{ display: 'flex', gap: '10px' }}>
          <button className="btn btn-secondary" onClick={() => setShowJson(!showJson)}>
            <Code2 size={16} />
            {showJson ? 'Hide JSON' : 'Inspect JSON'}
          </button>
          <button className="btn btn-secondary" onClick={handleValidate} disabled={isValidating}>
            <CheckCircle2 size={16} />
            {isValidating ? 'Validating...' : 'Validate'}
          </button>
          <button className="btn btn-primary" onClick={handleStartRun} disabled={isSubmitting}>
            <Play size={16} />
            {isSubmitting ? 'Starting...' : 'Execute Test Run'}
          </button>
        </div>
      </div>

      {/* Validation Result Banner */}
      {validationResult && (
        <div
          style={{
            padding: '14px 18px',
            borderRadius: 'var(--radius-md)',
            marginBottom: '24px',
            display: 'flex',
            alignItems: 'center',
            gap: '12px',
            backgroundColor: validationResult.valid ? 'var(--color-success-subtle)' : 'var(--color-error-subtle)',
            border: `1px solid ${validationResult.valid ? 'rgba(16, 185, 129, 0.4)' : 'rgba(244, 63, 94, 0.4)'}`,
          }}
        >
          {validationResult.valid ? (
            <>
              <CheckCircle2 size={20} color="var(--color-success)" />
              <div>
                <strong style={{ color: 'var(--color-success)' }}>Scenario configuration is valid!</strong>
                <div style={{ fontSize: '0.82rem', color: 'var(--text-secondary)' }}>
                  All constraints, ranges, types, and fault schedules verified. Ready for execution.
                </div>
              </div>
            </>
          ) : (
            <>
              <AlertTriangle size={20} color="var(--color-error)" />
              <div>
                <strong style={{ color: 'var(--color-error)' }}>Validation Failed:</strong>
                <div style={{ fontSize: '0.82rem', color: 'var(--text-primary)', marginTop: '2px' }}>
                  {validationResult.error}
                </div>
              </div>
            </>
          )}
        </div>
      )}

      {/* JSON Inspector Slide-over/Box */}
      {showJson && (
        <div className="ff-card" style={{ marginBottom: '24px', background: 'var(--bg-canvas)' }}>
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '12px' }}>
            <span style={{ fontFamily: 'var(--font-mono)', fontSize: '0.82rem', color: 'var(--accent-primary)' }}>
              Scenario JSON Definition
            </span>
            <button
              className="btn btn-subtle btn-sm"
              onClick={() => navigator.clipboard.writeText(currentScenarioJson)}
            >
              Copy JSON
            </button>
          </div>
          <pre
            style={{
              padding: '16px',
              borderRadius: 'var(--radius-sm)',
              background: 'var(--bg-surface-1)',
              border: '1px solid var(--border-subtle)',
              fontFamily: 'var(--font-mono)',
              fontSize: '0.82rem',
              color: 'var(--text-primary)',
              overflowX: 'auto',
              maxHeight: '300px',
            }}
          >
            {currentScenarioJson}
          </pre>
        </div>
      )}

      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(320px, 1fr))', gap: '24px' }}>
        {/* Left Column: Target & Scenario Identity */}
        <div className="ff-card">
          <div className="ff-card-title" style={{ marginBottom: '16px' }}>
            <Layers size={18} color="var(--accent-primary)" />
            Scenario Metadata & Target
          </div>

          <div className="form-group">
            <label className="form-label">
              Scenario Name
              <span className="form-help">Human-readable identifier</span>
            </label>
            <input
              type="text"
              className="form-input"
              value={name}
              onChange={(e) => setName(e.target.value)}
              placeholder="e.g. Orders Service Resilience"
            />
          </div>

          <div className="form-group">
            <label className="form-label">
              Description
              <span className="form-help">Testing goals and environment</span>
            </label>
            <textarea
              className="form-textarea"
              rows={2}
              value={description}
              onChange={(e) => setDescription(e.target.value)}
              placeholder="Optional scenario description"
            />
          </div>

          <div className="form-group">
            <label className="form-label">
              Tags
              <span className="form-help">Comma-separated</span>
            </label>
            <input
              type="text"
              className="form-input"
              value={tags}
              onChange={(e) => setTags(e.target.value)}
              placeholder="smoke, local, candidate"
            />
          </div>

          <div className="form-group">
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '6px' }}>
              <label className="form-label" style={{ margin: 0 }}>Target URL</label>
              <span className={`badge ${isLoopback ? 'badge-success' : 'badge-warning'}`}>
                {isLoopback ? 'Loopback Target' : 'External Target'}
              </span>
            </div>
            <input
              type="text"
              className="form-input"
              value={targetUrl}
              onChange={(e) => setTargetUrl(e.target.value)}
              placeholder="http://127.0.0.1:8080/health"
            />
          </div>

          {!isLoopback && (
            <div
              style={{
                padding: '14px',
                borderRadius: 'var(--radius-md)',
                backgroundColor: 'rgba(234, 179, 8, 0.1)',
                border: '1px solid rgba(234, 179, 8, 0.3)',
                marginTop: '12px',
              }}
            >
              <div style={{ display: 'flex', gap: '8px', alignItems: 'center', marginBottom: '8px', color: 'var(--color-warning)', fontWeight: 600, fontSize: '0.85rem' }}>
                <ShieldAlert size={16} />
                External Target Safety Opt-In
              </div>
              <p style={{ fontSize: '0.78rem', color: 'var(--text-secondary)', marginBottom: '12px' }}>
                ForgeFit enforces local loopback by default. External targets require explicit dual authorization.
              </p>
              <div style={{ display: 'flex', flexDirection: 'column', gap: '8px', fontSize: '0.82rem' }}>
                <label style={{ display: 'flex', alignItems: 'center', gap: '8px', cursor: 'pointer' }}>
                  <input
                    type="checkbox"
                    checked={allowExternal}
                    onChange={(e) => setAllowExternal(e.target.checked)}
                  />
                  <span>Allow external host target (allow_external=True)</span>
                </label>
                <label style={{ display: 'flex', alignItems: 'center', gap: '8px', cursor: 'pointer' }}>
                  <input
                    type="checkbox"
                    checked={authorizedAck}
                    onChange={(e) => setAuthorizedAck(e.target.checked)}
                  />
                  <span>I acknowledge I am authorized to test this target</span>
                </label>
              </div>
            </div>
          )}
        </div>

        {/* Right Column: Execution Parameters */}
        <div className="ff-card">
          <div className="ff-card-title" style={{ marginBottom: '16px' }}>
            <Clock size={18} color="var(--color-info)" />
            Execution Parameters & Bounding
          </div>

          <div className="form-row-2">
            <div className="form-group">
              <label className="form-label">
                Request Count
                <span className="form-help">1 to 1000</span>
              </label>
              <input
                type="number"
                min="1"
                max="1000"
                className="form-input"
                value={requestCount}
                onChange={(e) => setRequestCount(Number(e.target.value))}
              />
            </div>

            <div className="form-group">
              <label className="form-label">
                Per-Request Timeout (s)
                <span className="form-help">Clamped by deadline</span>
              </label>
              <input
                type="number"
                step="0.1"
                min="0.001"
                className="form-input"
                value={timeoutSeconds}
                onChange={(e) => setTimeoutSeconds(Number(e.target.value))}
              />
            </div>
          </div>

          <div className="form-row-2">
            <div className="form-group">
              <label className="form-label">
                Total Deadline (s)
                <span className="form-help">Strict wall-clock bound</span>
              </label>
              <input
                type="number"
                step="0.5"
                min="0.1"
                className="form-input"
                value={totalDeadlineSeconds}
                onChange={(e) => setTotalDeadlineSeconds(Number(e.target.value))}
              />
            </div>

            <div className="form-group">
              <label className="form-label">
                Random Seed
                <span className="form-help">Deterministic replay</span>
              </label>
              <div style={{ display: 'flex', gap: '6px' }}>
                <input
                  type="text"
                  className="form-input"
                  value={seed}
                  onChange={(e) => setSeed(e.target.value)}
                  placeholder="e.g. 42 (optional)"
                />
                <button
                  type="button"
                  className="btn btn-secondary btn-sm"
                  title="Generate random seed"
                  onClick={() => setSeed(String(Math.floor(Math.random() * 99999)))}
                >
                  <Shuffle size={14} />
                </button>
              </div>
            </div>
          </div>

          <div className="form-row-2">
            <div className="form-group">
              <label className="form-label">
                Artificial Latency (ms)
                <span className="form-help">Static fallback</span>
              </label>
              <input
                type="number"
                min="0"
                className="form-input"
                value={artificialLatencyMs}
                onChange={(e) => setArtificialLatencyMs(Number(e.target.value))}
              />
            </div>

            <div className="form-group">
              <label className="form-label">
                Failure Probability (0.0 - 1.0)
                <span className="form-help">Simulated rate</span>
              </label>
              <input
                type="number"
                step="0.01"
                min="0"
                max="1.0"
                className="form-input"
                value={failureProbability}
                onChange={(e) => setFailureProbability(Number(e.target.value))}
              />
            </div>
          </div>
        </div>
      </div>

      {/* Adaptive Fault Schedule Section */}
      <div className="ff-card" style={{ marginTop: '24px' }}>
        <div className="ff-card-header">
          <div>
            <div className="ff-card-title">
              <Flame size={18} color="var(--accent-primary)" />
              Adaptive Fault Schedule (Milestone 4)
            </div>
            <div className="ff-card-desc">
              Progressively alter simulated latency and failure probability during sequential request execution.
            </div>
          </div>

          {/* Schedule Mode Selector */}
          <div style={{ display: 'flex', gap: '6px', background: 'var(--bg-surface-2)', padding: '4px', borderRadius: 'var(--radius-md)' }}>
            <button
              type="button"
              className={`btn btn-sm ${scheduleMode === 'none' ? 'btn-primary' : 'btn-subtle'}`}
              onClick={() => setScheduleMode('none')}
            >
              Static Config
            </button>
            <button
              type="button"
              className={`btn btn-sm ${scheduleMode === 'constant' ? 'btn-primary' : 'btn-subtle'}`}
              onClick={() => setScheduleMode('constant')}
            >
              Constant
            </button>
            <button
              type="button"
              className={`btn btn-sm ${scheduleMode === 'step' ? 'btn-primary' : 'btn-subtle'}`}
              onClick={() => setScheduleMode('step')}
            >
              Step-Based
            </button>
            <button
              type="button"
              className={`btn btn-sm ${scheduleMode === 'ramped' ? 'btn-primary' : 'btn-subtle'}`}
              onClick={() => setScheduleMode('ramped')}
            >
              Ramped
            </button>
          </div>
        </div>

        {/* Schedule Mode: None */}
        {scheduleMode === 'none' && (
          <div style={{ padding: '20px', background: 'var(--bg-surface-2)', borderRadius: 'var(--radius-md)', fontSize: '0.88rem', color: 'var(--text-secondary)' }}>
            Static parameters will be applied uniformly across all {requestCount} requests:
            <strong> {artificialLatencyMs}ms artificial latency</strong> and <strong>{(failureProbability * 100).toFixed(1)}% simulated failure probability</strong>.
          </div>
        )}

        {/* Schedule Mode: Constant */}
        {scheduleMode === 'constant' && (
          <div style={{ padding: '20px', background: 'var(--bg-surface-2)', borderRadius: 'var(--radius-md)' }}>
            <div className="form-row-2">
              <div className="form-group" style={{ margin: 0 }}>
                <label className="form-label">Constant Latency (ms)</label>
                <input
                  type="number"
                  min="0"
                  className="form-input"
                  value={constLatency}
                  onChange={(e) => setConstLatency(Number(e.target.value))}
                />
              </div>
              <div className="form-group" style={{ margin: 0 }}>
                <label className="form-label">Constant Failure Probability (0.0 - 1.0)</label>
                <input
                  type="number"
                  step="0.05"
                  min="0"
                  max="1.0"
                  className="form-input"
                  value={constFailureProb}
                  onChange={(e) => setConstFailureProb(Number(e.target.value))}
                />
              </div>
            </div>
          </div>
        )}

        {/* Schedule Mode: Step-Based */}
        {scheduleMode === 'step' && (
          <div style={{ padding: '20px', background: 'var(--bg-surface-2)', borderRadius: 'var(--radius-md)' }}>
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '14px' }}>
              <span style={{ fontSize: '0.84rem', color: 'var(--text-secondary)' }}>
                Steps must have strictly ascending request thresholds. Clamped at schedule boundaries.
              </span>
              <button type="button" className="btn btn-secondary btn-sm" onClick={handleAddStep}>
                <Plus size={14} /> Add Step
              </button>
            </div>

            <div className="table-container">
              <table className="ff-table">
                <thead>
                  <tr>
                    <th>Step #</th>
                    <th>Request Threshold</th>
                    <th>Latency (ms)</th>
                    <th>Failure Probability (0.0 - 1.0)</th>
                    <th>Actions</th>
                  </tr>
                </thead>
                <tbody>
                  {steps.map((step, idx) => (
                    <tr key={idx}>
                      <td style={{ fontFamily: 'var(--font-mono)' }}>Step {idx + 1}</td>
                      <td>
                        <input
                          type="number"
                          min="1"
                          className="form-input"
                          style={{ maxWidth: '140px' }}
                          value={step.requests_threshold}
                          onChange={(e) =>
                            handleStepChange(idx, 'requests_threshold', Number(e.target.value))
                          }
                        />
                      </td>
                      <td>
                        <input
                          type="number"
                          min="0"
                          className="form-input"
                          style={{ maxWidth: '140px' }}
                          value={step.latency_ms}
                          onChange={(e) =>
                            handleStepChange(idx, 'latency_ms', Number(e.target.value))
                          }
                        />
                      </td>
                      <td>
                        <input
                          type="number"
                          step="0.05"
                          min="0"
                          max="1.0"
                          className="form-input"
                          style={{ maxWidth: '140px' }}
                          value={step.failure_probability}
                          onChange={(e) =>
                            handleStepChange(idx, 'failure_probability', Number(e.target.value))
                          }
                        />
                      </td>
                      <td>
                        <button
                          type="button"
                          className="btn btn-subtle btn-sm"
                          disabled={steps.length <= 1}
                          onClick={() => handleRemoveStep(idx)}
                          style={{ color: 'var(--color-error)' }}
                        >
                          <Trash2 size={15} />
                        </button>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </div>
        )}

        {/* Schedule Mode: Ramped */}
        {scheduleMode === 'ramped' && (
          <div style={{ padding: '20px', background: 'var(--bg-surface-2)', borderRadius: 'var(--radius-md)' }}>
            <p style={{ fontSize: '0.84rem', color: 'var(--text-secondary)', marginBottom: '16px' }}>
              Linearly interpolates latency and failure probability across a defined number of requests. Clamped to start values before start iteration and to end values at or beyond span completion.
            </p>
            <div className="form-row-3" style={{ marginBottom: '16px' }}>
              <div className="form-group" style={{ margin: 0 }}>
                <label className="form-label">Start Latency (ms)</label>
                <input
                  type="number"
                  min="0"
                  className="form-input"
                  value={rampStartLatency}
                  onChange={(e) => setRampStartLatency(Number(e.target.value))}
                />
              </div>
              <div className="form-group" style={{ margin: 0 }}>
                <label className="form-label">End Latency (ms)</label>
                <input
                  type="number"
                  min="0"
                  className="form-input"
                  value={rampEndLatency}
                  onChange={(e) => setRampEndLatency(Number(e.target.value))}
                />
              </div>
              <div className="form-group" style={{ margin: 0 }}>
                <label className="form-label">Ramp Requests (Span)</label>
                <input
                  type="number"
                  min="2"
                  className="form-input"
                  value={rampRequests}
                  onChange={(e) => setRampRequests(Number(e.target.value))}
                />
              </div>
            </div>

            <div className="form-row-3">
              <div className="form-group" style={{ margin: 0 }}>
                <label className="form-label">Start Failure Prob (0.0 - 1.0)</label>
                <input
                  type="number"
                  step="0.05"
                  min="0"
                  max="1.0"
                  className="form-input"
                  value={rampStartFail}
                  onChange={(e) => setRampStartFail(Number(e.target.value))}
                />
              </div>
              <div className="form-group" style={{ margin: 0 }}>
                <label className="form-label">End Failure Prob (0.0 - 1.0)</label>
                <input
                  type="number"
                  step="0.05"
                  min="0"
                  max="1.0"
                  className="form-input"
                  value={rampEndFail}
                  onChange={(e) => setRampEndFail(Number(e.target.value))}
                />
              </div>
              <div className="form-group" style={{ margin: 0 }}>
                <label className="form-label">Start Iteration #</label>
                <input
                  type="number"
                  min="1"
                  className="form-input"
                  value={rampStartIteration}
                  onChange={(e) => setRampStartIteration(Number(e.target.value))}
                />
              </div>
            </div>
          </div>
        )}
      </div>
    </div>
  );
};
