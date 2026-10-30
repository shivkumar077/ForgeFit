import React, { useState, useEffect } from 'react';
import {
  Flame,
  ArrowRight,
  ShieldCheck,
  Activity,
  Layers,
  GitCompare,
  Download,
  Sparkles,
  ExternalLink,
  CheckCircle2,
  AlertTriangle,
  Play
} from 'lucide-react';

interface LandingPageProps {
  onEnterApp: (targetView?: string) => void;
  apiConnected: boolean;
  version: string;
}

export const LandingPage: React.FC<LandingPageProps> = ({
  onEnterApp,
  apiConnected,
  version,
}) => {
  // Interactive Simulation State for Hero Animation
  const [simLatency, setSimLatency] = useState(85);
  const [simFaultProb, setSimFaultProb] = useState(0.2);
  const [simPackets, setSimPackets] = useState<Array<{ id: number; status: 'ok' | 'fault' | 'timeout'; latency: number }>>([]);
  const [packetCount, setPacketCount] = useState(0);

  useEffect(() => {
    const interval = setInterval(() => {
      setPacketCount((prev) => {
        const nextId = prev + 1;
        const isFault = Math.random() < simFaultProb;
        const currentLatency = Math.round(simLatency + (Math.random() * 20 - 10));
        const status = isFault ? 'fault' : 'ok';

        setSimPackets((packets) => [
          ...packets.slice(-5),
          { id: nextId, status, latency: currentLatency },
        ]);
        return nextId;
      });
    }, 1800);

    return () => clearInterval(interval);
  }, [simLatency, simFaultProb]);

  return (
    <div style={{ minHeight: '100vh', backgroundColor: 'var(--bg-canvas)', color: 'var(--text-primary)' }}>
      {/* Top Navigation */}
      <header
        style={{
          borderBottom: '1px solid var(--border-subtle)',
          backgroundColor: 'rgba(8, 12, 18, 0.85)',
          backdropFilter: 'blur(16px)',
          position: 'sticky',
          top: 0,
          zIndex: 50,
        }}
      >
        <div
          style={{
            maxWidth: '1280px',
            margin: '0 auto',
            padding: '16px 24px',
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'space-between',
          }}
        >
          <div style={{ display: 'flex', alignItems: 'center', gap: '12px', cursor: 'pointer' }} onClick={() => onEnterApp('overview')}>
            <div className="brand-mark">
              <Flame size={20} />
            </div>
            <div>
              <div style={{ fontWeight: 800, fontSize: '1.2rem', letterSpacing: '-0.02em', display: 'flex', alignItems: 'center', gap: '8px' }}>
                ForgeFit
                <span className="version-badge">v{version}</span>
              </div>
              <div style={{ fontSize: '0.7rem', color: 'var(--text-muted)', letterSpacing: '0.04em' }}>API RESILIENCE TOOLKIT</div>
            </div>
          </div>

          <nav style={{ display: 'flex', alignItems: 'center', gap: '28px' }}>
            <a href="#features" style={{ fontSize: '0.9rem', color: 'var(--text-secondary)', fontWeight: 500 }}>Features</a>
            <a href="#simulation" style={{ fontSize: '0.9rem', color: 'var(--text-secondary)', fontWeight: 500 }}>Simulator</a>
            <a href="#workflow" style={{ fontSize: '0.9rem', color: 'var(--text-secondary)', fontWeight: 500 }}>Workflow</a>
            <a href="#safety" style={{ fontSize: '0.9rem', color: 'var(--text-secondary)', fontWeight: 500 }}>Safety</a>
          </nav>

          <div style={{ display: 'flex', alignItems: 'center', gap: '14px' }}>
            <div className="api-status-badge">
              <span className={`status-dot ${apiConnected ? '' : 'offline'}`} />
              <span style={{ fontSize: '0.78rem' }}>{apiConnected ? 'Engine Ready' : 'API Connecting...'}</span>
            </div>
            <button className="btn btn-primary btn-sm" onClick={() => onEnterApp('overview')}>
              Launch Workspace
              <ArrowRight size={15} />
            </button>
          </div>
        </div>
      </header>

      {/* Hero Section */}
      <section style={{ padding: '80px 24px 60px', maxWidth: '1280px', margin: '0 auto', textAlign: 'center' }}>
        <div style={{ display: 'inline-flex', alignItems: 'center', gap: '8px', padding: '4px 14px', borderRadius: 'var(--radius-full)', background: 'var(--accent-subtle)', border: '1px solid rgba(245, 158, 11, 0.3)', marginBottom: '24px' }}>
          <Sparkles size={14} color="var(--accent-primary)" />
          <span style={{ fontSize: '0.8rem', fontWeight: 600, color: 'var(--accent-primary)' }}>Milestone 5 Production Release</span>
        </div>

        <h1 style={{ fontSize: 'clamp(2.4rem, 5.5vw, 4.2rem)', fontWeight: 800, letterSpacing: '-0.035em', lineHeight: 1.12, maxWidth: '960px', margin: '0 auto 24px', color: '#fff' }}>
          Stress-test APIs before <span style={{ color: 'var(--accent-primary)', textDecoration: 'underline decoration-amber-500/30' }}>production</span> does.
        </h1>

        <p style={{ fontSize: 'clamp(1rem, 2vw, 1.25rem)', color: 'var(--text-secondary)', maxWidth: '720px', margin: '0 auto 36px', lineHeight: 1.6 }}>
          Controlled latency injection, simulated fault schedules, deadline safety clamping, and automated run comparison — built for reliability engineers.
        </p>

        <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'center', gap: '16px', flexWrap: 'wrap', marginBottom: '60px' }}>
          <button className="btn btn-primary btn-lg" onClick={() => onEnterApp('new-test')}>
            <Play size={18} />
            Run a Resilience Test
          </button>
          <button className="btn btn-secondary btn-lg" onClick={() => onEnterApp('overview')}>
            Browse Saved Reports
            <Layers size={18} />
          </button>
        </div>

        {/* Live Interactive Simulator Visual Focal Point */}
        <div
          id="simulation"
          className="ff-card"
          style={{
            maxWidth: '1000px',
            margin: '0 auto',
            textAlign: 'left',
            position: 'relative',
            overflow: 'hidden',
            border: '1px solid rgba(245, 158, 11, 0.25)',
            background: 'linear-gradient(180deg, #0e1520 0%, #090d14 100%)',
            boxShadow: '0 24px 60px rgba(0,0,0,0.7), 0 0 30px rgba(245, 158, 11, 0.08)',
          }}
        >
          <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', borderBottom: '1px solid var(--border-subtle)', paddingBottom: '16px', marginBottom: '20px' }}>
            <div style={{ display: 'flex', alignItems: 'center', gap: '10px' }}>
              <div style={{ width: '10px', height: '10px', borderRadius: '50%', background: 'var(--color-success)', boxShadow: '0 0 8px var(--color-success)' }} />
              <span style={{ fontFamily: 'var(--font-mono)', fontSize: '0.85rem', fontWeight: 600, color: 'var(--text-secondary)' }}>
                interactive_fault_injector.simulation
              </span>
            </div>
            <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
              <span style={{ fontSize: '0.75rem', color: 'var(--text-muted)' }}>Packet Feed:</span>
              <span className="badge badge-info">{packetCount} packets simulated</span>
            </div>
          </div>

          {/* Interactive controls */}
          <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(280px, 1fr))', gap: '20px', marginBottom: '24px', background: 'var(--bg-surface-2)', padding: '16px', borderRadius: 'var(--radius-md)' }}>
            <div>
              <div style={{ display: 'flex', justifyContent: 'space-between', fontSize: '0.82rem', marginBottom: '6px' }}>
                <span style={{ color: 'var(--text-secondary)' }}>Simulated Latency:</span>
                <span style={{ fontFamily: 'var(--font-mono)', color: 'var(--accent-primary)', fontWeight: 600 }}>{simLatency} ms</span>
              </div>
              <input
                type="range"
                min="10"
                max="400"
                value={simLatency}
                onChange={(e) => setSimLatency(Number(e.target.value))}
                style={{ width: '100%', accentColor: 'var(--accent-primary)' }}
              />
            </div>
            <div>
              <div style={{ display: 'flex', justifyContent: 'space-between', fontSize: '0.82rem', marginBottom: '6px' }}>
                <span style={{ color: 'var(--text-secondary)' }}>Simulated Failure Probability:</span>
                <span style={{ fontFamily: 'var(--font-mono)', color: 'var(--color-error)', fontWeight: 600 }}>{(simFaultProb * 100).toFixed(0)}%</span>
              </div>
              <input
                type="range"
                min="0"
                max="0.8"
                step="0.05"
                value={simFaultProb}
                onChange={(e) => setSimFaultProb(Number(e.target.value))}
                style={{ width: '100%', accentColor: 'var(--color-error)' }}
              />
            </div>
          </div>

          {/* Pipeline flow */}
          <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', gap: '12px', padding: '24px 16px', background: 'rgba(0,0,0,0.3)', borderRadius: 'var(--radius-md)', overflowX: 'auto', marginBottom: '18px' }}>
            <div style={{ textAlign: 'center', minWidth: '110px' }}>
              <div style={{ width: '42px', height: '42px', borderRadius: '8px', background: 'var(--bg-surface-3)', border: '1px solid var(--border-subtle)', display: 'flex', alignItems: 'center', justifyContent: 'center', margin: '0 auto 8px' }}>
                <Activity size={20} color="var(--color-info)" />
              </div>
              <div style={{ fontSize: '0.76rem', fontWeight: 600 }}>Client Engine</div>
              <div style={{ fontSize: '0.68rem', color: 'var(--text-muted)' }}>Loopback Safe</div>
            </div>

            <div style={{ flex: 1, height: '2px', background: 'var(--border-strong)', position: 'relative', overflow: 'hidden' }}>
              <div style={{ position: 'absolute', top: 0, left: 0, height: '100%', width: '40px', background: 'var(--accent-primary)', animation: 'sparkTravel 1.6s infinite linear' }} />
            </div>

            <div style={{ textAlign: 'center', minWidth: '140px' }}>
              <div style={{ width: '42px', height: '42px', borderRadius: '8px', background: 'rgba(245, 158, 11, 0.15)', border: '1px solid var(--border-accent)', display: 'flex', alignItems: 'center', justifyContent: 'center', margin: '0 auto 8px' }}>
                <Flame size={20} color="var(--accent-primary)" />
              </div>
              <div style={{ fontSize: '0.76rem', fontWeight: 600 }}>Fault Scheduler</div>
              <div style={{ fontSize: '0.68rem', color: 'var(--accent-primary)' }}>+{simLatency}ms / {Math.round(simFaultProb * 100)}% fail</div>
            </div>

            <div style={{ flex: 1, height: '2px', background: 'var(--border-strong)', position: 'relative', overflow: 'hidden' }}>
              <div style={{ position: 'absolute', top: 0, left: 0, height: '100%', width: '40px', background: 'var(--color-info)', animation: 'sparkTravel 1.6s infinite linear 0.8s' }} />
            </div>

            <div style={{ textAlign: 'center', minWidth: '110px' }}>
              <div style={{ width: '42px', height: '42px', borderRadius: '8px', background: 'var(--bg-surface-3)', border: '1px solid var(--border-subtle)', display: 'flex', alignItems: 'center', justifyContent: 'center', margin: '0 auto 8px' }}>
                <ShieldCheck size={20} color="var(--color-success)" />
              </div>
              <div style={{ fontSize: '0.76rem', fontWeight: 600 }}>Target Service</div>
              <div style={{ fontSize: '0.68rem', color: 'var(--text-muted)' }}>Localhost Guarded</div>
            </div>
          </div>

          {/* Recent live outcome stream */}
          <div style={{ display: 'flex', gap: '10px', overflowX: 'auto', paddingBottom: '6px' }}>
            {simPackets.map((pkt) => (
              <div
                key={pkt.id}
                style={{
                  padding: '8px 12px',
                  borderRadius: 'var(--radius-sm)',
                  backgroundColor: pkt.status === 'fault' ? 'var(--color-error-subtle)' : 'var(--color-success-subtle)',
                  border: `1px solid ${pkt.status === 'fault' ? 'rgba(244,63,94,0.3)' : 'rgba(16,185,129,0.3)'}`,
                  fontSize: '0.74rem',
                  fontFamily: 'var(--font-mono)',
                  display: 'flex',
                  alignItems: 'center',
                  gap: '8px',
                  whiteSpace: 'nowrap',
                }}
              >
                {pkt.status === 'fault' ? (
                  <>
                    <AlertTriangle size={13} color="var(--color-error)" />
                    <span style={{ color: 'var(--color-error)' }}>REQ #{pkt.id}: SIMULATED_FAULT ({pkt.latency}ms)</span>
                  </>
                ) : (
                  <>
                    <CheckCircle2 size={13} color="var(--color-success)" />
                    <span style={{ color: 'var(--color-success)' }}>REQ #{pkt.id}: 200 OK ({pkt.latency}ms)</span>
                  </>
                )}
              </div>
            ))}
          </div>
        </div>
      </section>

      {/* Features Grid */}
      <section id="features" style={{ padding: '80px 24px', maxWidth: '1280px', margin: '0 auto' }}>
        <div style={{ textAlign: 'center', marginBottom: '56px' }}>
          <h2 style={{ fontSize: '2.2rem', fontWeight: 800, letterSpacing: '-0.02em', marginBottom: '12px' }}>
            Built for Systematic Reliability
          </h2>
          <p style={{ color: 'var(--text-secondary)', fontSize: '1.05rem', maxWidth: '640px', margin: '0 auto' }}>
            Everything needed to uncover architectural vulnerabilities without deploying complex or heavy test infrastructure.
          </p>
        </div>

        <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(280px, 1fr))', gap: '24px' }}>
          <div className="ff-card">
            <div style={{ width: '40px', height: '40px', borderRadius: '8px', background: 'var(--accent-subtle)', border: '1px solid var(--border-accent)', display: 'flex', alignItems: 'center', justifyContent: 'center', marginBottom: '16px' }}>
              <Layers size={20} color="var(--accent-primary)" />
            </div>
            <h3 style={{ fontSize: '1.15rem', fontWeight: 700, marginBottom: '8px' }}>Reusable Scenarios</h3>
            <p style={{ color: 'var(--text-secondary)', fontSize: '0.88rem', lineHeight: 1.6 }}>
              Define named resilience benchmarks with target URLs, request counts, socket timeouts, and deadlines in version-controlled JSON.
            </p>
          </div>

          <div className="ff-card">
            <div style={{ width: '40px', height: '40px', borderRadius: '8px', background: 'rgba(6, 182, 212, 0.12)', border: '1px solid rgba(6, 182, 212, 0.3)', display: 'flex', alignItems: 'center', justifyContent: 'center', marginBottom: '16px' }}>
              <Activity size={20} color="var(--color-info)" />
            </div>
            <h3 style={{ fontSize: '1.15rem', fontWeight: 700, marginBottom: '8px' }}>Adaptive Fault Schedules</h3>
            <p style={{ color: 'var(--text-secondary)', fontSize: '0.88rem', lineHeight: 1.6 }}>
              Progressively stress dependencies with Constant, Step-based thresholds, or linearly Ramped latency and failure injections.
            </p>
          </div>

          <div className="ff-card">
            <div style={{ width: '40px', height: '40px', borderRadius: '8px', background: 'rgba(16, 185, 129, 0.12)', border: '1px solid rgba(16, 185, 129, 0.3)', display: 'flex', alignItems: 'center', justifyContent: 'center', marginBottom: '16px' }}>
              <GitCompare size={20} color="var(--color-success)" />
            </div>
            <h3 style={{ fontSize: '1.15rem', fontWeight: 700, marginBottom: '8px' }}>Run Comparison & Deltas</h3>
            <p style={{ color: 'var(--text-secondary)', fontSize: '0.88rem', lineHeight: 1.6 }}>
              Compare baseline vs. candidate runs across p95 latency, error rates, and timeouts with automated directional assessment.
            </p>
          </div>

          <div className="ff-card">
            <div style={{ width: '40px', height: '40px', borderRadius: '8px', background: 'rgba(234, 179, 8, 0.12)', border: '1px solid rgba(234, 179, 8, 0.3)', display: 'flex', alignItems: 'center', justifyContent: 'center', marginBottom: '16px' }}>
              <Download size={20} color="var(--color-warning)" />
            </div>
            <h3 style={{ fontSize: '1.15rem', fontWeight: 700, marginBottom: '8px' }}>Telemetry Export</h3>
            <p style={{ color: 'var(--text-secondary)', fontSize: '0.88rem', lineHeight: 1.6 }}>
              Export completed report metrics in Prometheus text exposition format or OpenTelemetry OTLP JSON without external collectors.
            </p>
          </div>
        </div>
      </section>

      {/* Workflow Section */}
      <section id="workflow" style={{ padding: '80px 24px', backgroundColor: 'var(--bg-surface-1)', borderTop: '1px solid var(--border-subtle)', borderBottom: '1px solid var(--border-subtle)' }}>
        <div style={{ maxWidth: '1280px', margin: '0 auto' }}>
          <div style={{ textAlign: 'center', marginBottom: '56px' }}>
            <h2 style={{ fontSize: '2.2rem', fontWeight: 800, letterSpacing: '-0.02em', marginBottom: '12px' }}>
              Three Steps from Setup to Resilience Insights
            </h2>
            <p style={{ color: 'var(--text-secondary)', fontSize: '1.05rem', maxWidth: '600px', margin: '0 auto' }}>
              A frictionless workflow designed for continuous integration and local evaluation.
            </p>
          </div>

          <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(300px, 1fr))', gap: '32px' }}>
            <div style={{ position: 'relative', padding: '24px', background: 'var(--bg-surface-2)', borderRadius: 'var(--radius-lg)', border: '1px solid var(--border-subtle)' }}>
              <div style={{ fontFamily: 'var(--font-mono)', fontSize: '1.5rem', fontWeight: 800, color: 'var(--accent-primary)', marginBottom: '12px' }}>01</div>
              <h3 style={{ fontSize: '1.2rem', fontWeight: 700, marginBottom: '8px' }}>Configure Scenario</h3>
              <p style={{ color: 'var(--text-secondary)', fontSize: '0.9rem', lineHeight: 1.6 }}>
                Set your target endpoint, iteration limits, socket timeouts, and choose an optional constant, step, or ramped fault schedule.
              </p>
            </div>

            <div style={{ position: 'relative', padding: '24px', background: 'var(--bg-surface-2)', borderRadius: 'var(--radius-lg)', border: '1px solid var(--border-subtle)' }}>
              <div style={{ fontFamily: 'var(--font-mono)', fontSize: '1.5rem', fontWeight: 800, color: 'var(--color-info)', marginBottom: '12px' }}>02</div>
              <h3 style={{ fontSize: '1.2rem', fontWeight: 700, marginBottom: '8px' }}>Controlled Execution</h3>
              <p style={{ color: 'var(--text-secondary)', fontSize: '0.9rem', lineHeight: 1.6 }}>
                Dispatch requests sequentially with loopback safety enforcement, total deadline clamping, and monotonic timing.
              </p>
            </div>

            <div style={{ position: 'relative', padding: '24px', background: 'var(--bg-surface-2)', borderRadius: 'var(--radius-lg)', border: '1px solid var(--border-subtle)' }}>
              <div style={{ fontFamily: 'var(--font-mono)', fontSize: '1.5rem', fontWeight: 800, color: 'var(--color-success)', marginBottom: '12px' }}>03</div>
              <h3 style={{ fontSize: '1.2rem', fontWeight: 700, marginBottom: '8px' }}>Analyze & Compare</h3>
              <p style={{ color: 'var(--text-secondary)', fontSize: '0.9rem', lineHeight: 1.6 }}>
                Inspect atomic JSON reports, measure performance deltas against baselines, and stream Prometheus/OTel metrics to observability stacks.
              </p>
            </div>
          </div>
        </div>
      </section>

      {/* Safety Section */}
      <section id="safety" style={{ padding: '80px 24px', maxWidth: '1280px', margin: '0 auto' }}>
        <div className="ff-card" style={{ background: 'linear-gradient(135deg, #101926 0%, #0c121c 100%)', border: '1px solid var(--border-strong)', padding: '40px' }}>
          <div style={{ display: 'flex', alignItems: 'flex-start', gap: '20px', flexWrap: 'wrap' }}>
            <div style={{ width: '48px', height: '48px', borderRadius: '12px', background: 'rgba(16, 185, 129, 0.15)', border: '1px solid rgba(16, 185, 129, 0.3)', display: 'flex', alignItems: 'center', justifyContent: 'center', flexShrink: 0 }}>
              <ShieldCheck size={26} color="var(--color-success)" />
            </div>
            <div style={{ flex: 1, minWidth: '280px' }}>
              <h2 style={{ fontSize: '1.6rem', fontWeight: 800, marginBottom: '8px' }}>Non-Negotiable Safety Safeguards</h2>
              <p style={{ color: 'var(--text-secondary)', fontSize: '0.95rem', lineHeight: 1.6, marginBottom: '20px' }}>
                ForgeFit is built with defense-in-depth boundaries to guarantee your testing never accidentally attacks production or runs uncontrollably.
              </p>
              <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(260px, 1fr))', gap: '16px' }}>
                <div style={{ display: 'flex', alignItems: 'center', gap: '10px', fontSize: '0.88rem' }}>
                  <CheckCircle2 size={16} color="var(--color-success)" />
                  <span>Loopback-only by default (localhost/127.0.0.1)</span>
                </div>
                <div style={{ display: 'flex', alignItems: 'center', gap: '10px', fontSize: '0.88rem' }}>
                  <CheckCircle2 size={16} color="var(--color-success)" />
                  <span>Mandatory dual-flag authorization for external targets</span>
                </div>
                <div style={{ display: 'flex', alignItems: 'center', gap: '10px', fontSize: '0.88rem' }}>
                  <CheckCircle2 size={16} color="var(--color-success)" />
                  <span>Total run wall-clock deadline bounding</span>
                </div>
                <div style={{ display: 'flex', alignItems: 'center', gap: '10px', fontSize: '0.88rem' }}>
                  <CheckCircle2 size={16} color="var(--color-success)" />
                  <span>Strict credential & response body omission</span>
                </div>
              </div>
            </div>
          </div>
        </div>
      </section>

      {/* Footer */}
      <footer style={{ borderTop: '1px solid var(--border-subtle)', padding: '40px 24px', backgroundColor: 'var(--bg-surface-1)' }}>
        <div style={{ maxWidth: '1280px', margin: '0 auto', display: 'flex', alignItems: 'center', justifyContent: 'space-between', flexWrap: 'wrap', gap: '20px' }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: '10px' }}>
            <div className="brand-mark" style={{ width: '28px', height: '28px' }}>
              <Flame size={15} />
            </div>
            <span style={{ fontWeight: 700 }}>ForgeFit</span>
            <span style={{ color: 'var(--text-muted)', fontSize: '0.85rem' }}>— API Resilience Testing Toolkit</span>
          </div>

          <div style={{ fontSize: '0.85rem', color: 'var(--text-secondary)', display: 'flex', flexWrap: 'wrap', alignItems: 'center', gap: '14px' }}>
            <span>Created by <strong style={{ color: 'var(--text-primary)' }}>Shiv Kumar</strong></span>
            <span>•</span>
            <a
              href="https://github.com/shivkumar077"
              target="_blank"
              rel="noreferrer"
              style={{ display: 'flex', alignItems: 'center', gap: '4px', color: 'var(--accent-primary)' }}
            >
              GitHub <ExternalLink size={13} />
            </a>
            <span>•</span>
            <a
              href="https://www.linkedin.com/in/shiv-kumar-399a32231/"
              target="_blank"
              rel="noreferrer"
              style={{ display: 'flex', alignItems: 'center', gap: '4px', color: '#38bdf8' }}
            >
              LinkedIn <ExternalLink size={13} />
            </a>
            <span>•</span>
            <span>MIT License</span>
          </div>
        </div>
      </footer>
    </div>
  );
};
