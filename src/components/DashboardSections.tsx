import {
  Activity, AlertTriangle, ArrowDownRight, BarChart3, Check, ChevronDown, ChevronUp,
  CircleX, Code2, FileCode2, FlaskConical, Gauge, GitBranch, ListChecks, LockKeyhole,
  RotateCcw, ShieldCheck, TestTube2,
} from "lucide-react";
import { useEffect, useRef, useState } from "react";
import {
  Bar, BarChart, CartesianGrid, Legend, ResponsiveContainer, Tooltip, XAxis, YAxis,
} from "recharts";
import type { QualityMetric, RefactorAttempt, RefactorSettings, TestCounts, WorkflowStage } from "../types";

export type NavId = "overview" | "repository" | "runs" | "tests" | "comparison" | "metrics" | "activity" | "settings";

const navigation: { id: NavId; label: string; icon: typeof Activity }[] = [
  { id: "overview", label: "Overview", icon: BarChart3 },
  { id: "repository", label: "Repository", icon: GitBranch },
  { id: "runs", label: "Refactor Runs", icon: Activity },
  { id: "tests", label: "Test Results", icon: ListChecks },
  { id: "comparison", label: "Code Comparison", icon: Code2 },
  { id: "metrics", label: "Quality Metrics", icon: Gauge },
  { id: "activity", label: "Activity Logs", icon: TestTube2 },
  { id: "settings", label: "Settings", icon: ShieldCheck },
];

export function Sidebar({ active, collapsed, mobileOpen, onNavigate, onToggle, onClose }: {
  active: NavId; collapsed: boolean; mobileOpen: boolean; onNavigate: (id: NavId) => void; onToggle: () => void; onClose: () => void;
}) {
  return <>
    {mobileOpen && <button className="mobile-scrim" aria-label="Close menu" onClick={onClose} />}
    <aside className={`sidebar ${collapsed ? "collapsed" : ""} ${mobileOpen ? "mobile-open" : ""}`}>
      <div className="brand">
        <div className="brand-logo"><ShieldCheck size={21} /><Code2 size={11} className="brand-code" /></div>
        {!collapsed && <div className="brand-name"><strong>Legacy Refactor</strong><small>GUARD</small></div>}
        <button className="sidebar-toggle" onClick={onToggle} aria-label="Collapse sidebar"><ChevronDown size={16} /></button>
        <button className="mobile-close" onClick={onClose} aria-label="Close navigation">×</button>
      </div>
      {!collapsed && <div className="workspace"><span className="workspace-logo">L</span><span><b>Lighthouse Labs</b><small>Workspace</small></span><ChevronDown size={14} /></div>}
      {!collapsed && <p className="nav-label">WORKSPACE</p>}
      <nav aria-label="Main navigation">
        {navigation.map(({ id, label, icon: Icon }) => <button key={id} title={collapsed ? label : undefined} aria-current={active === id ? "page" : undefined} className={`nav-link ${active === id ? "active" : ""}`} onClick={() => { onNavigate(id); onClose(); }}>
          <Icon size={17} /><span>{label}</span>{id === "runs" && !collapsed && <i className="nav-count">2</i>}
        </button>)}
      </nav>
      {!collapsed && <div className="sidebar-callout"><span className="callout-shield"><ShieldCheck size={16} /></span><b>Protected by design</b><p>Every accepted change is verified against your test suite.</p><button onClick={() => onNavigate("settings")}>View safety settings <span>↗</span></button></div>}
      <div className="profile"><span className="avatar">JD</span>{!collapsed && <span><b>Jamie Davis</b><small>Developer</small></span>}{!collapsed && <ChevronDown size={14} />}</div>
    </aside>
  </>;
}

