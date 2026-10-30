import {
  AlertCircle,
  CheckCircle2,
  Code2,
  Copy,
  ExternalLink,
  FlaskConical,
  GitBranch,
  ShieldCheck,
  Terminal,
  X,
} from "lucide-react";
import { useEffect, useState } from "react";
import {
  AttemptTimeline,
  CodeDiffView,
  HistoryView,
  MetricCard,
  QualityMetricsView,
  RefactorStudioView,
  SafetySettingsView,
  SidebarNav,
  type TabId,
  TestResultsView,
  WorkflowPipeline,
} from "./components/DashboardSections";
import { defaultSettings, demoDashboardData } from "./data/mockData";
import {
  getDashboardData,
  getHistory,
} from "./services/api";
import type {
  DashboardData,
  HistoryItem,
  RefactorSettings,
  WorkflowStage,
} from "./types";

const tabTitles: Record<TabId, string> = {
  studio: "Refactor Studio & Verification Lab",
  overview: "System Overview & Execution Pipeline",
  tests: "Automated Verification & Unit Tests",
  comparison: "Code Diff & AST Structure",
  metrics: "Code Quality & Complexity Metrics",
  history: "Historical Execution Logs",
  safety: "Security Safeguards & Configuration",
};

export default function App() {
  const [activeTab, setActiveTab] = useState<TabId>("studio");
  const [dashboard, setDashboard] = useState<DashboardData>(demoDashboardData);
  const [history, setHistory] = useState<HistoryItem[]>([]);
  const [settings, setSettings] = useState<RefactorSettings>(defaultSettings);
  const [refreshing, setRefreshing] = useState(false);
  const [toastMessage, setToastMessage] = useState("");
  const [toastType, setToastType] = useState<"success" | "error">("success");
  const [stage] = useState<WorkflowStage>("decision");

  const notify = (msg: string, isError = false) => {
    setToastMessage(msg);
    setToastType(isError ? "error" : "success");
    setTimeout(() => setToastMessage(""), 3500);
  };

  const loadBackendData = async (showToast = false) => {
    setRefreshing(true);
    try {
      const [dashData, histData] = await Promise.all([
        getDashboardData(),
        getHistory().catch(() => []),
      ]);
      setDashboard(dashData);
      setHistory(histData);
      if (showToast) {
        notify("System data refreshed successfully!");
      }
    } catch (err) {
      console.warn("Could not connect to engine:", err);
      if (showToast) {
        notify("Could not reach service at 127.0.0.1:8000.", true);
      }
    } finally {
      setRefreshing(false);
    }
  };

  useEffect(() => {
    loadBackendData(false);
  }, []);

  const isLive = dashboard.source === "backend";
  const runLog = dashboard.runLog;

  const copyCliCommand = () => {
    navigator.clipboard.writeText("py run_demo.py");
    notify("Copied to clipboard: py run_demo.py");
  };

  return (
    <div className="app-shell">
      {/* Left Column Sidebar Navigation */}
      <SidebarNav
        activeTab={activeTab}
        onSelectTab={setActiveTab}
        repoName={runLog.repositoryName}
        isLive={isLive}
        onRefresh={() => loadBackendData(true)}
        refreshing={refreshing}
      />

      {/* Main Workspace (opens the selected sidebar section) */}
      <div className="app-workspace">
        <header className="workspace-topbar">
          <div className="topbar-left">
            <h2 className="topbar-title">{tabTitles[activeTab]}</h2>
            <span className="topbar-subtitle">Autonomous safety-first refactoring</span>
          </div>

          <div className="topbar-right">
            <div className="cli-badge">
              <Terminal size={13} className="text-emerald" />
              <code className="font-mono">py run_demo.py</code>
              <button className="icon-copy-btn" onClick={copyCliCommand} title="Copy CLI Command">
                <Copy size={13} />
              </button>
            </div>
            <a
              href="http://127.0.0.1:8000/docs"
              target="_blank"
              rel="noreferrer"
              className="api-docs-link"
            >
              <span>API Reference</span>
              <ExternalLink size={13} />
            </a>
          </div>
        </header>

        <main className="workspace-body">
          {/* Section 0: Interactive Refactor Studio & Verification Lab */}
          {activeTab === "studio" && (
            <div className="tab-pane animate-fade-in">
              <RefactorStudioView notify={notify} onRunComplete={() => loadBackendData(false)} />
            </div>
          )}

          {/* Section 1: Overview */}
          {activeTab === "overview" && (
            <div className="tab-pane animate-fade-in">
              <div className="metrics-grid">
                <MetricCard
                  label="Baseline Tests"
                  value={`${runLog.baselineTests.passed} / ${runLog.baselineTests.total}`}
                  subtext="100% pre-refactor tests passed"
                  icon={FlaskConical}
                  variant="success"
                />
                <MetricCard
                  label="Refactor Attempts"
                  value={String(runLog.attempts.length)}
                  subtext="Attempts evaluated against pytest"
                  icon={Code2}
                  variant="neutral"
                />
                <MetricCard
                  label="Final Verification"
                  value={`${runLog.finalTests.passed} / ${runLog.finalTests.total}`}
                  subtext="All assertions preserved & verified"
                  icon={ShieldCheck}
                  variant="info"
                />
                <MetricCard
                  label="Target Files Changed"
                  value={String(runLog.filesChanged.length)}
                  subtext={runLog.filesChanged.join(", ") || "None"}
                  icon={GitBranch}
                  variant="warning"
                />
              </div>

              <div className="dashboard-columns">
                <div className="col-main">
                  <AttemptTimeline attempts={runLog.attempts} isLive={isLive} />
                </div>
                <div className="col-side">
                  <WorkflowPipeline
                    currentStage={stage}
                    isRunning={false}
                    isCompleted={true}
                  />
                </div>
              </div>
            </div>
          )}

          {/* Section 2: Tests */}
          {activeTab === "tests" && (
            <div className="tab-pane animate-fade-in">
              <TestResultsView
                baseline={runLog.baselineTests}
                finalTests={runLog.finalTests}
                attempts={runLog.attempts}
              />
            </div>
          )}

          {/* Section 3: Code Diff */}
          {activeTab === "comparison" && (
            <div className="tab-pane animate-fade-in">
              <CodeDiffView notify={notify} />
            </div>
          )}

          {/* Section 4: Quality Metrics */}
          {activeTab === "metrics" && (
            <div className="tab-pane animate-fade-in">
              <QualityMetricsView metrics={dashboard.metrics} />
            </div>
          )}

          {/* Section 5: Historical Runs */}
          {activeTab === "history" && (
            <div className="tab-pane animate-fade-in">
              <HistoryView history={history} />
            </div>
          )}

          {/* Section 6: Safety & Settings */}
          {activeTab === "safety" && (
            <div className="tab-pane animate-fade-in">
              <SafetySettingsView
                settings={settings}
                onSave={setSettings}
                notify={notify}
              />
            </div>
          )}
        </main>
      </div>

      {/* Floating Notification Toast */}
      {toastMessage && (
        <div className={`app-toast toast-${toastType}`}>
          {toastType === "success" ? <CheckCircle2 size={16} /> : <AlertCircle size={16} />}
          <span>{toastMessage}</span>
          <button className="toast-close" onClick={() => setToastMessage("")}>
            <X size={14} />
          </button>
        </div>
      )}
    </div>
  );
}