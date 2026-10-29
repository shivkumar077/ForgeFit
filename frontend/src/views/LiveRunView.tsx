import React, { useState, useEffect } from 'react';
import {
  Activity,
  AlertTriangle,
  Download,
  GitCompare,
  Copy,
  Check
} from 'lucide-react';
import type { RunState } from '../types';
import { fetchRunStatus, exportSavedReport } from '../api';

interface LiveRunViewProps {
  runId: string | null;
  onNavigate: (view: string, extra?: any) => void;
}

export const LiveRunView: React.FC<LiveRunViewProps> = ({ runId, onNavigate }) => {
  const [runState, setRunState] = useState<RunState | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [copiedId, setCopiedId] = useState(false);
  const [exportModal, setExportModal] = useState<{ format: string; content: string } | null>(null);
  const [isExporting, setIsExporting] = useState(false);

  useEffect(() => {
    if (!runId) return;

    let isMounted = true;
    let pollTimeout: number | undefined;

    const poll = async () => {
      try {
        const data = await fetchRunStatus(runId);
        if (isMounted) {
          setRunState(data);
          setError(null);

          if (data.status === 'queued' || data.status === 'running') {
            pollTimeout = window.setTimeout(poll, 350);
          }
        }
      } catch (err: any) {
        if (isMounted) {
          setError(err.message || 'Error tracking run execution');
        }
      }
    };

    poll();

    return () => {
      isMounted = false;
      if (pollTimeout) clearTimeout(pollTimeout);
    };
  }, [runId]);

  const handleCopyRunId = () => {
    if (runId) {
      navigator.clipboard.writeText(runId);
      setCopiedId(true);
      setTimeout(() => setCopiedId(false), 2000);
    }
  };

  const handleExport = async (format: 'prometheus' | 'otel') => {
    if (!runId) return;
    setIsExporting(true);
    try {
      const content = await exportSavedReport(runId, format);
      setExportModal({ format, content });
    } catch (err: any) {
      alert(`Export error: ${err.message}`);
    } finally {
      setIsExporting(false);
    }
  };

  if (!runId) {
    return (
      <div className="view-content" style={{ animation: 'fadeIn 0.2s ease-out' }}>
        <div className="empty-state ff-card">
          <div className="empty-icon">
            <Activity size={28} />
          </div>
          <div className="empty-title">No Active Execution Selected</div>
          <p className="empty-desc">
            Launch a new test scenario or select a saved report to inspect detailed execution outcomes.
          </p>
          <button className="btn btn-primary" onClick={() => onNavigate('new-test')}>
            Configure a Scenario
          </button>
        </div>
      </div>
    );
  }

  const report = runState?.report;
  const currentCount = runState?.progress?.current || (report ? report.total_requests : 0);
  const totalCount = runState?.progress?.total || (report ? report.total_requests : 1);
  const progressPercent = Math.min(100, Math.round((currentCount / totalCount) * 100));

  const status = runState?.status || 'queued';
  const isFinished = status === 'completed' || status === 'interrupted' || status === 'failed';

  const successRate =
    report && report.total_requests > 0
      ? ((report.successful_requests / report.total_requests) * 100).toFixed(1)
      : '0.0';

  return (
    <div className="view-content" style={{ animation: 'fadeIn 0.2s ease-out' }}>
      {/* Header bar */}
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', marginBottom: '24px', flexWrap: 'wrap', gap: '16px' }}>
        <div>
          <div style={{ display: 'flex', alignItems: 'center', gap: '10px', marginBottom: '6px' }}>
            <h1 style={{ fontSize: '1.7rem', fontWeight: 800, letterSpacing: '-0.02em' }}>
              {runState?.scenario_name || 'Resilience Execution'}
            </h1>
            <span
              className={`badge ${
                status === 'completed'
                  ? 'badge-success'
                  : status === 'running'
                  ? 'badge-warning'
                  : status === 'interrupted'
                  ? 'badge-info'
                  : status === 'failed'
                  ? 'badge-error'
                  : 'badge-neutral'
              }`}
              style={{ textTransform: 'uppercase', fontSize: '0.78rem' }}
            >
              {status === 'running' && <span className="status-dot" style={{ width: '6px', height: '6px' }} />}
              {status}
            </span>
          </div>

          <div style={{ display: 'flex', alignItems: 'center', gap: '12px', fontSize: '0.85rem', color: 'var(--text-secondary)' }}>
            <span style={{ fontFamily: 'var(--font-mono)', color: 'var(--accent-primary)' }}>{runId}</span>
            <button
              onClick={handleCopyRunId}
              style={{ background: 'none', border: 'none', color: 'var(--text-muted)', cursor: 'pointer', display: 'flex', alignItems: 'center' }}
              title="Copy Run ID"
            >
              {copiedId ? <Check size={14} color="var(--color-success)" /> : <Copy size={14} />}
            </button>
            {runState?.created_at && (
              <span>• Started {new Date(runState.created_at).toLocaleTimeString()}</span>
            )}
          </div>
        </div>

        {/* Action Toolbar */}
        <div style={{ display: 'flex', gap: '10px', flexWrap: 'wrap' }}>
          {isFinished && (
            <>
              <button
                className="btn btn-secondary btn-sm"
                onClick={() => handleExport('prometheus')}
                disabled={isExporting}
              >
                <Download size={14} />
                Prometheus Export
              </button>
              <button
                className="btn btn-secondary btn-sm"
                onClick={() => handleExport('otel')}
                disabled={isExporting}
              >
                <Download size={14} />
                OpenTelemetry JSON
              </button>
              <button
                className="btn btn-primary btn-sm"
                onClick={() => onNavigate('comparison', { baselineId: runId })}
              >
                <GitCompare size={14} />
                Compare Run
              </button>
            </>
          )}
          <button className="btn btn-subtle btn-sm" onClick={() => onNavigate('new-test')}>
            New Test
          </button>
        </div>
      </div>

      {/* Error Notice */}
      {(error || runState?.error) && (
        <div
          style={{
            padding: '16px',
            borderRadius: 'var(--radius-md)',
            backgroundColor: 'var(--color-error-subtle)',
            border: '1px solid rgba(244, 63, 94, 0.4)',
            marginBottom: '24px',
            display: 'flex',
            alignItems: 'center',
            gap: '12px',
          }}
        >
          <AlertTriangle size={20} color="var(--color-error)" />
          <div style={{ color: 'var(--color-error)', fontSize: '0.9rem' }}>
            <strong>Execution Error: </strong>
            {error || runState?.error}
          </div>
        </div>
      )}

      {/* Progress Bar Container */}
      <div className="ff-card" style={{ marginBottom: '24px', padding: '20px' }}>
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '8px', fontSize: '0.88rem' }}>
          <span style={{ fontWeight: 600 }}>
            {status === 'running' ? 'Sequential Execution in Progress...' : isFinished ? 'Execution Complete' : 'Queued'}
          </span>
          <span style={{ fontFamily: 'var(--font-mono)', color: 'var(--accent-primary)', fontWeight: 600 }}>
            Request {currentCount} of {totalCount} ({progressPercent}%)
          </span>
        </div>

        <div style={{ width: '100%', height: '10px', background: 'var(--bg-surface-2)', borderRadius: 'var(--radius-full)', overflow: 'hidden' }}>
          <div
            style={{
              width: `${progressPercent}%`,
              height: '100%',
              background: 'linear-gradient(90deg, #f59e0b 0%, #10b981 100%)',
              transition: 'width 0.25s ease-out',
              borderRadius: 'var(--radius-full)',
            }}
          />
        </div>
      </div>

      {/* Metric KPI Cards (Loaded from real report) */}
      {report && (
        <div className="kpi-grid">
          <div className="kpi-card">
            <div className="kpi-label">Total Requests</div>
            <div className="kpi-value">{report.total_requests}</div>
            <div className="kpi-subtext">Executed sequentially</div>
          </div>

          <div className="kpi-card">
            <div className="kpi-label">Success Rate</div>
            <div className="kpi-value" style={{ color: Number(successRate) >= 90 ? 'var(--color-success)' : 'var(--color-error)' }}>
              {successRate}%
            </div>
            <div className="kpi-subtext">{report.successful_requests} successful (2xx)</div>
          </div>

          <div className="kpi-card">
            <div className="kpi-label">Average Latency</div>
            <div className="kpi-value" style={{ fontFamily: 'var(--font-mono)' }}>
              {report.average_latency_ms.toFixed(1)} <span style={{ fontSize: '0.9rem', color: 'var(--text-muted)' }}>ms</span>
            </div>
            <div className="kpi-subtext">Mean across all iterations</div>
          </div>

          <div className="kpi-card">
            <div className="kpi-label">p95 Latency</div>
            <div className="kpi-value" style={{ fontFamily: 'var(--font-mono)' }}>
              {report.p95_latency_ms.toFixed(1)} <span style={{ fontSize: '0.9rem', color: 'var(--text-muted)' }}>ms</span>
            </div>
            <div className="kpi-subtext">Nearest-rank 95th percentile</div>
          </div>

          <div className="kpi-card">
            <div className="kpi-label">Simulated Faults</div>
            <div className="kpi-value" style={{ color: 'var(--accent-primary)' }}>
              {report.simulated_fault_count}
            </div>
            <div className="kpi-subtext">Injected locally (0 net calls)</div>
          </div>

          <div className="kpi-card">
            <div className="kpi-label">HTTP / Network Errors</div>
            <div className="kpi-value" style={{ color: report.failed_requests - report.simulated_fault_count > 0 ? 'var(--color-error)' : 'var(--text-muted)' }}>
              {report.failed_requests - report.simulated_fault_count}
            </div>
            <div className="kpi-subtext">
              {report.timeout_count} timeouts, {report.connection_error_count} conn errors
            </div>
          </div>
        </div>
      )}

      {/* Individual Outcomes Breakdown Table */}
      {report && report.outcomes && report.outcomes.length > 0 && (
        <div className="ff-card">
          <div className="ff-card-header">
            <div>
              <div className="ff-card-title">
                <Activity size={18} color="var(--color-info)" />
                Sequential Request Outcomes Breakdown
              </div>
              <div className="ff-card-desc">
                Chronological record of individual request latencies, status codes, and fault injection events.
              </div>
            </div>
          </div>

          <div className="table-container">
            <table className="ff-table">
              <thead>
                <tr>
                  <th>#</th>
                  <th>Status</th>
                  <th>Measured Latency</th>
                  <th>Classification</th>
                  <th>Target URL</th>
                  <th>Details / Error Message</th>
                </tr>
              </thead>
              <tbody>
                {report.outcomes.map((out) => {
                  let statusBadge = (
                    <span className="badge badge-success">
                      {out.status_code || 200} OK
                    </span>
                  );
                  if (out.simulated_fault) {
                    statusBadge = (
                      <span className="badge badge-warning">
                        Simulated Fault
                      </span>
                    );
                  } else if (!out.success) {
                    statusBadge = (
                      <span className="badge badge-error">
                        {out.status_code ? `HTTP ${out.status_code}` : out.failure_category || 'Error'}
                      </span>
                    );
                  }

                  return (
                    <tr key={out.iteration}>
                      <td style={{ fontFamily: 'var(--font-mono)', fontWeight: 600 }}>
                        #{out.iteration}
                      </td>
                      <td>{statusBadge}</td>
                      <td style={{ fontFamily: 'var(--font-mono)' }}>
                        <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
                          <span>{out.latency_ms.toFixed(1)} ms</span>
                          <div
                            style={{
                              width: `${Math.min(100, Math.max(8, out.latency_ms / 3))}px`,
                              height: '4px',
                              borderRadius: '2px',
                              backgroundColor: out.simulated_fault
                                ? 'var(--accent-primary)'
                                : out.success
                                ? 'var(--color-success)'
                                : 'var(--color-error)',
                            }}
                          />
                        </div>
                      </td>
                      <td>
                        {out.simulated_fault ? (
                          <span style={{ fontSize: '0.8rem', color: 'var(--accent-primary)' }}>Injected Fault</span>
                        ) : out.success ? (
                          <span style={{ fontSize: '0.8rem', color: 'var(--color-success)' }}>Live Success</span>
                        ) : (
                          <span style={{ fontSize: '0.8rem', color: 'var(--color-error)' }}>{out.failure_category}</span>
                        )}
                      </td>
                      <td style={{ fontFamily: 'var(--font-mono)', fontSize: '0.78rem', color: 'var(--text-secondary)' }}>
                        {out.target_url}
                      </td>
                      <td style={{ fontSize: '0.8rem', color: out.error_message ? 'var(--color-error)' : 'var(--text-muted)' }}>
                        {out.error_message || '—'}
                      </td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
        </div>
      )}

      {/* Export Modal / Drawer */}
      {exportModal && (
        <div
          style={{
            position: 'fixed',
            inset: 0,
            background: 'rgba(0, 0, 0, 0.75)',
            backdropFilter: 'blur(8px)',
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'center',
            padding: '24px',
            zIndex: 100,
          }}
          onClick={() => setExportModal(null)}
        >
          <div
            className="ff-card"
            style={{ maxWidth: '800px', width: '100%', maxHeight: '85vh', display: 'flex', flexDirection: 'column' }}
            onClick={(e) => e.stopPropagation()}
          >
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '16px' }}>
              <div style={{ fontWeight: 700, fontSize: '1.1rem' }}>
                Export Format: {exportModal.format.toUpperCase()}
              </div>
              <div style={{ display: 'flex', gap: '8px' }}>
                <button
                  className="btn btn-secondary btn-sm"
                  onClick={() => {
                    navigator.clipboard.writeText(exportModal.content);
                    alert('Copied metrics export to clipboard!');
                  }}
                >
                  <Copy size={14} /> Copy
                </button>
                <button
                  className="btn btn-primary btn-sm"
                  onClick={() => {
                    const blob = new Blob([exportModal.content], {
                      type: exportModal.format === 'prometheus' ? 'text/plain' : 'application/json',
                    });
                    const url = URL.createObjectURL(blob);
                    const a = document.createElement('a');
                    a.href = url;
                    a.download = `report_${runId}.${exportModal.format === 'prometheus' ? 'prom' : 'json'}`;
                    a.click();
                  }}
                >
                  <Download size={14} /> Download File
                </button>
                <button className="btn btn-subtle btn-sm" onClick={() => setExportModal(null)}>
                  Close
                </button>
              </div>
            </div>
            <pre
              style={{
                flex: 1,
                overflowY: 'auto',
                background: 'var(--bg-canvas)',
                padding: '16px',
                borderRadius: 'var(--radius-md)',
                fontFamily: 'var(--font-mono)',
                fontSize: '0.8rem',
                border: '1px solid var(--border-subtle)',
              }}
            >
              {exportModal.content}
            </pre>
          </div>
        </div>
      )}
    </div>
  );
};