export function MetricCard({ label, value, note, icon: Icon, tone, trend, isDemo = true }: {
  label: string; value: string; note: string; icon: typeof Activity; tone: string; trend?: string; isDemo?: boolean;
}) {
  return <article className="metric-card"><div className="metric-top"><span className={`metric-icon ${tone}`}><Icon size={17} /></span><span className="demo-label">{isDemo ? "DEMO DATA" : "LIVE DATA"}</span></div>
    <p>{label}</p><strong className="metric-value">{value}</strong><div className="metric-note">{trend && <b><ArrowDownRight size={13} />{trend}</b>}{note}</div>
  </article>;
}

const stages: { id: WorkflowStage; title: string; detail: string; icon: typeof Activity }[] = [
  { id: "scan", title: "Repository scan", detail: "Map files & dependencies", icon: GitBranch },
  { id: "baseline", title: "Baseline tests", detail: "Confirm current behavior", icon: FlaskConical },
  { id: "planning", title: "Planning", detail: "Select a safe target", icon: ListChecks },
  { id: "refactoring", title: "Refactoring", detail: "Generate an improvement", icon: Code2 },
  { id: "verification", title: "Test verification", detail: "Run the full test suite", icon: ShieldCheck },
  { id: "decision", title: "Accept or roll back", detail: "Keep verified changes", icon: RotateCcw },
];

export function WorkflowStepper({ current, running, completed }: { current: WorkflowStage; running: boolean; completed: boolean }) {
  const active = stages.findIndex((stage) => stage.id === current);
  return <section className="panel workflow" id="workflow">
    <div className="section-head"><div><small>AUTONOMOUS PIPELINE</small><h2>Agent workflow</h2></div><span className={`workflow-state ${running ? "busy" : completed ? "ready" : ""}`}><i />{running ? "Workflow in progress" : completed ? "Demo run complete" : "Ready to run"}</span></div>
    <div className="steps">{stages.map(({ id, title, detail, icon: Icon }, index) => {
      const done = completed || index < active;
      const live = !completed && index === active;
      return <div key={id} className={`step ${done ? "done" : ""} ${live ? "current" : ""}`}>
        <div className="step-track"><span className="step-icon">{done ? <Check size={16} /> : <Icon size={16} />}</span>{index < stages.length - 1 && <i className={done ? "connected" : ""} />}</div>
        <b>{title}</b><small>{detail}</small>{live && <em>{running ? "IN PROGRESS" : "CURRENT"}</em>}
      </div>;
    })}</div>
    <div className="workflow-foot"><ShieldCheck size={14} /> Changes are accepted only after the configured verification suite passes.</div>
  </section>;
}

export function AttemptTimeline({ attempts, isDemo = true }: { attempts: RefactorAttempt[]; isDemo?: boolean }) {
  const [expanded, setExpanded] = useState<number | null>(2);
  return <section className="panel" id="runs">
    <div className="section-head"><div><small>RUN HISTORY</small><h2>Refactoring attempts</h2></div><span className="demo-label">{isDemo ? "ILLUSTRATIVE DEMO DATA" : "BACKEND DATA"}</span></div>
    <div className="attempt-list">{attempts.length === 0 ? <p className="empty-state">No attempts have been reported for this run.</p> : attempts.map((attempt) => {
      const accepted = attempt.status === "accepted";
      const open = expanded === attempt.attempt;
      return <article key={attempt.attempt} className={`attempt ${accepted ? "accepted" : "rolled-back"}`}>
        <button className="attempt-summary" aria-expanded={open} onClick={() => setExpanded(open ? null : attempt.attempt)}>
          <span className={`attempt-mark ${accepted ? "green" : "red"}`}>{accepted ? <Check size={16} /> : <RotateCcw size={15} />}</span>
          <span className="attempt-copy"><b>Attempt {attempt.attempt}</b><small>{attempt.targetFile} · {attempt.goal}</small></span>
          <span className={`status-pill ${accepted ? "green-pill" : "red-pill"}`}>{accepted ? "ACCEPTED" : "ROLLED BACK"}</span>
          <span className="attempt-count">{attempt.tests.passed}/{attempt.tests.total} passed</span>{open ? <ChevronUp size={16} /> : <ChevronDown size={16} />}
        </button>
        {open && <div className="attempt-details">
          <div><small>Target file</small><b>{attempt.targetFile}</b></div><div><small>Tests passed</small><b className="green-text">{attempt.tests.passed}</b></div>
          <div><small>Tests failed</small><b className={attempt.tests.failed ? "red-text" : "green-text"}>{attempt.tests.failed}</b></div><div><small>Attempt status</small><b>{accepted ? "Accepted" : "Rolled back"}</b></div>
          <div className={`attempt-reason ${accepted ? "pass-reason" : ""}`}><span>{accepted ? <Check size={14} /> : <CircleX size={14} />}</span><div><b>{accepted ? "All checks passed" : "Error summary"}</b><p>{attempt.errorSummary ?? "Changes retained after the full verification suite passed."}</p>{attempt.failingTests.length > 0 && <small>Failing tests: {attempt.failingTests.join(", ")}</small>}</div></div>
        </div>}
      </article>;
    })}</div>
  </section>;
}

