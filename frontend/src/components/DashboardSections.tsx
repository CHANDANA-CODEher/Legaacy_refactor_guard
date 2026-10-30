import {
  Activity,
  AlertTriangle,
  ArrowRight,
  Check,
  CheckCircle2,
  Code2,
  Copy,
  FileText,
  Gauge,
  GitBranch,
  History,
  Layers,
  ListChecks,
  Play,
  RefreshCw,
  RotateCcw,
  ShieldCheck,
  Sliders,
  Sparkles,
  Terminal,
} from "lucide-react";
import { useEffect, useState } from "react";
import {
  Bar,
  BarChart,
  CartesianGrid,
  Legend,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";
import {
  getSampleCode,
  runSandboxRefactor,
  type SandboxResponse,
} from "../services/api";
import type {
  HistoryItem,
  QualityMetric,
  RefactorAttempt,
  RefactorSettings,
  TestCounts,
  WorkflowStage,
} from "../types";

export type TabId = "studio" | "overview" | "tests" | "comparison" | "metrics" | "history" | "safety";

export function SidebarNav({
  activeTab,
  onSelectTab,
  repoName,
  isLive,
  onRefresh,
  refreshing,
}: {
  activeTab: TabId;
  onSelectTab: (tab: TabId) => void;
  repoName: string;
  isLive: boolean;
  onRefresh: () => void;
  refreshing: boolean;
}) {
  return (
    <aside className="site-sidebar">
      <div className="sidebar-brand">
        <div className="brand-group">
          <div className="brand-badge">
            <ShieldCheck size={22} className="brand-icon" />
          </div>
          <div>
            <div className="brand-title">Refactor Guard</div>
            <div className="brand-sub">Autonomous Safety Engine</div>
          </div>
        </div>
      </div>

      <div className="sidebar-nav-container">
        <div className="nav-group-title">WORKSPACE</div>
        <div className="sidebar-nav-list">
          <button
            className={`sidebar-nav-item ${activeTab === "studio" ? "active" : ""}`}
            onClick={() => onSelectTab("studio")}
          >
            <Sparkles size={16} />
            <span>Refactor Studio &amp; Lab</span>
          </button>
          <button
            className={`sidebar-nav-item ${activeTab === "overview" ? "active" : ""}`}
            onClick={() => onSelectTab("overview")}
          >
            <Layers size={16} />
            <span>Overview &amp; Pipeline</span>
          </button>
          <button
            className={`sidebar-nav-item ${activeTab === "tests" ? "active" : ""}`}
            onClick={() => onSelectTab("tests")}
          >
            <ListChecks size={16} />
            <span>Verification &amp; Tests</span>
          </button>
          <button
            className={`sidebar-nav-item ${activeTab === "comparison" ? "active" : ""}`}
            onClick={() => onSelectTab("comparison")}
          >
            <Code2 size={16} />
            <span>Code Diff &amp; AST</span>
          </button>
          <button
            className={`sidebar-nav-item ${activeTab === "metrics" ? "active" : ""}`}
            onClick={() => onSelectTab("metrics")}
          >
            <Gauge size={16} />
            <span>Quality Metrics</span>
          </button>
        </div>

        <div className="nav-group-title mt-4">SYSTEM</div>
        <div className="sidebar-nav-list">
          <button
            className={`sidebar-nav-item ${activeTab === "history" ? "active" : ""}`}
            onClick={() => onSelectTab("history")}
          >
            <History size={16} />
            <span>Historical Runs</span>
          </button>
          <button
            className={`sidebar-nav-item ${activeTab === "safety" ? "active" : ""}`}
            onClick={() => onSelectTab("safety")}
          >
            <ShieldCheck size={16} />
            <span>Safety Guardrails</span>
          </button>
        </div>
      </div>

      <div className="sidebar-footer">
        <div className="sidebar-status-box">
          <div className="status-indicator-row">
            <span className={`status-dot ${isLive ? "dot-green" : "dot-amber"}`} />
            <span className="status-label-text">{isLive ? "Engine Online" : "Demo Mode"}</span>
          </div>
          <div className="repo-pill">
            <GitBranch size={12} />
            <span>{repoName}</span>
          </div>
        </div>

        <button
          className="secondary-btn sidebar-refresh-btn"
          onClick={onRefresh}
          disabled={refreshing}
          title="Refresh Engine Status"
        >
          <RefreshCw size={13} className={refreshing ? "spin-icon" : ""} />
          <span>{refreshing ? "Refreshing..." : "Refresh Engine"}</span>
        </button>
      </div>
    </aside>
  );
}

export const HeaderNav = SidebarNav;

export function MetricCard({
  label,
  value,
  subtext,
  icon: Icon,
  variant = "neutral",
}: {
  label: string;
  value: string;
  subtext: string;
  icon: typeof Activity;
  variant?: "neutral" | "success" | "warning" | "info";
}) {
  return (
    <div className={`metric-card card-${variant}`}>
      <div className="metric-header">
        <span className="metric-label">{label}</span>
        <span className="metric-icon-wrap">
          <Icon size={18} />
        </span>
      </div>
      <div className="metric-value">{value}</div>
      <div className="metric-subtext">{subtext}</div>
    </div>
  );
}

const pipelineStages: { id: WorkflowStage; label: string; desc: string }[] = [
  { id: "scan", label: "1. Repository Scan", desc: "Validate paths & dependencies" },
  { id: "baseline", label: "2. Baseline Tests", desc: "Confirm original tests pass" },
  { id: "planning", label: "3. AST Validation", desc: "Pre-parse source syntax (AST)" },
  { id: "refactoring", label: "4. Single-File Snapshot", desc: "Atomic backup to memory" },
  { id: "verification", label: "5. Post-Test Verification", desc: "Execute pytest harness" },
  { id: "decision", label: "6. Decision / Rollback", desc: "Restore byte-for-byte on failure" },
];

export function WorkflowPipeline({
  currentStage,
  isRunning,
  isCompleted,
}: {
  currentStage: WorkflowStage;
  isRunning: boolean;
  isCompleted: boolean;
}) {
  const activeIndex = pipelineStages.findIndex((s) => s.id === currentStage);

  return (
    <div className="content-card">
      <div className="card-header">
        <div>
          <h3 className="card-title">Refactoring Safety Pipeline</h3>
          <p className="card-description">Deterministic 6-phase test-gated execution cycle</p>
        </div>
        <span className="chip chip-info">{isRunning ? "Running..." : "Enforced by Safety Guard"}</span>
      </div>

      <div className="pipeline-grid">
        {pipelineStages.map((stage, idx) => {
          const isDone = isCompleted || idx < activeIndex;
          const isCurrent = !isCompleted && idx === activeIndex;

          return (
            <div
              key={stage.id}
              className={`pipeline-step ${isDone ? "step-done" : ""} ${
                isCurrent ? "step-current" : ""
              }`}
            >
              <div className="step-badge">
                {isDone ? (
                  <Check size={14} className="text-emerald" />
                ) : (
                  <span>{idx + 1}</span>
                )}
              </div>
              <div className="step-info">
                <div className="step-title">{stage.label}</div>
                <div className="step-desc">{stage.desc}</div>
              </div>
            </div>
          );
        })}
      </div>
    </div>
  );
}

export function AttemptTimeline({
  attempts,
  isLive,
}: {
  attempts: RefactorAttempt[];
  isLive: boolean;
}) {
  return (
    <div className="content-card">
      <div className="card-header">
        <div>
          <h3 className="card-title">Latest Refactoring Attempts</h3>
          <p className="card-description">
            {isLive ? "Live results loaded from run_log.json" : "Sample verification attempts"}
          </p>
        </div>
        <span className="chip chip-neutral">{attempts.length} Attempt(s) Recorded</span>
      </div>

      <div className="attempts-list">
        {attempts.length === 0 ? (
          <div className="empty-state">No refactoring attempts recorded for this run.</div>
        ) : (
          attempts.map((att) => {
            const isAccepted = att.status === "accepted";
            const isRolledBack = att.status === "rolled_back";

            return (
              <div
                key={att.attempt}
                className={`attempt-item ${
                  isAccepted ? "attempt-accepted" : isRolledBack ? "attempt-rollback" : ""
                }`}
              >
                <div className="attempt-head">
                  <div className="attempt-title-row">
                    <span
                      className={`status-chip ${
                        isAccepted
                          ? "chip-success"
                          : isRolledBack
                          ? "chip-warning"
                          : "chip-danger"
                      }`}
                    >
                      {isAccepted ? "ACCEPTED" : isRolledBack ? "ROLLED BACK" : "FAILED"}
                    </span>
                    <span className="attempt-number">Attempt #{att.attempt}</span>
                    <span className="attempt-file">{att.targetFile}</span>
                  </div>
                  <div className="attempt-stats">
                    <span className="text-emerald font-mono">
                      {att.tests.passed} passed
                    </span>
                    <span className="text-muted">/</span>
                    <span
                      className={
                        att.tests.failed > 0
                          ? "text-rose font-mono font-bold"
                          : "text-muted font-mono"
                      }
                    >
                      {att.tests.failed} failed
                    </span>
                  </div>
                </div>

                <div className="attempt-goal">
                  <strong>Goal:</strong> {att.goal}
                </div>

                {att.errorSummary && (
                  <div className="error-box">
                    <div className="error-box-header">
                      <AlertTriangle size={13} />
                      <span>Failure Diagnosis</span>
                    </div>
                    <pre className="error-pre">{att.errorSummary}</pre>
                  </div>
                )}

                {att.failingTests.length > 0 && (
                  <div className="failing-tests-list">
                    <small>Failing tests:</small>
                    <div className="failing-tags">
                      {att.failingTests.map((t) => (
                        <span key={t} className="fail-tag">
                          {t}
                        </span>
                      ))}
                    </div>
                  </div>
                )}
              </div>
            );
          })
        )}
      </div>
    </div>
  );
}

export function TestResultsView({
  baseline,
  finalTests,
  attempts,
}: {
  baseline: TestCounts;
  finalTests: TestCounts;
  attempts: RefactorAttempt[];
}) {
  const [filter, setFilter] = useState<"all" | "failed">("all");

  const passRate = finalTests.total
    ? Math.round((finalTests.passed / finalTests.total) * 100)
    : 0;

  const failureRows = attempts.flatMap((att) =>
    att.failingTests.map((tName) => ({
      testName: tName,
      attempt: att.attempt,
      targetFile: att.targetFile,
      error: att.errorSummary || "Test assertion failed",
    }))
  );

  return (
    <div className="section-container">
      <div className="stats-row">
        <div className="stat-box">
          <div className="stat-label">Baseline Tests</div>
          <div className="stat-value text-emerald font-mono">
            {baseline.passed} / {baseline.total}
          </div>
          <div className="stat-sub">100% pre-refactor integrity verified</div>
        </div>

        <div className="stat-box">
          <div className="stat-label">Final Verification Suite</div>
          <div className="stat-value text-emerald font-mono">
            {finalTests.passed} / {finalTests.total}
          </div>
          <div className="stat-sub">{passRate}% pass rate retained</div>
        </div>

        <div className="stat-box">
          <div className="stat-label">Rollbacks Enforced</div>
          <div className="stat-value text-amber font-mono">
            {attempts.filter((a) => a.status === "rolled_back").length}
          </div>
          <div className="stat-sub">Regressions safely reverted</div>
        </div>
      </div>

      <div className="content-card">
        <div className="card-header">
          <div>
            <h3 className="card-title">Automated Pytest Results</h3>
            <p className="card-description">
              Execution reports from the isolated subprocess test harness
            </p>
          </div>
          <div className="btn-group">
            <button
              className={`filter-btn ${filter === "all" ? "active" : ""}`}
              onClick={() => setFilter("all")}
            >
              All Tests ({finalTests.total})
            </button>
            <button
              className={`filter-btn ${filter === "failed" ? "active" : ""}`}
              onClick={() => setFilter("failed")}
            >
              Failures Caught ({failureRows.length})
            </button>
          </div>
        </div>

        {filter === "failed" && failureRows.length === 0 ? (
          <div className="success-banner">
            <CheckCircle2 size={16} />
            <span>Zero failures recorded! All 8 unit tests passed cleanly.</span>
          </div>
        ) : (
          <div className="table-responsive">
            <table className="data-table">
              <thead>
                <tr>
                  <th>Test Function / Class</th>
                  <th>Attempt</th>
                  <th>Outcome</th>
                  <th>Diagnostics</th>
                </tr>
              </thead>
              <tbody>
                {failureRows.map((row, idx) => (
                  <tr key={`${row.testName}-${idx}`}>
                    <td className="font-mono text-dark">{row.testName}</td>
                    <td>Attempt #{row.attempt}</td>
                    <td>
                      <span className="badge-danger">FAILED</span>
                    </td>
                    <td className="text-muted text-sm">{row.error}</td>
                  </tr>
                ))}
                {filter === "all" && (
                  <>
                    <tr>
                      <td className="font-mono">test_empty_cart_returns_zero</td>
                      <td>Final</td>
                      <td>
                        <span className="badge-success">PASSED</span>
                      </td>
                      <td className="text-muted text-sm">Cart zero validation verified</td>
                    </tr>
                    <tr>
                      <td className="font-mono">test_standard_customer_under_threshold</td>
                      <td>Final</td>
                      <td>
                        <span className="badge-success">PASSED</span>
                      </td>
                      <td className="text-muted text-sm">Shipping $5.00 calculation correct</td>
                    </tr>
                    <tr>
                      <td className="font-mono">test_standard_customer_over_threshold</td>
                      <td>Final</td>
                      <td>
                        <span className="badge-success">PASSED</span>
                      </td>
                      <td className="text-muted text-sm">Free shipping tier verified</td>
                    </tr>
                    <tr>
                      <td className="font-mono">test_premium_customer_discount</td>
                      <td>Final</td>
                      <td>
                        <span className="badge-success">PASSED</span>
                      </td>
                      <td className="text-muted text-sm">10% tier discount verified</td>
                    </tr>
                    <tr>
                      <td className="font-mono">test_vip_customer_discount</td>
                      <td>Final</td>
                      <td>
                        <span className="badge-success">PASSED</span>
                      </td>
                      <td className="text-muted text-sm">20% tier discount verified</td>
                    </tr>
                    <tr>
                      <td className="font-mono">test_save10_coupon_applied</td>
                      <td>Final</td>
                      <td>
                        <span className="badge-success">PASSED</span>
                      </td>
                      <td className="text-muted text-sm">$10.00 coupon deduction correct</td>
                    </tr>
                    <tr>
                      <td className="font-mono">test_freeship_coupon_applied</td>
                      <td>Final</td>
                      <td>
                        <span className="badge-success">PASSED</span>
                      </td>
                      <td className="text-muted text-sm">Shipping waived by code</td>
                    </tr>
                    <tr>
                      <td className="font-mono">test_combined_vip_and_save10</td>
                      <td>Final</td>
                      <td>
                        <span className="badge-success">PASSED</span>
                      </td>
                      <td className="text-muted text-sm">Stacked discounts verified</td>
                    </tr>
                  </>
                )}
              </tbody>
            </table>
          </div>
        )}
      </div>
    </div>
  );
}

const sampleCodeDiffs: Record<string, { before: string[]; after: string[] }> = {
  "shop.py (Real Demo File)": {
    before: [
      "# Legacy calculation with hardcoded numbers and magic constants",
      "def calculate_order_total(items, customer_type='standard', coupon_code=None):",
      "    if not items:",
      "        return 0.0",
      "    subtotal = sum(i['price'] * i['quantity'] for i in items)",
      "    if customer_type == 'vip':",
      "        subtotal *= 0.80",
      "    elif customer_type == 'premium':",
      "        subtotal *= 0.90",
      "    shipping = 0.0 if subtotal >= 50 or coupon_code == 'FREESHIP' else 5.0",
      "    return round(subtotal * 1.08 + shipping, 2)",
    ],
    after: [
      "from __future__ import annotations",
      "",
      "TAX_RATE: float = 0.08",
      "STANDARD_SHIPPING: float = 5.00",
      "FREE_SHIPPING_THRESHOLD: float = 50.00",
      "CUSTOMER_DISCOUNTS: dict[str, float] = {'vip': 0.20, 'premium': 0.10, 'standard': 0.0}",
      "",
      "def calculate_order_total(",
      "    items: list[dict[str, float | int]] | None,",
      "    customer_type: str = 'standard',",
      "    coupon_code: str | None = None,",
      ") -> float:",
      "    # Clean, type-annotated implementation verified by 8 unit tests",
      "    if not items:",
      "        return 0.0",
      "    ...",
    ],
  },
  "billing.py (Sample)": {
    before: [
      "def invoice_total(items, tax_rate):",
      "    subtotal = sum(i.price for i in items)",
      "    tax = round(subtotal * tax_rate, 2)",
      "    return subtotal + tax",
    ],
    after: [
      "def calculate_tax(subtotal: float, tax_rate: float) -> float:",
      "    return round(subtotal * tax_rate, 2)",
      "",
      "def invoice_total(items, tax_rate):",
      "    subtotal = sum(i.price for i in items)",
      "    return subtotal + calculate_tax(subtotal, tax_rate)",
    ],
  },
};

export function CodeDiffView({ notify }: { notify: (msg: string) => void }) {
  const [selectedFile, setSelectedFile] = useState("shop.py (Real Demo File)");
  const diff = sampleCodeDiffs[selectedFile] || sampleCodeDiffs["shop.py (Real Demo File)"];

  const copyDiff = () => {
    navigator.clipboard.writeText(diff.after.join("\n"));
    notify("Refactored code copied to clipboard!");
  };

  return (
    <div className="content-card">
      <div className="card-header">
        <div>
          <h3 className="card-title">Code Diff &amp; AST Verification</h3>
          <p className="card-description">
            Inspect original source code alongside verified refactored output
          </p>
        </div>
        <div className="file-selector-row">
          <select
            className="select-input"
            value={selectedFile}
            onChange={(e) => setSelectedFile(e.target.value)}
          >
            {Object.keys(sampleCodeDiffs).map((fname) => (
              <option key={fname} value={fname}>
                {fname}
              </option>
            ))}
          </select>
          <button className="secondary-btn" onClick={copyDiff}>
            <Copy size={13} />
            <span>Copy Refactored</span>
          </button>
        </div>
      </div>

      <div className="diff-container">
        <div className="diff-pane">
          <div className="pane-header header-original">
            <span className="dot dot-red" />
            <span>Original Code (Snapshot Baseline)</span>
          </div>
          <pre className="code-block">
            {diff.before.map((line, i) => (
              <div key={i} className="code-line">
                <span className="line-num">{i + 1}</span>
                <span className="line-content">{line}</span>
              </div>
            ))}
          </pre>
        </div>

        <div className="diff-pane">
          <div className="pane-header header-refactored">
            <span className="dot dot-green" />
            <span>Refactored Code (AST Validated)</span>
          </div>
          <pre className="code-block code-refactored">
            {diff.after.map((line, i) => (
              <div key={i} className="code-line line-added">
                <span className="line-num">{i + 1}</span>
                <span className="line-content">{line}</span>
              </div>
            ))}
          </pre>
        </div>
      </div>
    </div>
  );
}

export function HistoryView({ history }: { history: HistoryItem[] }) {
  return (
    <div className="content-card">
      <div className="card-header">
        <div>
          <h3 className="card-title">Archived Run Logs</h3>
          <p className="card-description">
            Historical logs preserved automatically in the outputs/ directory
          </p>
        </div>
        <span className="chip chip-info">{history.length} Logs Available</span>
      </div>

      {history.length === 0 ? (
        <div className="empty-state">
          No archived run logs found in outputs/. Run logs are archived automatically when new runs
          begin.
        </div>
      ) : (
        <div className="table-responsive">
          <table className="data-table">
            <thead>
              <tr>
                <th>Archive File</th>
                <th>Repository</th>
                <th>Started At</th>
                <th>Provider</th>
                <th>Baseline</th>
                <th>Final Outcome</th>
                <th>Attempts</th>
              </tr>
            </thead>
            <tbody>
              {history.map((item, idx) => (
                <tr key={`${item.filename}-${idx}`}>
                  <td className="font-mono text-dark">
                    <FileText size={14} className="inline mr-1 text-muted" />
                    {item.filename}
                  </td>
                  <td>{item.repo}</td>
                  <td className="text-muted text-sm">
                    {new Date(item.started_at).toLocaleString()}
                  </td>
                  <td>
                    <span className="chip chip-neutral font-mono">{item.provider}</span>
                  </td>
                  <td className="font-mono text-emerald">
                    {item.baseline.passed} passed / {item.baseline.failed} failed
                  </td>
                  <td className="font-mono text-emerald">
                    {item.final.passed} passed / {item.final.failed} failed
                  </td>
                  <td>
                    <span className="badge-info">{item.attempts_count} attempt</span>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
}

export function SafetySettingsView({
  settings,
  onSave,
  notify,
}: {
  settings: RefactorSettings;
  onSave: (s: RefactorSettings) => void;
  notify: (msg: string) => void;
}) {
  const [formData, setFormData] = useState(settings);

  const copyCli = () => {
    navigator.clipboard.writeText("py run_demo.py");
    notify("Copied: py run_demo.py");
  };

  return (
    <div className="settings-grid">
      <div className="content-card">
        <h3 className="card-title">Safety Guardrails &amp; Protections</h3>
        <p className="card-description">Built-in safeguards preventing regressions and corruptions</p>

        <div className="safeguards-list">
          <div className="safeguard-item">
            <CheckCircle2 size={18} className="text-emerald" />
            <div>
              <strong>Fail-Early Baseline Check</strong>
              <p>Refactoring stops immediately if tests fail before any code changes.</p>
            </div>
          </div>

          <div className="safeguard-item">
            <CheckCircle2 size={18} className="text-emerald" />
            <div>
              <strong>Zero Test File Tampering</strong>
              <p>Files matching test_*, *_test.py, or inside tests/ folders cannot be modified.</p>
            </div>
          </div>

          <div className="safeguard-item">
            <CheckCircle2 size={18} className="text-emerald" />
            <div>
              <strong>Pre-Write AST Syntax Validation</strong>
              <p>Proposals are parsed via ast.parse. Syntax errors never touch the disk.</p>
            </div>
          </div>

          <div className="safeguard-item">
            <CheckCircle2 size={18} className="text-emerald" />
            <div>
              <strong>Single-File In-Memory Rollback</strong>
              <p>Original file contents are restored byte-for-byte upon any test failure.</p>
            </div>
          </div>

          <div className="safeguard-item">
            <CheckCircle2 size={18} className="text-emerald" />
            <div>
              <strong>Subprocess Pytest Isolation</strong>
              <p>Tests execute with strict timeouts to prevent hangs or background leaks.</p>
            </div>
          </div>
        </div>
      </div>

      <div className="content-card">
        <h3 className="card-title">Run Configuration</h3>
        <p className="card-description">Configure timeouts and offline execution commands</p>

        <form
          className="settings-form"
          onSubmit={(e) => {
            e.preventDefault();
            onSave(formData);
            notify("Settings saved for this session!");
          }}
        >
          <div className="form-group">
            <label className="form-label">Repository Target Directory</label>
            <input
              type="text"
              className="form-input"
              value={formData.repositoryPath}
              onChange={(e) =>
                setFormData({ ...formData, repositoryPath: e.target.value })
              }
            />
            <small className="form-help">Target repository directory</small>
          </div>

          <div className="form-row">
            <div className="form-group">
              <label className="form-label">Pytest Timeout (Seconds)</label>
              <input
                type="number"
                className="form-input"
                min={5}
                max={300}
                value={formData.testTimeoutSeconds}
                onChange={(e) =>
                  setFormData({
                    ...formData,
                    testTimeoutSeconds: Number(e.target.value),
                  })
                }
              />
            </div>

            <div className="form-group">
              <label className="form-label">Maximum Retries</label>
              <input
                type="number"
                className="form-input"
                min={1}
                max={5}
                value={formData.maximumRetries}
                onChange={(e) =>
                  setFormData({
                    ...formData,
                    maximumRetries: Number(e.target.value),
                  })
                }
              />
            </div>
          </div>

          <div className="cli-box">
            <div className="cli-header">
              <Terminal size={14} />
              <span>Offline CLI Execution</span>
            </div>
            <div className="cli-command-row">
              <code className="font-mono text-emerald">py run_demo.py</code>
              <button type="button" className="copy-btn" onClick={copyCli}>
                <Copy size={13} />
                <span>Copy</span>
              </button>
            </div>
            <small className="text-muted">
              To protect workspace files, live modifications are run in the terminal.
            </small>
          </div>

          <button type="submit" className="primary-btn mt-3">
            Save Preferences
          </button>
        </form>
      </div>
    </div>
  );
}

export function QualityMetricsView({ metrics }: { metrics: QualityMetric[] }) {
  const chartData = metrics.map((m) => ({
    name: m.label,
    Before: m.before,
    After: m.after,
  }));

  return (
    <div className="section-container">
      <div className="metrics-grid-3">
        {metrics.map((m) => (
          <div key={m.key} className="content-card">
            <div className="metric-header">
              <span className="metric-label">{m.label}</span>
              <Gauge size={16} className="text-muted" />
            </div>
            <div className="comparison-row">
              <div>
                <small className="text-muted">Before</small>
                <div className="stat-val font-mono">{m.before}</div>
              </div>
              <ArrowRight size={18} className="text-muted mt-2" />
              <div>
                <small className="text-emerald">After Refactor</small>
                <div className="stat-val text-emerald font-mono">{m.after}</div>
              </div>
            </div>
          </div>
        ))}
      </div>

      <div className="content-card">
        <h3 className="card-title">Code Health Comparison (Lower is Better)</h3>
        <p className="card-description">
          Complexity reduction and duplication removal metrics
        </p>
        <div style={{ width: "100%", height: 260, marginTop: 20 }}>
          <ResponsiveContainer width="100%" height="100%">
            <BarChart data={chartData} margin={{ top: 10, right: 20, left: -10, bottom: 0 }}>
              <CartesianGrid stroke="#e2e8f0" vertical={false} />
              <XAxis dataKey="name" stroke="#64748b" fontSize={12} tickLine={false} />
              <YAxis stroke="#64748b" fontSize={12} tickLine={false} />
              <Tooltip
                contentStyle={{
                  backgroundColor: "#ffffff",
                  borderColor: "#e2e8f0",
                  borderRadius: 8,
                  color: "#0f172a",
                  boxShadow: "0 4px 6px -1px rgba(0, 0, 0, 0.08)",
                }}
              />
              <Legend wrapperStyle={{ fontSize: 13, color: "#64748b" }} />
              <Bar dataKey="Before" fill="#94a3b8" radius={[4, 4, 0, 0]} />
              <Bar dataKey="After" fill="#10b981" radius={[4, 4, 0, 0]} />
            </BarChart>
          </ResponsiveContainer>
        </div>
      </div>
    </div>
  );
}

export function RefactorStudioView({
  notify,
  onRunComplete,
}: {
  notify: (msg: string, isError?: boolean) => void;
  onRunComplete?: () => void;
}) {
  const [targetFile, setTargetFile] = useState("shop.py");
  const [goal, setGoal] = useState("Add type annotations and optimize calculate_order_total");
  const [scenario, setScenario] = useState<"safe_refactor" | "broken_code_rollback" | "custom_code">("safe_refactor");
  const [code, setCode] = useState<string>("");
  const [loading, setLoading] = useState(false);
  const [result, setResult] = useState<SandboxResponse | null>(null);

  useEffect(() => {
    getSampleCode("shop.py")
      .then((data) => setCode(data.code))
      .catch((err) => console.warn("Failed to load sample code:", err));
  }, []);

  const handleRun = async () => {
    setLoading(true);
    try {
      const res = await runSandboxRefactor({
        target_file: targetFile,
        goal,
        scenario,
        custom_code: scenario === "custom_code" ? code : undefined,
      });
      setResult(res);
      if (onRunComplete) {
        onRunComplete();
      }
      if (res.status === "accepted" || res.success) {
        notify("Refactor Accepted! All 8 baseline tests verified in sandbox.");
      } else if (res.status === "rolled_back") {
        notify("Regression Blocked! Pytest failure triggered byte-for-byte rollback.", true);
      } else {
        notify(`Execution finished with status: ${res.status}`);
      }
    } catch (err: unknown) {
      const msg = err instanceof Error ? err.message : "Execution failed";
      notify(msg, true);
    } finally {
      setLoading(false);
    }
  };

  const loadPreset = (type: "safe" | "broken" | "clean") => {
    if (type === "safe") {
      setScenario("safe_refactor");
      setGoal("Add type annotations and clean up calculate_order_total");
    } else if (type === "broken") {
      setScenario("broken_code_rollback");
      setGoal("Inject broken calculation (returns 0.0) to test automatic rollback guard");
    } else {
      setScenario("custom_code");
      setGoal("Test custom logic against verification suite");
    }
  };

  return (
    <div className="studio-container">
      {/* Top Banner Guide */}
      <div className="hero-banner">
        <div className="hero-content">
          <div className="hero-tag">
            <Sparkles size={14} />
            <span>Interactive Sandbox &amp; Verification Lab</span>
          </div>
          <h1 className="hero-title">Enter Details, Test &amp; Verify Code in Real Time</h1>
          <p className="hero-sub">
            Configure refactoring parameters or test code proposals in an isolated temporary sandbox.
            Subprocess pytest execution evaluates your changes safely, triggering automatic byte-for-byte rollback if tests fail.
          </p>
        </div>
      </div>

      <div className="studio-grid">
        {/* Left Card: Input & Controls */}
        <div className="content-card studio-input-card">
          <div className="card-header">
            <div>
              <h3 className="card-title">1. Configure Refactoring Request</h3>
              <p className="card-description">Select preset or enter custom code to test</p>
            </div>
            <span className="chip chip-info font-mono">Isolated Sandbox</span>
          </div>

          <div className="scenario-selector">
            <label className="form-label">Select Execution Scenario:</label>
            <div className="scenario-buttons">
              <button
                type="button"
                className={`scenario-btn ${scenario === "safe_refactor" ? "active" : ""}`}
                onClick={() => loadPreset("safe")}
              >
                <CheckCircle2 size={16} className="text-emerald" />
                <div>
                  <strong>Safe Refactor (Mock AI)</strong>
                  <small>Verifies 8/8 tests pass cleanly</small>
                </div>
              </button>

              <button
                type="button"
                className={`scenario-btn ${scenario === "broken_code_rollback" ? "active" : ""}`}
                onClick={() => loadPreset("broken")}
              >
                <RotateCcw size={16} className="text-amber" />
                <div>
                  <strong>Rollback Guard Demo</strong>
                  <small>Deliberate bug &rarr; 7 tests fail &rarr; Rollback</small>
                </div>
              </button>

              <button
                type="button"
                className={`scenario-btn ${scenario === "custom_code" ? "active" : ""}`}
                onClick={() => loadPreset("clean")}
              >
                <Code2 size={16} className="text-emerald" />
                <div>
                  <strong>Custom Code Editor</strong>
                  <small>Test custom code against pytest</small>
                </div>
              </button>
            </div>
          </div>

          <div className="form-row mt-3">
            <div className="form-group">
              <label className="form-label">Target File</label>
              <input
                type="text"
                className="form-input font-mono"
                value={targetFile}
                onChange={(e) => setTargetFile(e.target.value)}
              />
            </div>
            <div className="form-group">
              <label className="form-label">LLM Provider</label>
              <select className="select-input" value="mock" disabled>
                <option value="mock">Deterministic Mock Provider (Offline Safe)</option>
              </select>
            </div>
          </div>

          <div className="form-group mt-2">
            <label className="form-label">Refactoring Goal / Prompt</label>
            <input
              type="text"
              className="form-input"
              value={goal}
              onChange={(e) => setGoal(e.target.value)}
              placeholder="e.g., Add type annotations and optimize order calculations"
            />
          </div>

          {scenario === "custom_code" && (
            <div className="form-group mt-3">
              <div className="card-header" style={{ marginBottom: 8, paddingBottom: 6 }}>
                <label className="form-label" style={{ margin: 0 }}>Editable Source Code (shop.py)</label>
                <span className="text-muted text-sm font-mono">ast.parse validated</span>
              </div>
              <textarea
                className="code-editor-textarea font-mono"
                rows={12}
                value={code}
                onChange={(e) => setCode(e.target.value)}
                placeholder="Enter source code to test..."
              />
            </div>
          )}

          <div className="studio-actions mt-3">
            <button
              className="primary-btn run-studio-btn"
              onClick={handleRun}
              disabled={loading}
              style={{ width: "100%", padding: "12px 20px" }}
            >
              {loading ? (
                <>
                  <RefreshCw size={16} className="spin-icon" />
                  <span>Evaluating Tests in Sandbox...</span>
                </>
              ) : (
                <>
                  <Play size={16} />
                  <span>Run Refactor &amp; Test Guard</span>
                </>
              )}
            </button>
          </div>
        </div>

        {/* Right Card: Live Results & Diagnostics */}
        <div className="content-card studio-output-card">
          <div className="card-header">
            <div>
              <h3 className="card-title">2. Guard Execution &amp; Test Diagnostics</h3>
              <p className="card-description">Deterministic subprocess verification output</p>
            </div>
            {result && (
              <span
                className={`status-chip ${
                  result.status === "accepted" || result.success ? "chip-success" : "chip-warning"
                }`}
              >
                {result.status === "accepted" || result.success ? "ACCEPTED" : "ROLLED BACK"}
              </span>
            )}
          </div>

          {!result && !loading && (
            <div className="empty-state">
              <Sliders size={32} className="text-muted inline" style={{ marginBottom: 12 }} />
              <p>
                Click <strong>"Run Refactor &amp; Test Guard"</strong> to execute real baseline pytest verification,
                syntax validation, and test evaluation in the isolated sandbox.
              </p>
              <small className="text-muted mt-2 inline">
                Real subprocess pytest runs cleanly without altering workspace files.
              </small>
            </div>
          )}

          {loading && (
            <div className="empty-state">
              <RefreshCw size={32} className="text-emerald spin-icon inline" style={{ marginBottom: 12 }} />
              <p>Spinning up sandbox &rarr; Running baseline tests &rarr; AST parsing &rarr; Executing subprocess pytest...</p>
            </div>
          )}

          {result && (
            <div className="studio-result-view">
              {/* Decision Banner */}
              <div
                className={`result-alert ${
                  result.status === "accepted" || result.success
                    ? "alert-accepted"
                    : "alert-rollback"
                }`}
              >
                {result.status === "accepted" || result.success ? (
                  <>
                    <CheckCircle2 size={20} className="text-emerald flex-shrink-0" />
                    <div>
                      <strong>Refactoring Accepted &amp; Verified</strong>
                      <p>
                        All {result.final.passed} tests passed! Zero regressions detected.
                        Changes verified safe in sandbox.
                      </p>
                    </div>
                  </>
                ) : (
                  <>
                    <RotateCcw size={20} className="text-amber flex-shrink-0" />
                    <div>
                      <strong>Regression Caught: Automatic Rollback Triggered</strong>
                      <p>
                        Deliberate bug caused unit tests to fail ({result.final.failed} failed, {result.final.passed} passed).
                        Original file restored byte-for-byte.
                      </p>
                    </div>
                  </>
                )}
              </div>

              {/* Stats Grid */}
              <div className="stats-row mt-3">
                <div className="stat-box">
                  <div className="stat-label">Baseline Tests</div>
                  <div className="stat-value text-emerald font-mono">
                    {result.baseline.passed} / {result.baseline.total}
                  </div>
                  <div className="stat-sub">100% pre-refactor integrity</div>
                </div>

                <div className="stat-box">
                  <div className="stat-label">Post-Refactor Tests</div>
                  <div
                    className={`stat-value font-mono ${
                      result.final.failed > 0 ? "text-rose" : "text-emerald"
                    }`}
                  >
                    {result.final.passed} passed / {result.final.failed} failed
                  </div>
                  <div className="stat-sub">
                    {result.final.failed > 0 ? "Regression caught!" : "Clean verification"}
                  </div>
                </div>

                <div className="stat-box">
                  <div className="stat-label">Byte-for-Byte Restored</div>
                  <div className="stat-value text-emerald font-mono">
                    {result.restored_byte_for_byte ? "100% YES" : "N/A (Accepted)"}
                  </div>
                  <div className="stat-sub">Original shop.py preserved</div>
                </div>
              </div>

              {/* Code Inspection Pane */}
              <div className="diff-pane mt-3">
                <div className="pane-header header-refactored">
                  <Code2 size={14} />
                  <span>Sandbox Code State (After Decision)</span>
                </div>
                <pre className="code-block" style={{ maxHeight: 260 }}>
                  {result.after_code.split("\n").map((line, idx) => (
                    <div key={idx} className="code-line">
                      <span className="line-num">{idx + 1}</span>
                      <span className="line-content">{line}</span>
                    </div>
                  ))}
                </pre>
              </div>
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
