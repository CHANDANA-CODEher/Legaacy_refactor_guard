import {
  ArrowUpRight, Bell, Check, ChevronRight, Clock3, Code2, FlaskConical, GitBranch,
  LoaderCircle, Menu, Play, RotateCcw, ShieldCheck, Sparkles, X,
} from "lucide-react";
import { useEffect, useRef, useState } from "react";
import {
  ActivityLogs, AttemptTimeline, CodeComparison, MetricCard, QualityMetrics, SafetyGuard,
  SettingsPanel, Sidebar, TestResults, WorkflowStepper,
  type ActivityEntry, type NavId,
} from "./components/DashboardSections";
import { defaultSettings, demoActivity, demoDashboardData } from "./data/mockData";
import { getDashboardData, getRunStatus, isApiConfigured, startRefactoring } from "./services/api";
import type { DashboardData, RefactorAttempt, RefactorSettings, WorkflowStage } from "./types";

const pageNames: Record<NavId, string> = {
  overview: "Overview",
  repository: "Repository",
  runs: "Refactor Runs",
  tests: "Test Results",
  comparison: "Code Comparison",
  metrics: "Quality Metrics",
  activity: "Activity Logs",
  settings: "Settings",
};
const stages: WorkflowStage[] = ["scan", "baseline", "planning", "refactoring", "verification", "decision"];

function currentTime() {
  return new Date().toLocaleTimeString("en-GB", { hour12: false });
}