export function TestResults({ baseline, attempts, finalTests, isDemo = true }: { baseline: TestCounts; attempts: RefactorAttempt[]; finalTests: TestCounts; isDemo?: boolean }) {
  const success = finalTests.total ? Math.round(finalTests.passed / finalTests.total * 100) : 0;
  const rows = attempts.flatMap((attempt) => attempt.failingTests.map((name) => ({
    name,
    attempt: `Attempt ${attempt.attempt}`,
    error: attempt.errorSummary ?? "Failure reported by the backend.",
  })));
  return <section className="panel" id="tests">
    <div className="section-head"><div><small>VERIFICATION</small><h2>Test results</h2></div><span className="demo-label">{isDemo ? "DEMO DATA" : "BACKEND DATA"}</span></div>
    <div className="test-summary">
      <div className="test-score"><span><TestTube2 size={18} /></span><div><b>{finalTests.passed}<small>/{finalTests.total}</small></b><small>Final tests passed</small></div></div>
      <div><small>Baseline</small><b>{baseline.passed}/{baseline.total}</b><em>All clear</em></div>
      <div><small>Attempts</small><b>{attempts.length}</b><em>{attempts.reduce((sum, item) => sum + item.tests.failed, 0)} failures caught</em></div>
      <div><small>Success rate</small><b>{success}%</b><em>Final verification</em></div>
    </div>
    <div className="progress-info"><span>Final suite pass rate</span><b>{success}%</b></div><div className="progress-track"><span style={{ width: `${success}%` }} /></div>
    <div className="table-scroll"><table><thead><tr><th>Test name</th><th>Attempt</th><th>Result</th><th>Error summary</th></tr></thead><tbody>
      {rows.length ? rows.map((row, i) => <tr key={`${row.name}-${i}`}><td className="test-name">{row.name}</td><td>{row.attempt}</td><td><span className="result-fail"><CircleX size={12} />Failed</span></td><td className="error-text">{row.error}</td></tr>) : <tr><td className="empty-cell" colSpan={4}>No failing test names were reported for the available attempts.</td></tr>}
    </tbody></table></div><p className="data-note">{isDemo ? "Example test names and results are illustrative. No test suite was executed by this frontend." : "Only failing test names supplied by the backend are listed; aggregate passed counts are shown above."}</p>
  </section>;
}

