import type { DashboardData, RefactorSettings, RunLog, RunStatusResponse } from "../types";

const API_BASE_URL = (import.meta.env.VITE_API_BASE_URL ?? "").replace(/\/$/, "");

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
    throw new Error(`Backend request failed (${response.status} ${response.statusText}).`);
  }
  return (await response.json()) as T;
}

export const getDashboardData = () => request<DashboardData>("/api/dashboard");
export const getRunLog = () => request<RunLog>("/api/run-log");
export const getMetrics = () => request<DashboardData["metrics"]>("/api/metrics");
export const startRefactoring = (settings: RefactorSettings) =>
  request<{ runId: string }>("/api/runs", { method: "POST", body: JSON.stringify(settings) });
export const getRunStatus = (runId: string) =>
  request<RunStatusResponse>(`/api/runs/${encodeURIComponent(runId)}/status`);
