import React from 'react';
import {
  Flame,
  ShieldCheck,
  Activity,
  Layers,
  GitCompare,
  ExternalLink,
  Code2
} from 'lucide-react';

export const AboutView: React.FC = () => {
  return (
    <div className="view-content" style={{ animation: 'fadeIn 0.2s ease-out', maxWidth: '1000px' }}>
      {/* Title Header */}
      <div style={{ marginBottom: '36px' }}>
        <div style={{ display: 'inline-flex', alignItems: 'center', gap: '8px', padding: '4px 12px', borderRadius: 'var(--radius-full)', background: 'var(--accent-subtle)', border: '1px solid rgba(245, 158, 11, 0.3)', marginBottom: '14px' }}>
          <Flame size={14} color="var(--accent-primary)" />
          <span style={{ fontSize: '0.78rem', fontWeight: 600, color: 'var(--accent-primary)' }}>Architecture & Principles</span>
        </div>
        <h1 style={{ fontSize: '2.2rem', fontWeight: 800, letterSpacing: '-0.025em', marginBottom: '10px' }}>
          About ForgeFit
        </h1>
        <p style={{ color: 'var(--text-secondary)', fontSize: '1.05rem', lineHeight: 1.6 }}>
          ForgeFit is an open-source, Python-based API resilience testing toolkit designed to evaluate how client applications, microservices, and upstream dependencies behave under controlled adverse conditions.
        </p>
      </div>

      {/* Section 1: Why Resilience Testing Matters */}
      <div className="ff-card" style={{ marginBottom: '24px' }}>
        <div className="ff-card-title" style={{ marginBottom: '12px' }}>
          <Activity size={18} color="var(--accent-primary)" />
          Why API Resilience Testing Matters
        </div>
        <p style={{ color: 'var(--text-secondary)', fontSize: '0.92rem', lineHeight: 1.7, marginBottom: '14px' }}>
          Modern distributed systems rarely fail completely at once; instead, they degrade silently. Tail latencies increase, downstream microservices exhaust socket pools, retry storms amplify load, and unhandled connection timeouts cause cascading failures across independent service boundaries.
        </p>
        <p style={{ color: 'var(--text-secondary)', fontSize: '0.92rem', lineHeight: 1.7 }}>
          ForgeFit allows software teams to inject artificial latency, simulate intermittent failures, and test strict overall execution deadlines before deploying to production. By discovering weaknesses locally in CI/CD pipelines, engineers can configure robust timeouts, backoffs, and circuit breakers with empirical confidence.
        </p>
      </div>

      {/* Section 2: Scenarios & Fault Schedules */}
      <div className="ff-card" style={{ marginBottom: '24px' }}>
        <div className="ff-card-title" style={{ marginBottom: '12px' }}>
          <Layers size={18} color="var(--color-info)" />
          Scenarios & Adaptive Fault Progression
        </div>
        <p style={{ color: 'var(--text-secondary)', fontSize: '0.92rem', lineHeight: 1.7, marginBottom: '14px' }}>
          ForgeFit separates test definitions from execution logic through version-controlled <strong>Scenarios</strong>. A scenario encapsulates target endpoints, request volumes, socket timeouts, and optional <strong>Adaptive Fault Schedules</strong>:
        </p>
        <ul style={{ paddingLeft: '24px', fontSize: '0.9rem', color: 'var(--text-secondary)', lineHeight: 1.7 }}>
          <li style={{ marginBottom: '8px' }}>
            <strong style={{ color: 'var(--text-primary)' }}>Constant Schedule:</strong> Maintains a static artificial latency and simulated failure probability across every iteration.
          </li>
          <li style={{ marginBottom: '8px' }}>
            <strong style={{ color: 'var(--text-primary)' }}>Step-Based Schedule:</strong> Transitions latency or failure probability at configured request-count thresholds, strictly clamping to initial or final step values at boundaries.
          </li>
          <li style={{ marginBottom: '8px' }}>
            <strong style={{ color: 'var(--text-primary)' }}>Ramped Schedule:</strong> Progressively increases or decreases latency and failure probabilities linearly over a defined span of requests with automatic boundary clamping.
          </li>
        </ul>
      </div>

      {/* Section 3: Reports, Comparisons & Telemetry */}
      <div className="ff-card" style={{ marginBottom: '24px' }}>
        <div className="ff-card-title" style={{ marginBottom: '12px' }}>
          <GitCompare size={18} color="var(--color-success)" />
          Atomic Reports & Automated Comparisons
        </div>
        <p style={{ color: 'var(--text-secondary)', fontSize: '0.92rem', lineHeight: 1.7, marginBottom: '14px' }}>
          All executed runs produce immutable JSON report artifacts written atomically using temporary files and OS-level <code style={{ fontFamily: 'var(--font-mono)', background: 'var(--bg-surface-2)', padding: '2px 6px', borderRadius: '4px' }}>fsync</code> flushes prior to replacement. This guarantees reports are never partially written or corrupted during sudden process interruption.
        </p>
        <p style={{ color: 'var(--text-secondary)', fontSize: '0.92rem', lineHeight: 1.7 }}>
          The comparison engine evaluates candidate runs against baselines, calculating absolute and percentage deltas while categorizing changes directionally (Improved, Degraded, Neutral, Unchanged). Reports can also be exported directly into <strong>Prometheus text exposition format</strong> or <strong>OpenTelemetry OTLP JSON</strong> without third-party collector dependencies.
        </p>
      </div>

      {/* Section 4: Safety Safeguards & Limitations */}
      <div className="ff-card" style={{ marginBottom: '24px' }}>
        <div className="ff-card-title" style={{ marginBottom: '12px' }}>
          <ShieldCheck size={18} color="var(--color-warning)" />
          Safety Safeguards & Current Limitations
        </div>
        <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(260px, 1fr))', gap: '16px', marginBottom: '16px' }}>
          <div style={{ background: 'var(--bg-surface-2)', padding: '14px', borderRadius: 'var(--radius-md)' }}>
            <strong style={{ color: 'var(--text-primary)', display: 'block', marginBottom: '4px' }}>Loopback-Only by Default</strong>
            <span style={{ fontSize: '0.82rem', color: 'var(--text-secondary)' }}>
              Restricts targeting strictly to <code style={{ fontFamily: 'var(--font-mono)' }}>localhost</code>, <code style={{ fontFamily: 'var(--font-mono)' }}>127.0.0.1</code>, and <code style={{ fontFamily: 'var(--font-mono)' }}>::1</code> unless dual authorization flags are explicitly provided.
            </span>
          </div>

          <div style={{ background: 'var(--bg-surface-2)', padding: '14px', borderRadius: 'var(--radius-md)' }}>
            <strong style={{ color: 'var(--text-primary)', display: 'block', marginBottom: '4px' }}>Execution Deadline Clamping</strong>
            <span style={{ fontSize: '0.82rem', color: 'var(--text-secondary)' }}>
              Total run wall-clock duration is strictly bounded by <code style={{ fontFamily: 'var(--font-mono)' }}>total_deadline_seconds</code>, dynamically clamping effective per-request socket timeouts.
            </span>
          </div>

          <div style={{ background: 'var(--bg-surface-2)', padding: '14px', borderRadius: 'var(--radius-md)' }}>
            <strong style={{ color: 'var(--text-primary)', display: 'block', marginBottom: '4px' }}>Transport Safety & Privacy</strong>
            <span style={{ fontSize: '0.82rem', color: 'var(--text-secondary)' }}>
              Response payloads are truncated at 4KB, redirects are never silently followed to external third parties, and credentials are strictly omitted from persisted reports.
            </span>
          </div>
        </div>

        <p style={{ fontSize: '0.82rem', color: 'var(--text-muted)' }}>
          <strong>Current Scope Limitations:</strong> ForgeFit is designed as a focused, lightweight testing toolkit. Distributed multi-node scheduling, heavy asynchronous concurrency pools, and hosted relational database backends are intentionally excluded in favor of simple, deterministic, offline execution.
        </p>
      </div>

      {/* Creator & Project Information */}
      <div className="ff-card" style={{ background: 'linear-gradient(135deg, #101926 0%, #0c121c 100%)', border: '1px solid var(--border-accent)' }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: '16px', marginBottom: '14px' }}>
          <div className="brand-mark" style={{ width: '44px', height: '44px' }}>
            <Flame size={22} />
          </div>
          <div>
            <div style={{ fontWeight: 800, fontSize: '1.15rem' }}>ForgeFit Open Source Project</div>
            <div style={{ fontSize: '0.82rem', color: 'var(--text-secondary)' }}>
              Created by Shiv (<code style={{ fontFamily: 'var(--font-mono)', color: 'var(--accent-primary)' }}>shivkumar077</code>)
            </div>
          </div>
        </div>
        <p style={{ fontSize: '0.88rem', color: 'var(--text-secondary)', lineHeight: 1.6, marginBottom: '16px' }}>
          Developed with a focus on disciplined engineering, test-driven reliability, and verifiable safety guarantees under the MIT License.
        </p>
        <div style={{ display: 'flex', gap: '12px' }}>
          <a
            href="https://github.com/shivkumar077/ForgeFit"
            target="_blank"
            rel="noreferrer"
            className="btn btn-secondary btn-sm"
          >
            <Code2 size={14} />
            GitHub Repository
            <ExternalLink size={12} />
          </a>
        </div>
      </div>
    </div>
  );
};