const codeSamples: Record<string, { before: string[]; after: string[] }> = {
  "billing.py": {
    before: ["def invoice_total(items, tax_rate):", "    subtotal = sum(i.price for i in items)", "    tax = round(subtotal * tax_rate, 2)", "    return subtotal + tax", "", "def quote_total(items, tax_rate):", "    subtotal = sum(i.price for i in items)", "    tax = round(subtotal * tax_rate, 2)", "    return subtotal + tax"],
    after: ["def calculate_tax(subtotal, tax_rate):", "    return round(subtotal * tax_rate, 2)", "", "def invoice_total(items, tax_rate):", "    subtotal = sum(i.price for i in items)", "    return subtotal + calculate_tax(subtotal, tax_rate)", "", "def quote_total(items, tax_rate):", "    subtotal = sum(i.price for i in items)", "    return subtotal + calculate_tax(subtotal, tax_rate)"],
  },
  "inventory.py": { before: ["def available(stock, reserved):", "    return stock - reserved", "", "def sellable(stock, reserved):", "    return stock - reserved"], after: ["def available(stock, reserved):", "    return stock - reserved", "", "def sellable(stock, reserved):", "    return available(stock, reserved)"] },
  "orders.py": { before: ["def normalize_order(order):", "    order.status = order.status.lower()", "    order.email = order.email.strip()", "    return order"], after: ["def normalize_order(order):", "    order.status = order.status.casefold()", "    order.email = order.email.strip()", "    return order"] },
  "reports.py": { before: ["def report_rows(records):", "    rows = []", "    for record in records:", "        rows.append(format_row(record))", "    return rows"], after: ["def report_rows(records):", "    return [format_row(record) for record in records]"] },
  "utils.py": { before: ["def is_blank(value):", "    return value is None or value == \"\"", "", "def has_value(value):", "    return value is not None and value != \"\""], after: ["def is_blank(value):", "    return not value", "", "def has_value(value):", "    return bool(value)"] },
};

function syntax(line: string) {
  const safe = line.replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;");
  return safe.replace(/\b(def|return|for|in|None|or|and|not|is)\b/g, '<i class="keyword">$1</i>')
    .replace(/\b(round|sum|bool)\b/g, '<i class="function">$1</i>')
    .replace(/(&quot;.*?&quot;|".*?")/g, '<i class="string">$1</i>')
    .replace(/\b(\d+(?:\.\d+)?)\b/g, '<i class="number">$1</i>');
}

export function CodeComparison({ notify }: { notify: (message: string) => void }) {
  const [file, setFile] = useState("billing.py");
  const sample = codeSamples[file];
  return <section className="panel" id="comparison">
    <div className="section-head"><div><small>ILLUSTRATIVE CODE</small><h2>Before &amp; after</h2></div><label className="file-picker"><FileCode2 size={14} /><select aria-label="Choose demo file" value={file} onChange={(event) => setFile(event.target.value)}>{Object.keys(codeSamples).map((name) => <option key={name}>{name}</option>)}</select><ChevronDown size={13} /></label></div>
    <div className="code-note"><LockKeyhole size={13} /> Read-only example. Real files are supplied by the configured Python backend.</div>
    <div className="editors">{(["before", "after"] as const).map((side) => <div className="editor" key={side}>
      <div className="editor-head"><span><i className={side === "before" ? "dot-red" : "dot-green"} />{side === "before" ? "Before refactoring" : "After refactoring"}</span><small>Python</small></div>
      <div className="editor-code" role="region" tabIndex={0} aria-label={`${side} refactoring`}>
        {sample[side].map((line, i) => {
          const diff = file === "billing.py"
            ? (side === "before" ? [0, 0, 1, 0, 0, 0, 0, 1, 0][i] : [1, 1, 1, 0, 0, 1, 1, 0, 0, 1][i])
            : side === "after" && file === "inventory.py" && i === 4 ? 1 : 0;
          return <div key={`${i}-${line}`} className={`code-line ${diff ? side === "before" ? "removed" : "added" : ""}`}><span>{i + 1}</span><code dangerouslySetInnerHTML={{ __html: syntax(line) || " " }} /></div>;
        })}
      </div>
    </div>)}</div>
    <div className="diff-footer"><span><i className="removed-key" />Removed <i className="added-key" />Added <i className="same-key" />Unchanged</span><button onClick={() => notify(`${file} is a read-only illustrative example.`)}>View full diff ↗</button></div>
    <p className="data-note">Illustrative code only; these files are not from a real repository.</p>
  </section>;
}