export default function App() {
  const [activePage, setActivePage] = useState<NavId>("overview");
  const [collapsed, setCollapsed] = useState(false);
  const [mobileOpen, setMobileOpen] = useState(false);
  const [confirmOpen, setConfirmOpen] = useState(false);
  const [notificationOpen, setNotificationOpen] = useState(false);
  const [running, setRunning] = useState(false);
  const [completed, setCompleted] = useState(true);
  const [stage, setStage] = useState<WorkflowStage>("decision");
  const [dashboard, setDashboard] = useState<DashboardData>(demoDashboardData);
  const [attempts, setAttempts] = useState<RefactorAttempt[]>(demoDashboardData.runLog.attempts);
  const [activity, setActivity] = useState<ActivityEntry[]>(demoActivity);
  const [activityIsDemo, setActivityIsDemo] = useState(true);
  const [settings, setSettings] = useState<RefactorSettings>(defaultSettings);
  const [lastRun, setLastRun] = useState("Today at 10:00 AM");
  const [dataError, setDataError] = useState("");
  const [loadingData, setLoadingData] = useState(isApiConfigured);
  const [runError, setRunError] = useState("");
  const [toast, setToast] = useState("");
  const [toastIsError, setToastIsError] = useState(false);
  const timers = useRef<number[]>([]);
  const confirmButtonRef = useRef<HTMLButtonElement>(null);
  const toastTimer = useRef<number | undefined>(undefined);

  function notify(message: string, isError = false) {
    setToast(message);
    setToastIsError(isError);
    window.clearTimeout(toastTimer.current);
    toastTimer.current = window.setTimeout(() => setToast(""), 3800);
  }

  useEffect(() => () => {
    timers.current.forEach(window.clearTimeout);
    window.clearTimeout(toastTimer.current);
  }, []);

  useEffect(() => {
    if (!confirmOpen) return;
    confirmButtonRef.current?.focus();
    const closeOnEscape = (event: KeyboardEvent) => {
      if (event.key === "Escape") setConfirmOpen(false);
    };
    window.addEventListener("keydown", closeOnEscape);
    return () => window.removeEventListener("keydown", closeOnEscape);
  }, [confirmOpen]);

  useEffect(() => {
    if (!isApiConfigured) return;
    let active = true;
    getDashboardData()
      .then((data) => {
        if (!active) return;
        setDashboard(data);
        setAttempts(data.runLog.attempts);
        setActivity([]);
        setActivityIsDemo(false);
        setLastRun(new Date(data.runLog.startedAt).toLocaleString());
        setDataError("");
      })
      .catch((error: unknown) => {
        if (active) setDataError(error instanceof Error ? error.message : "Could not load dashboard data.");
      })
      .finally(() => { if (active) setLoadingData(false); });
    return () => { active = false; };
  }, []);

  function navigate(id: NavId) {
    setActivePage(id);
    const targetId = id === "overview" ? "overview" : id;
    document.getElementById(targetId)?.scrollIntoView({ behavior: "smooth", block: id === "overview" ? "start" : "center" });
  }

  function log(level: string, text: string) {
    setActivity((current) => [...current, { time: currentTime(), level, text }]);
  }

  async function startBackendRun() {
    if (!isApiConfigured) {
      const message = "Backend API is not configured. Set VITE_API_BASE_URL or enable demo mode.";
      setConfirmOpen(false);
      setRunError(message);
      notify(message, true);
      return;
    }
    setConfirmOpen(false);
    setRunning(true);
    setCompleted(false);
    setRunError("");
    setActivity([]);
    setActivityIsDemo(false);
    try {
      const { runId } = await startRefactoring(settings);
      log("info", `Backend run started: ${runId}`);
      let response = await getRunStatus(runId);
      for (let poll = 0; poll < 180; poll += 1) {
        setStage(response.stage);
        if (response.message) log("info", response.message);
        if (response.status !== "running") break;
        await new Promise((resolve) => window.setTimeout(resolve, 1000));
        response = await getRunStatus(runId);
      }
      if (response.status === "running") throw new Error("The run did not finish within three minutes.");
      const latest = await getDashboardData();
      setDashboard(latest);
      setAttempts(latest.runLog.attempts);
      setLastRun(new Date(latest.runLog.startedAt).toLocaleString());
      const accepted = response.status === "accepted";
      setStage(response.stage);
      setCompleted(accepted);
      setRunning(false);
      if (accepted) notify("Backend run completed and reported acceptance.");
      else {
        const message = response.message || `Backend run ended with status: ${response.status}.`;
        setRunError(message);
        notify(message, true);
      }
    } catch (error) {
      const message = error instanceof Error ? error.message : "The backend run failed.";
      setRunError(message);
      setRunning(false);
      log("error", message);
      notify(`Backend run failed: ${message}`, true);
    }
  }

  function startDemo() {
    if (!settings.demoMode) {
      void startBackendRun();
      return;
    }
    if (running) return;
    setConfirmOpen(false);
    setRunning(true);
    setCompleted(false);
    setRunError("");
    setDashboard(demoDashboardData);
    setLastRun("Today at 10:00 AM");
    setAttempts([]);
    setActivity([]);
    setActivityIsDemo(true);
    setStage("scan");
    log("info", "Demo workflow started — no files will be changed.");
    const messages: Record<WorkflowStage, [string, string]> = {
      scan: ["success", "Repository scan completed (simulated)"],
      baseline: ["success", "Baseline tests passed: 24/24 (simulated)"],
      planning: ["info", "Refactoring target selected: billing.py"],
      refactoring: ["warning", "Attempt 1 generated · test feedback simulated"],
      verification: ["error", "Attempt 1 failed 2 tests · rollback simulated"],
      decision: ["success", "Retry passed 24/24 · changes accepted (simulated)"],
    };
    stages.forEach((nextStage, index) => {
      const timer = window.setTimeout(() => {
        setStage(nextStage);
        const [level, message] = messages[nextStage];
        log(level, message);
        if (nextStage === "verification") {
          setAttempts([demoDashboardData.runLog.attempts[0]]);
          setActivity((current) => [...current, { time: currentTime(), level: "info", text: "Retry started using simulated test feedback" }]);
        }
        if (nextStage === "decision") {
          setAttempts(demoDashboardData.runLog.attempts);
          setRunning(false);
          setCompleted(true);
          setLastRun("Just now");
          notify("Demo run complete — the simulated refactor passed verification.");
        }
      }, 1050 * (index + 1));
      timers.current.push(timer);
    });
  }

  function resetDemo() {
    timers.current.forEach(window.clearTimeout);
    timers.current = [];
    setRunning(false);
    setCompleted(true);
    setStage("decision");
    setAttempts(demoDashboardData.runLog.attempts);
    setDashboard(demoDashboardData);
    setActivity(demoActivity);
    setActivityIsDemo(true);
    setRunError("");
    setLastRun("Today at 10:00 AM");
    notify("Demo dashboard reset to its sample state.");
  }

  function saveSettings(next: RefactorSettings) {
    setSettings(next);
    notify("Settings updated for this session.");
  }

  return <div className={`app-shell ${collapsed ? "is-collapsed" : ""}`}>
    <Sidebar active={activePage} collapsed={collapsed} mobileOpen={mobileOpen} onNavigate={navigate} onToggle={() => setCollapsed((value) => !value)} onClose={() => setMobileOpen(false)} />
    <main className="main-area">
      <header className="topbar">
        <div className="topbar-start"><button className="mobile-menu" aria-label="Open navigation" onClick={() => setMobileOpen(true)}><Menu size={19} /></button><div className="breadcrumb"><span>Workspace</span><ChevronRight size={13} /><b>{pageNames[activePage]}</b></div></div>
        <div className="topbar-end">
          <div className="repo-status"><GitBranch size={15} /><b>{dashboard.runLog.repositoryName}</b><i /></div><span className="top-separator" />
          <span className={`agent-status ${running ? "is-running" : ""}`}><i />{running ? "Agent working" : "Agent ready"}</span>
          <div className="notification-wrap"><button className="notification-button" aria-label="Notifications" aria-expanded={notificationOpen} onClick={() => setNotificationOpen((value) => !value)}><Bell size={17} /><i /></button>
            {notificationOpen && <div className="notification-popover"><b>Notifications</b><p><span><Check size={12} /></span>Latest demo run verified successfully.</p><small>Illustrative demo notification</small></div>}
          </div><span className="avatar top-avatar">JD</span>
        </div>
      </header>

      <div className="content">
        <section className="hero" id="overview">
          <div className="hero-copy">
            <div className="hero-kicker"><span><Sparkles size={12} /></span> AI-POWERED REFACTORING <i /> SAFETY-FIRST</div>
            <h1>Refactor fearlessly.<br /><em>Verify everything.</em></h1>
            <p>An autonomous coding agent that improves legacy code<br className="desktop-break" /> without sacrificing correctness.</p>
            <div className="hero-buttons">
              <button className="primary-button" disabled={running} onClick={() => setConfirmOpen(true)}>{running ? <><LoaderCircle size={15} className="spin" />Running demo...</> : <><Play size={14} fill="currentColor" />Run refactoring</>}</button>
              <button className="secondary-button" onClick={() => navigate("comparison")}><Code2 size={15} />View code changes</button>
            </div>
            <div className="hero-meta"><span><Clock3 size={13} />Last run: {lastRun}</span><span className={running ? "live-agent" : ""}><i />{running ? "Workflow in progress" : "Agent is idle"}</span><button onClick={resetDemo}><RotateCcw size={12} />Reset demo</button></div>
          </div>
          <HeroArt running={running} />
        </section>

        <div className={`demo-banner ${dashboard.source === "backend" ? "backend-banner" : ""}`}><span className="banner-icon">✦</span><span><b>{dashboard.source === "backend" ? "CONNECTED BACKEND" : "DEMO ENVIRONMENT"}</b><i />{dashboard.source === "backend" ? " Dashboard data is supplied by the configured Python API." : " All figures, activity, and code shown are illustrative sample data."}</span><button onClick={() => navigate("settings")}>{dashboard.source === "backend" ? "API settings" : "Configure backend"} <ArrowUpRight size={13} /></button></div>
        {loadingData && <div className="inline-state" role="status"><LoaderCircle size={14} className="spin" /> Connecting to dashboard API…</div>}
        {dataError && <div className="inline-state error-state" role="alert"><X size={14} />{dataError}</div>}
        {runError && <div className="inline-state error-state" role="alert"><X size={14} />{runError}</div>}

        <section className="metrics-grid" id="repository" aria-label="Repository summary metrics">
          <MetricCard label="Baseline tests" value={`${dashboard.runLog.baselineTests.passed} / ${dashboard.runLog.baselineTests.total}`} note="passed before changes" icon={FlaskConical} tone="blue" trend={dashboard.runLog.baselineTests.total ? `${Math.round(dashboard.runLog.baselineTests.passed / dashboard.runLog.baselineTests.total * 100)}%` : undefined} isDemo={dashboard.source === "demo"} />
          <MetricCard label="Refactoring attempts" value={String(attempts.length)} note="in the latest run" icon={Sparkles} tone="purple" trend={attempts.some((attempt) => attempt.status === "rolled_back") ? "Rollback recorded" : undefined} isDemo={dashboard.source === "demo"} />
          <MetricCard label="Final test results" value={`${dashboard.runLog.finalTests.passed} / ${dashboard.runLog.finalTests.total}`} note="passed after verification" icon={ShieldCheck} tone="green" trend={dashboard.runLog.finalTests.total ? `${Math.round(dashboard.runLog.finalTests.passed / dashboard.runLog.finalTests.total * 100)}%` : undefined} isDemo={dashboard.source === "demo"} />
          <MetricCard label="Files changed" value={`${dashboard.runLog.filesChanged.length} ${dashboard.runLog.filesChanged.length === 1 ? "file" : "files"}`} note={dashboard.runLog.filesChanged.join(", ") || "No files reported"} icon={Code2} tone="amber" isDemo={dashboard.source === "demo"} />
        </section>

        <WorkflowStepper current={stage} running={running} completed={completed} />
        <div className="dashboard-grid">
          <div className="column main-column">
            <AttemptTimeline attempts={attempts} isDemo={dashboard.source === "demo"} />
            <TestResults baseline={dashboard.runLog.baselineTests} attempts={attempts} finalTests={dashboard.runLog.finalTests} isDemo={dashboard.source === "demo"} />
            <CodeComparison notify={notify} />
          </div>
          <div className="column side-column">
            <QualityMetrics metrics={dashboard.metrics} isDemo={dashboard.source === "demo"} />
            <SafetyGuard />
            <ActivityLogs entries={activity} isDemo={activityIsDemo} />
            <SettingsPanel initial={settings} onSave={saveSettings} />
          </div>
        </div>
        <footer className="footer"><span>© 2025 Legacy Refactor Guard</span><span><ShieldCheck size={13} /> Verify every change. Keep control.</span><button onClick={() => notify("See README.md for the backend integration contract.")}>ⓘ Integration help</button></footer>
      </div>
    </main>

    {confirmOpen && <div className="modal-backdrop" onMouseDown={(event) => { if (event.target === event.currentTarget) setConfirmOpen(false); }}>
      <section className="confirm-modal" role="dialog" aria-modal="true" aria-labelledby="confirm-title">
        <button className="modal-x" aria-label="Close dialog" onClick={() => setConfirmOpen(false)}><X size={17} /></button>
        <div className="modal-icon"><Sparkles size={20} /></div>        <small>{settings.demoMode ? "DEMO RUN" : "BACKEND RUN"}</small><h2 id="confirm-title">{settings.demoMode ? "Start a simulated refactor?" : "Start a backend refactor?"}</h2>
        <p>{settings.demoMode ? "This demo will animate the agent workflow, show an illustrative failed attempt and rollback, then finish with a simulated passing retry." : "The configured Python backend will receive these settings and run the refactor. The frontend does not access repository files directly."}</p>
        <div className="modal-note"><ShieldCheck size={15} />{settings.demoMode ? "No Python, LLM, pytest, or repository files will be touched." : isApiConfigured ? "The configured backend is responsible for executing and enforcing safety controls." : "No backend API URL is configured yet. Configure VITE_API_BASE_URL before starting."}</div>
        <div className="modal-actions"><button className="secondary-button" onClick={() => setConfirmOpen(false)}>Cancel</button><button ref={confirmButtonRef} className="primary-button" onClick={startDemo}><Play size={13} fill="currentColor" />{settings.demoMode ? "Start demo" : "Start backend run"}</button></div>
      </section>
    </div>}
    {toast && <div className={`toast ${toastIsError ? "error-toast" : ""}`} role={toastIsError ? "alert" : "status"}><span>{toastIsError ? <X size={13} /> : <Check size={13} />}</span>{toast}<button aria-label="Dismiss notification" onClick={() => setToast("")}><X size={13} /></button></div>}
  </div>;
}

function HeroArt({ running }: { running: boolean }) {
  return <div className="hero-art" aria-hidden="true"><div className="art-glow" /><div className="orbit orbit-one" /><div className="orbit orbit-two" />
    <div className="hero-shield"><ShieldCheck size={45} strokeWidth={1.4} /><span><Code2 size={17} /></span></div>
    <i className="float-icon float-check"><Check size={14} /></i><i className="float-icon float-code"><Code2 size={14} /></i><i className="float-icon float-test"><FlaskConical size={14} /></i>
    <div className="hero-score"><i className={running ? "score-running" : ""} /><small>{running ? "VERIFYING CHANGES" : "TESTS VERIFIED"}</small><b>24<em>/24</em></b></div>
  </div>;
}
