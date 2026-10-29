import React, { useState, useEffect } from 'react';
import {
  FileText,
  Search,
  RefreshCw,
  GitCompare,
  Download,
  Eye,
  Copy
} from 'lucide-react';
import type { ReportSummary } from '../types';
import { fetchSavedReports, fetchSingleReport, exportSavedReport } from '../api';

interface ReportsViewProps {
  onNavigate: (view: string, extra?: any) => void;
  initialSelectedRunId?: string | null;
}

export const ReportsView: React.FC<ReportsViewProps> = ({
  onNavigate,
  initialSelectedRunId,
}) => {
  const [reports, setReports] = useState<ReportSummary[]>([]);
  const [loading, setLoading] = useState(true);
  const [searchQuery, setSearchQuery] = useState('');
  const [selectedReport, setSelectedReport] = useState<any | null>(null);
  const [exportModal, setExportModal] = useState<{ format: string; content: string } | null>(null);

  const loadReports = async () => {
    setLoading(true);
    try {
      const data = await fetchSavedReports('reports');
      setReports(data);
    } catch (err) {
      console.error('Failed to load reports:', err);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    loadReports();
  }, []);

  useEffect(() => {
    if (initialSelectedRunId) {
      handleInspect(initialSelectedRunId);
    }
  }, [initialSelectedRunId]);

  const handleInspect = async (runId: string) => {
    try {
      const data = await fetchSingleReport(runId, 'reports');
      setSelectedReport(data);
    } catch (err: any) {
      alert(`Failed to load report: ${err.message}`);
    }
  };

  const handleExport = async (runId: string, format: 'prometheus' | 'otel') => {
    try {
      const content = await exportSavedReport(runId, format);
      setExportModal({ format, content });
    } catch (err: any) {
      alert(`Export error: ${err.message}`);
    }
  };

  const filteredReports = reports.filter(
    (r) =>
      r.scenario_name.toLowerCase().includes(searchQuery.toLowerCase()) ||
      r.run_id.toLowerCase().includes(searchQuery.toLowerCase())
  );

  return (
    <div className="view-content" style={{ animation: 'fadeIn 0.2s ease-out' }}>
      {/* Header */}
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '24px', flexWrap: 'wrap', gap: '16px' }}>
        <div>
          <h1 style={{ fontSize: '1.8rem', fontWeight: 800, letterSpacing: '-0.02em', marginBottom: '6px' }}>
            Persisted Execution Reports
          </h1>
          <p style={{ color: 'var(--text-secondary)', fontSize: '0.95rem' }}>
            Browse and inspect immutable execution artifacts preserved atomically on disk.
          </p>
        </div>
        <div style={{ display: 'flex', gap: '10px' }}>
          <button className="btn btn-secondary" onClick={loadReports} disabled={loading}>
            <RefreshCw size={15} className={loading ? 'animate-spin' : ''} />
            Refresh
          </button>
          <button className="btn btn-primary" onClick={() => onNavigate('new-test')}>
            New Run
          </button>
        </div>
      </div>

      {/* Filter & Search Bar */}
      <div className="ff-card" style={{ marginBottom: '24px', padding: '16px 20px' }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: '12px' }}>
          <Search size={18} color="var(--text-muted)" />
          <input
            type="text"
            className="form-input"
            style={{ border: 'none', background: 'transparent', padding: '6px 0', fontSize: '0.92rem' }}
            placeholder="Search reports by scenario name or run identifier..."
            value={searchQuery}
            onChange={(e) => setSearchQuery(e.target.value)}
          />
          {searchQuery && (
            <button className="btn btn-subtle btn-sm" onClick={() => setSearchQuery('')}>
              Clear
            </button>
          )}
        </div>
      </div>

      {/* Reports Table */}
      <div className="ff-card">
        {loading ? (
          <div style={{ padding: '60px 20px', textAlign: 'center', color: 'var(--text-muted)' }}>
            Loading saved execution reports from repository...
          </div>
        ) : filteredReports.length === 0 ? (
          <div className="empty-state">
            <div className="empty-icon">
              <FileText size={28} />
            </div>
            <div className="empty-title">
              {searchQuery ? 'No Reports Match Your Search' : 'No Execution Reports Saved Yet'}
            </div>
            <p className="empty-desc">
              {searchQuery
                ? `No reports matched "${searchQuery}". Try searching with a different term.`
                : 'Execute your first scenario to persist an atomic execution artifact.'}
            </p>
            {!searchQuery && (
              <button className="btn btn-primary" onClick={() => onNavigate('new-test')}>
                Configure a Scenario
              </button>
            )}
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
                {filteredReports.map((r) => {
                  const rate =
                    r.total_requests > 0
                      ? ((r.successful_requests / r.total_requests) * 100).toFixed(1)
                      : '0.0';
                  return (
                    <tr key={r.run_id}>
                      <td style={{ fontFamily: 'var(--font-mono)', fontSize: '0.82rem', color: 'var(--accent-primary)', fontWeight: 600 }}>
                        {r.run_id}
                      </td>
                      <td style={{ fontWeight: 600 }}>{r.scenario_name}</td>
                      <td style={{ fontSize: '0.8rem', color: 'var(--text-muted)' }}>
                        {new Date(r.created_at).toLocaleString()}
                      </td>
                      <td>
                        <span className="badge badge-neutral">{r.total_requests} reqs</span>
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
                            onClick={() => handleInspect(r.run_id)}
                          >
                            <Eye size={13} />
                            Inspect
                          </button>
                          <button
                            className="btn btn-subtle btn-sm"
                            onClick={() => onNavigate('comparison', { baselineId: r.run_id })}
                            title="Compare with another run"
                          >
                            <GitCompare size={14} />
                          </button>
                          <button
                            className="btn btn-subtle btn-sm"
                            onClick={() => handleExport(r.run_id, 'prometheus')}
                            title="Export metrics"
                          >
                            <Download size={14} />
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

      {/* Report Inspection Modal */}
      {selectedReport && (
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
            zIndex: 90,
          }}
          onClick={() => setSelectedReport(null)}
        >
          <div
            className="ff-card"
            style={{ maxWidth: '900px', width: '100%', maxHeight: '85vh', display: 'flex', flexDirection: 'column' }}
            onClick={(e) => e.stopPropagation()}
          >
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '20px', borderBottom: '1px solid var(--border-subtle)', paddingBottom: '16px' }}>
              <div>
                <h3 style={{ fontSize: '1.25rem', fontWeight: 800 }}>{selectedReport.scenario_name}</h3>
                <div style={{ fontSize: '0.8rem', fontFamily: 'var(--font-mono)', color: 'var(--accent-primary)', marginTop: '2px' }}>
                  {selectedReport.run_id} • {new Date(selectedReport.created_at).toLocaleString()}
                </div>
              </div>
              <div style={{ display: 'flex', gap: '8px' }}>
                <button
                  className="btn btn-secondary btn-sm"
                  onClick={() => handleExport(selectedReport.run_id, 'prometheus')}
                >
                  Prometheus
                </button>
                <button
                  className="btn btn-secondary btn-sm"
                  onClick={() => handleExport(selectedReport.run_id, 'otel')}
                >
                  OpenTelemetry
                </button>
                <button
                  className="btn btn-primary btn-sm"
                  onClick={() => {
                    const rid = selectedReport.run_id;
                    setSelectedReport(null);
                    onNavigate('comparison', { baselineId: rid });
                  }}
                >
                  <GitCompare size={14} /> Compare
                </button>
                <button className="btn btn-subtle btn-sm" onClick={() => setSelectedReport(null)}>
                  Close
                </button>
              </div>
            </div>

            {/* Metrics summary inside modal */}
            <div style={{ overflowY: 'auto', paddingRight: '6px' }}>
              <div className="kpi-grid" style={{ marginBottom: '20px' }}>
                <div className="kpi-card">
                  <div className="kpi-label">Total Requests</div>
                  <div className="kpi-value">{selectedReport.report.total_requests}</div>
                </div>
                <div className="kpi-card">
                  <div className="kpi-label">Successful (2xx)</div>
                  <div className="kpi-value" style={{ color: 'var(--color-success)' }}>
                    {selectedReport.report.successful_requests}
                  </div>
                </div>
                <div className="kpi-card">
                  <div className="kpi-label">Avg Latency</div>
                  <div className="kpi-value" style={{ fontFamily: 'var(--font-mono)' }}>
                    {selectedReport.report.average_latency_ms.toFixed(1)} ms
                  </div>
                </div>
                <div className="kpi-card">
                  <div className="kpi-label">Simulated Faults</div>
                  <div className="kpi-value" style={{ color: 'var(--accent-primary)' }}>
                    {selectedReport.report.simulated_fault_count}
                  </div>
                </div>
              </div>

              {/* Configuration parameters */}
              {selectedReport.config && (
                <div style={{ background: 'var(--bg-surface-2)', padding: '16px', borderRadius: 'var(--radius-md)', marginBottom: '20px' }}>
                  <div style={{ fontWeight: 600, fontSize: '0.88rem', marginBottom: '8px' }}>Execution Parameters</div>
                  <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(200px, 1fr))', gap: '8px', fontSize: '0.8rem', color: 'var(--text-secondary)' }}>
                    <div>Target URL: <strong style={{ color: 'var(--text-primary)' }}>{selectedReport.config.target_url}</strong></div>
                    <div>Timeout: <strong style={{ color: 'var(--text-primary)' }}>{selectedReport.config.timeout_seconds}s</strong></div>
                    <div>Deadline: <strong style={{ color: 'var(--text-primary)' }}>{selectedReport.config.total_deadline_seconds}s</strong></div>
                    <div>Seed: <strong style={{ color: 'var(--text-primary)' }}>{selectedReport.config.seed ?? 'None'}</strong></div>
                  </div>
                </div>
              )}

              {/* Raw JSON View */}
              <div style={{ fontWeight: 600, fontSize: '0.88rem', marginBottom: '8px' }}>Full Report JSON</div>
              <pre
                style={{
                  background: 'var(--bg-canvas)',
                  padding: '16px',
                  borderRadius: 'var(--radius-md)',
                  fontFamily: 'var(--font-mono)',
                  fontSize: '0.78rem',
                  border: '1px solid var(--border-subtle)',
                  maxHeight: '260px',
                  overflowY: 'auto',
                }}
              >
                {JSON.stringify(selectedReport, null, 2)}
              </pre>
            </div>
          </div>
        </div>
      )}

      {/* Export Output Modal */}
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
                Export: {exportModal.format.toUpperCase()}
              </div>
              <div style={{ display: 'flex', gap: '8px' }}>
                <button
                  className="btn btn-secondary btn-sm"
                  onClick={() => {
                    navigator.clipboard.writeText(exportModal.content);
                    alert('Copied to clipboard!');
                  }}
                >
                  <Copy size={14} /> Copy
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