const metricIcons = { linesOfCode: Code2, complexity: Gauge, duplicateBlocks: FileCode2 };
const metricNotes = { linesOfCode: "Less code to maintain", complexity: "Simpler control flow", duplicateBlocks: "Fewer repeated patterns" };

export function QualityMetrics({ metrics, isDemo = true }: { metrics: QualityMetric[]; isDemo?: boolean }) {
  const chartData = metrics.map((metric) => ({ name: metric.label.replace("Avg. ", ""), Before: metric.before, After: metric.after }));
  return <section className="panel" id="metrics"><div className="section-head"><div><small>CODE HEALTH</small><h2>Quality metrics</h2></div><span className="demo-label">{isDemo ? "SAMPLE VALUES" : "BACKEND DATA"}</span></div>
    <div className="quality-cards">{metrics.map((metric) => {
      const Icon = metricIcons[metric.key];
      return <article className="quality-card" key={metric.key}><span className="quality-icon"><Icon size={16} /></span><b>{metric.label}</b><div className="quality-values"><span><small>BEFORE</small><strong>{metric.before}</strong></span><i>→</i><span><small>AFTER</small><strong className="green-text">{metric.after}</strong></span></div><small className="quality-note"><ArrowDownRight size={12} />{metricNotes[metric.key]}</small></article>;
    })}</div>
    {chartData.length > 0 ? <div className="chart-box"><div className="chart-title"><b>Before vs after refactor</b><small>{isDemo ? "Illustrative sample · lower is better" : "Backend-reported values · lower is better"}</small></div>
      <ResponsiveContainer width="100%" height={170}><BarChart data={chartData} margin={{ top: 8, right: 7, left: -20, bottom: 0 }} barGap={7}><CartesianGrid stroke="#202a39" vertical={false} /><XAxis dataKey="name" tick={{ fill: "#8290a4", fontSize: 10 }} axisLine={false} tickLine={false} /><YAxis tick={{ fill: "#718096", fontSize: 9 }} axisLine={false} tickLine={false} /><Tooltip contentStyle={{ background: "#111827", border: "1px solid #293449", borderRadius: 8, color: "#e5eaf2" }} /><Legend wrapperStyle={{ fontSize: 10, color: "#9ba8ba" }} /><Bar dataKey="Before" fill="#43516a" radius={[4, 4, 0, 0]} maxBarSize={27} /><Bar dataKey="After" fill="#5879f4" radius={[4, 4, 0, 0]} maxBarSize={27} /></BarChart></ResponsiveContainer>
    </div> : <p className="empty-state">No code quality metrics were supplied.</p>}<p className="data-note">{isDemo ? "Sample values only. Metrics are not measured from a connected repository." : "Metrics are supplied by the configured Python backend."}</p>
  </section>;
}

export function SafetyGuard() {
  const safeguards = ["Baseline tests pass before refactoring", "Test files protected from modification", "Changes validated before acceptance", "Failed attempts are rolled back", "Maximum retry count is configurable"];
  return <section className="panel" id="safety"><div className="section-head"><div><small>GUARDRAILS</small><h2>Safety guard</h2></div><span className="enforced"><ShieldCheck size={13} /> Backend-enforced</span></div>
    <div className="safety-list">{safeguards.map((item, index) => <div key={item}><span><Check size={12} /></span><p>{item}</p><small>{["Required", "Protected", "Required", "Automatic", "Configurable"][index]}</small></div>)}</div>
    <div className="warning-box"><AlertTriangle size={16} /><p><b>Verification has limits.</b> Test success is evidence of correctness, not a mathematical guarantee of identical behavior. Test coverage determines what the agent can verify.</p></div>
    <p className="safety-disclaimer">ⓘ These indicators describe intended backend controls. The frontend itself does not enforce safety protections.</p>
  </section>;
}

