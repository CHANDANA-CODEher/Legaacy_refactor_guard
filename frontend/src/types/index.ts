export type RunStatus = "accepted" | "rolled_back" | "running" | "failed";
export type WorkflowStage = "scan" | "baseline" | "planning" | "refactoring" | "verification" | "decision";

export interface TestCounts {
  total: number;
  passed: number;
  failed: number;
}

export interface RefactorAttempt {
  attempt: number;
  targetFile: string;
  goal: string;
  tests: TestCounts;
  failingTests: string[];
  errorSummary: string | null;
  status: RunStatus;
  timestamp: string;
}

export interface RunLog {
  repositoryName: string;
  startedAt: string;
  baselineTests: TestCounts;
  attempts: RefactorAttempt[];
  finalTests: TestCounts;
  filesChanged: string[];
  isDemo: boolean;
}

export interface QualityMetric {
  key: "linesOfCode" | "complexity" | "duplicateBlocks";
  label: string;
  before: number;
  after: number;
  unit?: string;
}

export interface DashboardData {
  runLog: RunLog;
  metrics: QualityMetric[];
  source: "demo" | "backend";
}

export interface RefactorSettings {
  repositoryPath: string;
  maximumRetries: number;
  testTimeoutSeconds: number;
  executionMode: "assisted" | "autonomous";
  demoMode: boolean;
}

export interface RunStatusResponse {
  status: RunStatus;
  stage: WorkflowStage;
  message: string;
}

export interface HistoryItem {
  filename: string;
  repo: string;
  started_at: string;
  provider: string;
  baseline: { passed: number; failed: number; total?: number };
  final: { passed: number; failed: number; files_changed?: string[] };
  attempts_count: number;
}
