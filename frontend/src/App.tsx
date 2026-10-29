import React, { useState, useEffect } from 'react';
import {
  Flame,
  LayoutDashboard,
  Play,
  Activity,
  FileText,
  GitCompare,
  HelpCircle,
  Menu,
  X,
  ShieldCheck,
  Globe
} from 'lucide-react';
import { LandingPage } from './views/LandingPage';
import { OverviewView } from './views/OverviewView';
import { ScenarioBuilderView } from './views/ScenarioBuilderView';
import { LiveRunView } from './views/LiveRunView';
import { ReportsView } from './views/ReportsView';
import { ComparisonView } from './views/ComparisonView';
import { AboutView } from './views/AboutView';
import type { ApiStatus, ReportSummary } from './types';
import { fetchApiStatus, fetchSavedReports } from './api';
import './App.css';

export const App: React.FC = () => {
  // Navigation State
  const [currentMode, setCurrentMode] = useState<'landing' | 'app'>('landing');
  const [activeTab, setActiveTab] = useState<'overview' | 'new-test' | 'live-run' | 'reports' | 'comparison' | 'about'>('overview');
  const [mobileNavOpen, setMobileNavOpen] = useState(false);

  // Workflow State Pass-throughs
  const [activeRunId, setActiveRunId] = useState<string | null>(null);
  const [comparisonBaselineId, setComparisonBaselineId] = useState<string | null>(null);
  const [inspectReportId, setInspectReportId] = useState<string | null>(null);
  const [selectedPreset, setSelectedPreset] = useState<string | null>(null);

  // Global Backend Status & Data
  const [apiStatus, setApiStatus] = useState<ApiStatus | null>(null);
  const [apiConnected, setApiConnected] = useState(false);
  const [reports, setReports] = useState<ReportSummary[]>([]);

  const refreshGlobalData = async () => {
    try {
      const statusData = await fetchApiStatus();
      setApiStatus(statusData);
      setApiConnected(true);
    } catch {
      setApiConnected(false);
    }

    try {
      const reportsData = await fetchSavedReports('reports');
      setReports(reportsData);
    } catch (err) {
      console.error('Failed to load reports:', err);
    }
  };

  useEffect(() => {
    refreshGlobalData();
    const interval = setInterval(refreshGlobalData, 10000);
    return () => clearInterval(interval);
  }, []);

  const handleEnterApp = (targetView?: string) => {
    setCurrentMode('app');
    if (targetView) {
      setActiveTab(targetView as any);
    }
    window.scrollTo({ top: 0, behavior: 'smooth' });
  };

  const handleNavigate = (view: string, extra?: any) => {
    setActiveTab(view as any);
    setMobileNavOpen(false);

    if (extra?.selectedRunId) {
      setInspectReportId(extra.selectedRunId);
    }
    if (extra?.baselineId) {
      setComparisonBaselineId(extra.baselineId);
    }
    window.scrollTo({ top: 0, behavior: 'smooth' });
  };

  const handleRunStarted = (runId: string) => {
    setActiveRunId(runId);
    setActiveTab('live-run');
    refreshGlobalData();
  };

  const handleSelectPreset = (presetKey: string) => {
    setSelectedPreset(presetKey);
    setActiveTab('new-test');
  };

  if (currentMode === 'landing') {
    return (
      <LandingPage
        onEnterApp={handleEnterApp}
        apiConnected={apiConnected}
        version={apiStatus?.version || '0.1.0'}
      />
    );
  }

  return (
    <div className="app-container">
      {/* Sidebar Navigation */}
      <aside className={`app-sidebar ${mobileNavOpen ? 'open' : ''}`}>
        <div className="sidebar-header">
          <div className="brand-mark" style={{ cursor: 'pointer' }} onClick={() => setCurrentMode('landing')}>
            <Flame size={20} />
          </div>
          <div className="brand-text">
            <h1>
              ForgeFit
              <span className="version-badge">v{apiStatus?.version || '0.1.0'}</span>
            </h1>
            <div className="brand-tagline">API Resilience Toolkit</div>
          </div>
        </div>

        <nav className="sidebar-nav">
          <button
            className={`nav-item ${activeTab === 'overview' ? 'active' : ''}`}
            onClick={() => handleNavigate('overview')}
          >
            <LayoutDashboard size={18} />
            <span>Overview</span>
          </button>

          <button
            className={`nav-item ${activeTab === 'new-test' ? 'active' : ''}`}
            onClick={() => handleNavigate('new-test')}
          >
            <Play size={18} />
            <span>New Test Scenario</span>
          </button>

          <button
            className={`nav-item ${activeTab === 'live-run' ? 'active' : ''}`}
            onClick={() => handleNavigate('live-run')}
          >
            <Activity size={18} />
            <span>Live Execution</span>
            {activeRunId && (
              <span className="badge badge-warning" style={{ marginLeft: 'auto', fontSize: '0.65rem' }}>
                Active
              </span>
            )}
          </button>

          <button
            className={`nav-item ${activeTab === 'reports' ? 'active' : ''}`}
            onClick={() => handleNavigate('reports')}
          >
            <FileText size={18} />
            <span>Saved Reports</span>
            <span className="badge badge-neutral" style={{ marginLeft: 'auto', fontSize: '0.65rem' }}>
              {reports.length}
            </span>
          </button>

          <button
            className={`nav-item ${activeTab === 'comparison' ? 'active' : ''}`}
            onClick={() => handleNavigate('comparison')}
          >
            <GitCompare size={18} />
            <span>Run Comparison</span>
          </button>

          <button
            className={`nav-item ${activeTab === 'about' ? 'active' : ''}`}
            onClick={() => handleNavigate('about')}
          >
            <HelpCircle size={18} />
            <span>About ForgeFit</span>
          </button>
        </nav>

        <div className="sidebar-footer">
          <div className="api-status-badge">
            <span className={`status-dot ${apiConnected ? '' : 'offline'}`} />
            <span>{apiConnected ? 'FastAPI Backend Online' : 'Connecting to API...'}</span>
          </div>

          <button
            className="btn btn-subtle btn-sm"
            style={{ width: '100%', justifyContent: 'flex-start', padding: '6px 8px', fontSize: '0.78rem' }}
            onClick={() => setCurrentMode('landing')}
          >
            <Globe size={14} />
            Return to Landing Page
          </button>
        </div>
      </aside>

      {/* Main Workspace Area */}
      <main className="app-main">
        {/* Top bar */}
        <header className="app-topbar">
          <div style={{ display: 'flex', alignItems: 'center', gap: '14px' }}>
            <button
              className="mobile-nav-toggle"
              onClick={() => setMobileNavOpen(!mobileNavOpen)}
              aria-label="Toggle navigation"
            >
              {mobileNavOpen ? <X size={20} /> : <Menu size={20} />}
            </button>
            <div className="topbar-title">
              {activeTab === 'overview' && 'Resilience Workspace'}
              {activeTab === 'new-test' && 'Scenario Configuration'}
              {activeTab === 'live-run' && 'Active Run Execution'}
              {activeTab === 'reports' && 'Persisted Reports'}
              {activeTab === 'comparison' && 'Run Comparison Engine'}
              {activeTab === 'about' && 'About ForgeFit'}
            </div>
          </div>

          <div className="topbar-actions">
            <div style={{ display: 'flex', alignItems: 'center', gap: '8px', fontSize: '0.8rem', color: 'var(--text-secondary)' }}>
              <ShieldCheck size={16} color="var(--color-success)" />
              <span className="badge badge-success">Loopback Guarded</span>
            </div>
            <button
              className="btn btn-primary btn-sm"
              onClick={() => handleNavigate('new-test')}
            >
              <Play size={14} />
              Run Test
            </button>
          </div>
        </header>

        {/* View Component Rendering */}
        {activeTab === 'overview' && (
          <OverviewView
            reports={reports}
            apiStatus={apiStatus}
            onNavigate={handleNavigate}
            onSelectPreset={handleSelectPreset}
          />
        )}

        {activeTab === 'new-test' && (
          <ScenarioBuilderView
            onRunStarted={handleRunStarted}
            initialPreset={selectedPreset}
          />
        )}

        {activeTab === 'live-run' && (
          <LiveRunView
            runId={activeRunId}
            onNavigate={handleNavigate}
          />
        )}

        {activeTab === 'reports' && (
          <ReportsView
            onNavigate={handleNavigate}
            initialSelectedRunId={inspectReportId}
          />
        )}

        {activeTab === 'comparison' && (
          <ComparisonView
            initialBaselineId={comparisonBaselineId}
            onNavigate={handleNavigate}
          />
        )}

        {activeTab === 'about' && <AboutView />}
      </main>
    </div>
  );
};

export default App;