export interface ActivityEntry { time: string; level: string; text: string }

export function ActivityLogs({ entries, isDemo = true }: { entries: ActivityEntry[]; isDemo?: boolean }) {
  const ref = useRef<HTMLDivElement>(null);
  useEffect(() => { if (ref.current) ref.current.scrollTop = ref.current.scrollHeight; }, [entries]);
  return <section className="panel" id="activity"><div className="section-head"><div><small>EVENT STREAM</small><h2>Activity logs</h2></div><span className="simulated-dot"><i />{isDemo ? "Simulated logs" : "Backend status"}</span></div>
    <div className="terminal"><div className="terminal-head"><span className="traffic"><i /><i /><i /></span><span>◉ &nbsp;refactor-agent — {isDemo ? "demo" : "API"}</span><button aria-label="Scroll to latest activity" onClick={() => { if (ref.current) ref.current.scrollTop = ref.current.scrollHeight; }}>↓</button></div>
      <div className="terminal-content" role="log" aria-live="polite" ref={ref}>{entries.length ? entries.map((entry, index) => <div key={`${entry.time}-${index}`}><time>[{entry.time}]</time><b className={`level-${entry.level}`}>[{entry.level.toUpperCase()}]</b><span>{entry.text}</span></div>) : <p className="empty-state">{isDemo ? "No demo events yet." : "No backend status updates yet."}</p>}</div>
    </div><p className="data-note">{isDemo ? "Simulated demo events, not output from Python, an LLM, or pytest." : "These are status messages returned by the backend API, not raw process logs."}</p>
  </section>;
}

export function SettingsPanel({ initial, onSave }: { initial: RefactorSettings; onSave: (settings: RefactorSettings) => void }) {
  const [settings, setSettings] = useState(initial);
  function update<K extends keyof RefactorSettings>(key: K, value: RefactorSettings[K]) {
    setSettings((current) => ({ ...current, [key]: value }));
  }
  return <section className="panel" id="settings"><div className="section-head"><div><small>CONFIGURATION</small><h2>Agent settings</h2></div><span className="demo-mode">{settings.demoMode ? "DEMO MODE" : "BACKEND MODE"} <i /></span></div>
    <form className="settings-form" onSubmit={(event) => { event.preventDefault(); onSave(settings); }}>
      <label className="wide"><span>Repository path</span><input value={settings.repositoryPath} onChange={(event) => update("repositoryPath", event.target.value)} /><small>Read by the Python backend only; browsers cannot access local project files.</small></label>
      <label><span>Maximum retries</span><input type="number" min={0} max={10} value={settings.maximumRetries} onChange={(event) => update("maximumRetries", Number(event.target.value))} /></label>
      <label><span>Test timeout (seconds)</span><input type="number" min={10} max={3600} value={settings.testTimeoutSeconds} onChange={(event) => update("testTimeoutSeconds", Number(event.target.value))} /></label>
      <label><span>Execution mode</span><select value={settings.executionMode} onChange={(event) => update("executionMode", event.target.value as RefactorSettings["executionMode"])}><option value="autonomous">Autonomous</option><option value="assisted">Assisted review</option></select></label>
      <label><span>Demo mode</span><span className="toggle-line"><button type="button" className={`toggle ${settings.demoMode ? "on" : ""}`} aria-pressed={settings.demoMode} onClick={() => update("demoMode", !settings.demoMode)}><i /></button><small>{settings.demoMode ? "Simulated workflow" : "Backend required"}</small></span></label>
      <div className="settings-actions"><span>ⓘ API secrets are never requested or stored.</span><button className="primary-button compact" type="submit">Save settings</button></div>
    </form>
  </section>;
}
