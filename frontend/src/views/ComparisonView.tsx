import React, { useState, useEffect } from 'react';
import {
  GitCompare,
  AlertTriangle,
  Info,
  Code2
} from 'lucide-react';
import type { ComparisonResult, ReportSummary } from '../types';
import { fetchSavedReports, compareSavedReports } from '../api';

interface ComparisonViewProps {
  initialBaselineId?: string | null;
  onNavigate: (view: string, extra?: any) => void;
}

export const ComparisonView: React.FC<ComparisonViewProps> = ({
  initialBaselineId,
  onNavigate,
}) => {
  const [reports, setReports] = useState<ReportSummary[]>([]);
  const [baselineId, setBaselineId] = useState<string>(initialBaselineId || '');
  const [comparisonId, setComparisonId] = useState<string>('');
  const [comparisonResult, setComparisonResult] = useState<ComparisonResult | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [showJson, setShowJson] = useState(false);

  useEffect(() => {
    const load = async () => {
      try {
        const data = await fetchSavedReports('reports');
        setReports(data);
        if (!baselineId && data.length > 0) {
          setBaselineId(data[0].run_id);
        }
        if (data.length > 1 && !comparisonId) {
          setComparisonId(data[1].run_id);
        }
      } catch (err: any) {
        console.error('Error fetching reports for comparison:', err);
      }
    };
    load();
  }, [initialBaselineId]);

  const handleRunComparison = async () => {
    if (!baselineId || !comparisonId) {
      setError('Please select both a Baseline and a Comparison report.');
      return;
    }
    setLoading(true);
    setError(null);
    try {
      const result = await compareSavedReports(baselineId, comparisonId, 'reports');
      setComparisonResult(result);
    } catch (err: any) {
      setError(err.message || 'Comparison failed');
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="view-content" style={{ animation: 'fadeIn 0.2s ease-out' }}>
      {/* Header */}
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '24px', flexWrap: 'wrap', gap: '16px' }}>
        <div>
          <h1 style={{ fontSize: '1.8rem', fontWeight: 800, letterSpacing: '-0.02em', marginBottom: '6px' }}>
            Resilience Run Comparison
          </h1>
          <p style={{ color: 'var(--text-secondary)', fontSize: '0.95rem' }}>
            Compare metrics between a baseline run and candidate run with automated directional assessment.
          </p>
        </div>
        {comparisonResult && (
          <button className="btn btn-secondary btn-sm" onClick={() => setShowJson(!showJson)}>
            <Code2 size={15} />
            {showJson ? 'Hide JSON' : 'Inspect JSON'}
          </button>
        )}
      </div>

      {/* Selectors Card */}
      <div className="ff-card" style={{ marginBottom: '24px' }}>
        <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(280px, 1fr))', gap: '20px', alignItems: 'flex-end' }}>
          <div className="form-group" style={{ margin: 0 }}>
            <label className="form-label">Baseline Run (Reference)</label>
            <select
              className="form-select"
              value={baselineId}
              onChange={(e) => setBaselineId(e.target.value)}
            >
              <option value="">Select baseline report...</option>
              {reports.map((r) => (
                <option key={r.run_id} value={r.run_id}>
                  {r.scenario_name} ({r.run_id.slice(-12)})
                </option>
              ))}
            </select>
          </div>

          <div className="form-group" style={{ margin: 0 }}>
            <label className="form-label">Comparison Run (Candidate)</label>
            <select
              className="form-select"
              value={comparisonId}
              onChange={(e) => setComparisonId(e.target.value)}
            >
              <option value="">Select comparison report...</option>
              {reports.map((r) => (
                <option key={r.run_id} value={r.run_id}>
                  {r.scenario_name} ({r.run_id.slice(-12)})
                </option>
              ))}
            </select>
          </div>

          <div>
            <button
              className="btn btn-primary"
              style={{ width: '100%' }}
              onClick={handleRunComparison}
              disabled={loading || !baselineId || !comparisonId}
            >
              <GitCompare size={16} />
              {loading ? 'Evaluating...' : 'Compare Runs'}
            </button>
          </div>
        </div>
      </div>

      {/* Error Notice */}
      {error && (
        <div
          style={{
            padding: '14px 18px',
            borderRadius: 'var(--radius-md)',
            backgroundColor: 'var(--color-error-subtle)',
            border: '1px solid rgba(244, 63, 94, 0.4)',
            marginBottom: '24px',
            color: 'var(--color-error)',
            fontSize: '0.88rem',
            display: 'flex',
            alignItems: 'center',
            gap: '10px',
          }}
        >
          <AlertTriangle size={18} />
          <span>{error}</span>
        </div>
      )}

      {/* JSON Viewer */}
      {showJson && comparisonResult && (
        <div className="ff-card" style={{ marginBottom: '24px', background: 'var(--bg-canvas)' }}>
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '12px' }}>
            <span style={{ fontFamily: 'var(--font-mono)', fontSize: '0.82rem', color: 'var(--accent-primary)' }}>
              Comparison Result JSON
            </span>
            <button
              className="btn btn-subtle btn-sm"
              onClick={() => navigator.clipboard.writeText(JSON.stringify(comparisonResult, null, 2))}
            >
              Copy
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
              maxHeight: '260px',
            }}
          >
            {JSON.stringify(comparisonResult, null, 2)}
          </pre>
        </div>
      )}

      {/* Comparison Results Card */}
      {comparisonResult && (
        <div className="ff-card">
          <div className="ff-card-header">
            <div>
              <div className="ff-card-title">
                <GitCompare size={18} color="var(--accent-primary)" />
                Resilience Run Comparison Breakdown
              </div>
              <div className="ff-card-desc">
                Baseline: <strong>{comparisonResult.baseline_scenario}</strong> ({comparisonResult.baseline_run_id}) vs. Comparison: <strong>{comparisonResult.comparison_scenario}</strong> ({comparisonResult.comparison_run_id})
              </div>
            </div>
          </div>

          {/* Warnings Banner */}
          {comparisonResult.warnings && comparisonResult.warnings.length > 0 && (
            <div
              style={{
                padding: '14px 18px',
                borderRadius: 'var(--radius-md)',
                backgroundColor: 'rgba(234, 179, 8, 0.1)',
                border: '1px solid rgba(234, 179, 8, 0.3)',
                marginBottom: '20px',
              }}
            >
              <div style={{ display: 'flex', alignItems: 'center', gap: '8px', color: 'var(--color-warning)', fontWeight: 600, fontSize: '0.85rem', marginBottom: '6px' }}>
                <AlertTriangle size={16} />
                Workload Divergence Warnings
              </div>
              <ul style={{ paddingLeft: '24px', fontSize: '0.82rem', color: 'var(--text-secondary)' }}>
                {comparisonResult.warnings.map((w, idx) => (
                  <li key={idx} style={{ marginBottom: '4px' }}>{w}</li>
                ))}
              </ul>
            </div>
          )}

          {/* Notes */}
          {comparisonResult.notes && comparisonResult.notes.length > 0 && (
            <div
              style={{
                padding: '12px 16px',
                borderRadius: 'var(--radius-md)',
                backgroundColor: 'var(--bg-surface-2)',
                border: '1px solid var(--border-subtle)',
                marginBottom: '20px',
                display: 'flex',
                alignItems: 'center',
                gap: '10px',
                fontSize: '0.82rem',
                color: 'var(--text-muted)',
              }}
            >
              <Info size={16} color="var(--color-info)" />
              <div>{comparisonResult.notes.join(' • ')}</div>
            </div>
          )}

          {/* Comparative Metrics Table */}
          <div className="table-container">
            <table className="ff-table">
              <thead>
                <tr>
                  <th>Metric</th>
                  <th>Baseline</th>
                  <th>Comparison</th>
                  <th>Absolute Diff</th>
                  <th>Percentage Diff</th>
                  <th>Assessment</th>
                </tr>
              </thead>
              <tbody>
                {Object.entries(comparisonResult.metrics).map(([key, m]) => {
                  let badge = <span className="badge badge-neutral">Neutral</span>;
                  if (m.direction === 'improved') {
                    badge = <span className="badge badge-success">Improved</span>;
                  } else if (m.direction === 'degraded') {
                    badge = <span className="badge badge-error">Degraded</span>;
                  } else if (m.direction === 'unchanged') {
                    badge = <span className="badge badge-neutral">Unchanged</span>;
                  }

                  const sign = m.absolute_diff > 0 ? '+' : '';
                  const pctSign = m.percentage_diff && m.percentage_diff > 0 ? '+' : '';

                  return (
                    <tr key={key}>
                      <td style={{ fontWeight: 600 }}>{m.metric_name}</td>
                      <td style={{ fontFamily: 'var(--font-mono)' }}>
                        {typeof m.baseline === 'number' ? m.baseline.toFixed(2) : m.baseline}
                      </td>
                      <td style={{ fontFamily: 'var(--font-mono)' }}>
                        {typeof m.comparison === 'number' ? m.comparison.toFixed(2) : m.comparison}
                      </td>
                      <td style={{ fontFamily: 'var(--font-mono)', fontWeight: 600 }}>
                        {sign}{typeof m.absolute_diff === 'number' ? m.absolute_diff.toFixed(2) : m.absolute_diff}
                      </td>
                      <td style={{ fontFamily: 'var(--font-mono)' }}>
                        {m.percentage_diff !== null ? `${pctSign}${m.percentage_diff.toFixed(1)}%` : 'N/A'}
                      </td>
                      <td>{badge}</td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
        </div>
      )}

      {/* Empty State before comparison */}
      {!comparisonResult && reports.length < 2 && (
        <div className="empty-state ff-card">
          <div className="empty-icon">
            <GitCompare size={28} />
          </div>
          <div className="empty-title">At Least Two Runs Required</div>
          <p className="empty-desc">
            To compare resilience characteristics and compute directional deltas, execute and persist at least two test runs.
          </p>
          <button className="btn btn-primary" onClick={() => onNavigate('new-test')}>
            Execute a Run
          </button>
        </div>
      )}
    </div>
  );
};
