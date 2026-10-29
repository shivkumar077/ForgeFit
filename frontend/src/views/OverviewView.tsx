import React from 'react';
import {
  Layers,
  ArrowRight,
  Play,
  FileText,
  GitCompare,
  Flame
} from 'lucide-react';
import type { ReportSummary, ApiStatus } from '../types';

interface OverviewViewProps {
  reports: ReportSummary[];
  apiStatus: ApiStatus | null;
  onNavigate: (view: string, extra?: any) => void;
  onSelectPreset: (presetKey: string) => void;
}

export const OverviewView: React.FC<OverviewViewProps> = ({
  reports,
  apiStatus,
  onNavigate,
  onSelectPreset,
}) => {
  // Compute aggregate statistics across available reports
  const totalRuns = reports.length;
  const avgSuccessRate =
    totalRuns > 0
      ? (
          reports.reduce(
            (acc, r) =>
              acc + (r.total_requests > 0 ? (r.successful_requests / r.total_requests) * 100 : 0),
            0
          ) / totalRuns
        ).toFixed(1)
      : '0.0';

  const meanLatency =
    totalRuns > 0
      ? (reports.reduce((acc, r) => acc + r.average_latency_ms, 0) / totalRuns).toFixed(2)
      : '0.00';

  return (
    <div className="view-content" style={{ animation: 'fadeIn 0.2s ease-out' }}>
      {/* Top Banner */}
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', marginBottom: '28px', flexWrap: 'wrap', gap: '16px' }}>
        <div>
          <h1 style={{ fontSize: '1.8rem', fontWeight: 800, letterSpacing: '-0.02em', marginBottom: '6px' }}>
            Resilience Workspace Overview
          </h1>
          <p style={{ color: 'var(--text-secondary)', fontSize: '0.95rem' }}>
            Monitor executed API resilience tests, explore saved reports, or launch an adaptive fault scenario.
          </p>
        </div>
        <div style={{ display: 'flex', gap: '12px' }}>
          <button className="btn btn-primary" onClick={() => onNavigate('new-test')}>
            <Play size={16} />
            New Test Scenario
          </button>
        </div>
      </div>

      {/* KPI Metrics */}
      <div className="kpi-grid">
        <div className="kpi-card">
          <div className="kpi-label">Saved Execution Reports</div>
          <div className="kpi-value">{totalRuns}</div>
          <div className="kpi-subtext">Persisted in local repository</div>
        </div>

        <div className="kpi-card">
          <div className="kpi-label">Average Availability</div>
          <div className="kpi-value" style={{ color: Number(avgSuccessRate) >= 90 ? 'var(--color-success)' : 'var(--accent-primary)' }}>
            {avgSuccessRate}%
          </div>
          <div className="kpi-subtext">Across completed test runs</div>
        </div>

        <div className="kpi-card">
          <div className="kpi-label">Mean Measured Latency</div>
          <div className="kpi-value" style={{ fontFamily: 'var(--font-mono)' }}>
            {meanLatency} <span style={{ fontSize: '1rem', color: 'var(--text-muted)' }}>ms</span>
          </div>
          <div className="kpi-subtext">Including injected artificial delay</div>
        </div>

        <div className="kpi-card">
          <div className="kpi-label">Engine Capabilities</div>
          <div className="kpi-value" style={{ fontSize: '1.2rem', color: 'var(--color-info)' }}>
            {apiStatus?.supported_schedules.length || 3} Schedules
          </div>
          <div className="kpi-subtext">Constant, Step, Ramped</div>
        </div>
      </div>

      {/* Quick Launch Scenario Templates */}
      <div className="ff-card" style={{ marginBottom: '32px' }}>
        <div className="ff-card-header">
          <div>
            <div className="ff-card-title">
              <Flame size={18} color="var(--accent-primary)" />
              Quick Launch Scenario Templates
            </div>
            <div className="ff-card-desc">
              Pre-configured resilience evaluation benchmarks ready to execute or customize.
            </div>
          </div>
        </div>

        <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(260px, 1fr))', gap: '16px' }}>
          <div
            className="ff-card"
            style={{
              background: 'var(--bg-surface-2)',
              cursor: 'pointer',
              border: '1px solid var(--border-subtle)',
              padding: '18px',
            }}
            onClick={() => onSelectPreset('baseline')}
          >
            <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: '8px' }}>
              <span className="badge badge-success">Baseline</span>
              <ArrowRight size={16} color="var(--text-muted)" />
            </div>
            <div style={{ fontWeight: 700, fontSize: '1rem', marginBottom: '4px' }}>Localhost Baseline</div>
            <p style={{ fontSize: '0.8rem', color: 'var(--text-secondary)', marginBottom: '12px' }}>
              20 requests, 50ms latency, 5% simulated fault injection.
            </p>
            <div style={{ fontSize: '0.75rem', fontFamily: 'var(--font-mono)', color: 'var(--text-muted)' }}>
              Target: http://127.0.0.1:8080/health
            </div>
          </div>

          <div
            className="ff-card"
            style={{
              background: 'var(--bg-surface-2)',
              cursor: 'pointer',
              border: '1px solid var(--border-subtle)',
              padding: '18px',
            }}
            onClick={() => onSelectPreset('ramped')}
          >
            <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: '8px' }}>
              <span className="badge badge-warning">Ramped</span>
              <ArrowRight size={16} color="var(--text-muted)" />
            </div>
            <div style={{ fontWeight: 700, fontSize: '1rem', marginBottom: '4px' }}>Progressive Latency Ramp</div>
            <p style={{ fontSize: '0.8rem', color: 'var(--text-secondary)', marginBottom: '12px' }}>
              Linearly ramps latency (20ms to 200ms) & failure prob (0% to 30%).
            </p>
            <div style={{ fontSize: '0.75rem', fontFamily: 'var(--font-mono)', color: 'var(--text-muted)' }}>
              25 requests • start at #1
            </div>
          </div>

          <div
            className="ff-card"
            style={{
              background: 'var(--bg-surface-2)',
              cursor: 'pointer',
              border: '1px solid var(--border-subtle)',
              padding: '18px',
            }}
            onClick={() => onSelectPreset('step')}
          >
            <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: '8px' }}>
              <span className="badge badge-info">Step Threshold</span>
              <ArrowRight size={16} color="var(--text-muted)" />
            </div>
            <div style={{ fontWeight: 700, fontSize: '1rem', marginBottom: '4px' }}>Sudden Degradation Spike</div>
            <p style={{ fontSize: '0.8rem', color: 'var(--text-secondary)', marginBottom: '12px' }}>
              Normal performance until request #15, then jumps to 400ms & 50% faults.
            </p>
            <div style={{ fontSize: '0.75rem', fontFamily: 'var(--font-mono)', color: 'var(--text-muted)' }}>
              30 requests • 2 threshold steps
            </div>
          </div>

          <div
            className="ff-card"
            style={{
              background: 'var(--bg-surface-2)',
              cursor: 'pointer',
              border: '1px solid var(--border-subtle)',
              padding: '18px',
            }}
            onClick={() => onSelectPreset('timeout')}
          >
            <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: '8px' }}>
              <span className="badge badge-error">Safety Test</span>
              <ArrowRight size={16} color="var(--text-muted)" />
            </div>
            <div style={{ fontWeight: 700, fontSize: '1rem', marginBottom: '4px' }}>Deadline Clamping Probe</div>
            <p style={{ fontSize: '0.8rem', color: 'var(--text-secondary)', marginBottom: '12px' }}>
              Verifies that per-request socket timeouts are clamped to remaining budget.
            </p>
            <div style={{ fontSize: '0.75rem', fontFamily: 'var(--font-mono)', color: 'var(--text-muted)' }}>
              15 requests • 10.0s total deadline
            </div>
          </div>
        </div>
      </div>

      {/* Recent Saved Reports Table */}
      <div className="ff-card">
        <div className="ff-card-header">
          <div>
            <div className="ff-card-title">
              <FileText size={18} />
              Recent Saved Reports
            </div>
            <div className="ff-card-desc">
              Latest test execution artifacts stored atomically in the reports directory.
            </div>
          </div>
          <button className="btn btn-secondary btn-sm" onClick={() => onNavigate('reports')}>
            View All Reports ({totalRuns})
            <ArrowRight size={14} />
          </button>
        </div>

        {reports.length === 0 ? (
          <div className="empty-state">
            <div className="empty-icon">
              <Layers size={28} />
            </div>
            <div className="empty-title">No Execution Reports Saved Yet</div>
            <p className="empty-desc">
              Run your first resilience test scenario or launch one of the templates above to generate a persistent report.
            </p>
            <button className="btn btn-primary" onClick={() => onNavigate('new-test')}>
              Configure a Scenario
            </button>
          </div>
        ) : (
          <div className="table-container">
            <table className="ff-table">
              <thead>
                <tr>
                  <th>Run ID</th>
                  <th>Scenario Name</th>
                  <th>Execution Timestamp</th>
                  <th>Requests</th>
                  <th>Success Rate</th>
                  <th>Avg Latency</th>
                  <th>p95 Latency</th>
                  <th>Actions</th>
                </tr>
              </thead>
              <tbody>
                {reports.slice(0, 5).map((r) => {
                  const rate =
                    r.total_requests > 0
                      ? ((r.successful_requests / r.total_requests) * 100).toFixed(1)
                      : '0.0';
                  return (
                    <tr key={r.run_id}>
                      <td style={{ fontFamily: 'var(--font-mono)', fontSize: '0.82rem', color: 'var(--accent-primary)' }}>
                        {r.run_id}
                      </td>
                      <td style={{ fontWeight: 600 }}>{r.scenario_name}</td>
                      <td style={{ fontSize: '0.8rem', color: 'var(--text-muted)' }}>
                        {new Date(r.created_at).toLocaleString()}
                      </td>
                      <td>
                        <span className="badge badge-neutral">{r.total_requests}</span>
                      </td>
                      <td>
                        <span className={`badge ${Number(rate) >= 90 ? 'badge-success' : 'badge-warning'}`}>
                          {rate}%
                        </span>
                      </td>
                      <td style={{ fontFamily: 'var(--font-mono)' }}>{r.average_latency_ms.toFixed(1)} ms</td>
                      <td style={{ fontFamily: 'var(--font-mono)' }}>{r.p95_latency_ms.toFixed(1)} ms</td>
                      <td>
                        <div style={{ display: 'flex', gap: '8px' }}>
                          <button
                            className="btn btn-secondary btn-sm"
                            onClick={() => onNavigate('reports', { selectedRunId: r.run_id })}
                          >
                            Inspect
                          </button>
                          <button
                            className="btn btn-subtle btn-sm"
                            onClick={() => onNavigate('comparison', { baselineId: r.run_id })}
                          >
                            <GitCompare size={14} />
                            Compare
                          </button>
                        </div>
                      </td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
        )}
      </div>
    </div>
  );
};
