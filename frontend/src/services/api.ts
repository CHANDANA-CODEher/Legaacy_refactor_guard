import type { DashboardData, HistoryItem, RefactorSettings, RunLog, RunStatusResponse } from "../types";

const API_BASE_URL = (import.meta.env.VITE_API_BASE_URL ?? "http://127.0.0.1:8000").replace(/\/$/, "");

export const isApiConfigured = API_BASE_URL.length > 0;

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  if (!API_BASE_URL) {
    throw new Error("Backend API is not configured. Set VITE_API_BASE_URL to connect it.");
  }
  const response = await fetch(`${API_BASE_URL}${path}`, {
    ...init,
    headers: { "Content-Type": "application/json", ...init?.headers },
  });
  if (!response.ok) {
    let detail = "";
    try {
      const err = await response.json();
      detail = err.detail || "";
    } catch {
      // ignore
    }
    throw new Error(detail || `Backend request failed (${response.status} ${response.statusText}).`);
  }
  return (await response.json()) as T;
}

export const getHealth = () => request<{ status: string; service: string }>("/health");
export const getDemoStatus = () => request<Record<string, unknown>>("/demo/status");
export const getDashboardData = () => request<DashboardData>("/api/dashboard");
export const getRunLog = () => request<RunLog>("/api/run-log");
export const getRawRunLog = () => request<Record<string, unknown>>("/api/log");
export const getHistory = () => request<HistoryItem[]>("/api/history");
export const getMetrics = () => request<DashboardData["metrics"]>("/api/metrics");
export const startRefactoring = (settings: RefactorSettings) =>
  request<{ runId: string }>("/api/runs", { method: "POST", body: JSON.stringify(settings) });
export const getRunStatus = (runId: string) =>
  request<RunStatusResponse>(`/api/runs/${encodeURIComponent(runId)}/status`);

export interface SandboxRequest {
  target_file: string;
  goal: string;
  scenario: "safe_refactor" | "broken_code_rollback" | "custom_code";
  custom_code?: string;
  provider?: string;
}

export interface SandboxResponse {
  success: boolean;
  status: "accepted" | "rolled_back" | "failed";
  message: string;
  baseline: { passed: number; failed: number; total: number };
  final: { passed: number; failed: number; files_changed: string[] };
  target_file: string;
  goal: string;
  scenario: string;
  before_code: string;
  after_code: string;
  restored_byte_for_byte: boolean;
  attempts: Array<{
    attempt: number;
    tests_passed: number;
    tests_failed: number;
    status: string;
    failing_tests?: string[];
    error_summary?: string;
  }>;
  real_repo_protected: boolean;
}

export const getSampleCode = (filename = "shop.py") =>
  request<{ filename: string; code: string; lines: number }>(
    `/api/refactor/sample-code?filename=${encodeURIComponent(filename)}`
  );

export const runSandboxRefactor = (payload: SandboxRequest) =>
  request<SandboxResponse>("/api/refactor/sandbox", {
    method: "POST",
    body: JSON.stringify(payload),
  });
