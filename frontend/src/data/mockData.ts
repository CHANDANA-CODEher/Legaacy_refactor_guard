import type { DashboardData, RefactorSettings } from "../types";

export const demoDashboardData: DashboardData = {
  source: "demo",
  runLog: {
    repositoryName: "legacy-billing-service",
    startedAt: "2025-02-14T10:00:00Z",
    baselineTests: { total: 24, passed: 24, failed: 0 },
    attempts: [
      {
        attempt: 1,
        targetFile: "billing.py",
        goal: "Remove duplicated tax calculation logic",
        tests: { total: 24, passed: 22, failed: 2 },
        failingTests: ["test_rounding_precision", "test_tax_total_for_invoice"],
        errorSummary: "Rounding behavior changed for fractional tax amounts.",
        status: "rolled_back",
        timestamp: "10:00:12",
      },
      {
        attempt: 2,
        targetFile: "billing.py",
        goal: "Extract shared tax calculation with precision preserved",
        tests: { total: 24, passed: 24, failed: 0 },
        failingTests: [],
        errorSummary: null,
        status: "accepted",
        timestamp: "10:00:22",
      },
    ],
    finalTests: { total: 24, passed: 24, failed: 0 },
    filesChanged: ["billing.py"],
    isDemo: true,
  },
  metrics: [
    { key: "linesOfCode", label: "Lines of code", before: 420, after: 350 },
    { key: "complexity", label: "Avg. complexity", before: 8.2, after: 5.6 },
    { key: "duplicateBlocks", label: "Duplicate blocks", before: 12, after: 4 },
  ],
};

export const defaultSettings: RefactorSettings = {
  repositoryPath: "C:\\projects\\legacy-billing-service",
  maximumRetries: 3,
  testTimeoutSeconds: 120,
  executionMode: "autonomous",
  demoMode: true,
};

export const demoActivity = [
  { time: "10:00:01", level: "success", text: "Repository scan completed" },
  { time: "10:00:03", level: "info", text: "Baseline tests started" },
  { time: "10:00:06", level: "success", text: "Baseline tests passed: 24/24" },
  { time: "10:00:08", level: "info", text: "Refactoring target selected: billing.py" },
  { time: "10:00:12", level: "warning", text: "Attempt 1 completed · 2 test failures" },
  { time: "10:00:14", level: "error", text: "Rollback completed · rounding behavior changed" },
  { time: "10:00:17", level: "info", text: "Attempt 2 started with test feedback" },
  { time: "10:00:21", level: "success", text: "All tests passed: 24/24" },
  { time: "10:00:22", level: "success", text: "Refactor accepted" },
];
