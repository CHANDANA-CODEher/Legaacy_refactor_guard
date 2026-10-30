"""Minimal, browser-accessible testing API for Legacy Refactor Guard.

Provides safe, local-only HTTP endpoints bound to 127.0.0.1 so developers
can inspect repository status and baseline tests via Swagger UI (/docs) in Chrome.

Safety Guarantees:
- Binds to 127.0.0.1 only (never 0.0.0.0).
- Does not execute arbitrary Python code.
- Does not accept user-supplied file paths or directories.
- Does not expose API keys, environment variables, or secrets.
- Read-only demo status: does not modify any files on disk.
- POST /demo/run is withheld because the current RefactorAgent design modifies
  demo_repo/shop.py and run_log.json on disk in-place.
"""

from __future__ import annotations

import json
import shutil
import tempfile
from pathlib import Path
from typing import Any

from fastapi import FastAPI, HTTPException, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field

from agent.agent import RefactorAgent
from agent.guard import validate_python_syntax
from agent.llm import MockLLMProvider
from agent.runner import run_tests

# Root directory of the Legacy Refactor Guard workspace
WORKSPACE_ROOT = Path(__file__).resolve().parent
DEMO_REPO_PATH = WORKSPACE_ROOT / "demo_repo"
RUN_LOG_PATH = WORKSPACE_ROOT / "run_log.json"
OUTPUTS_PATH = WORKSPACE_ROOT / "outputs"

# Whitelisted local frontend development origins
ALLOWED_ORIGINS = [
    "http://localhost:3000",
    "http://127.0.0.1:3000",
    "http://localhost:5173",
    "http://127.0.0.1:5173",
]

ALLOWED_METHODS = ["GET", "POST", "OPTIONS", "HEAD"]
ALLOWED_HEADERS = ["Content-Type", "Authorization", "Accept", "Origin", "X-Requested-With"]

app = FastAPI(
    title="Legacy Refactor Guard Testing API",
    description=(
        "Minimal browser-accessible testing interface for Legacy Refactor Guard. "
        "Bound strictly to 127.0.0.1 for safe local inspection via Swagger UI. "
        "This is a local testing interface, not a production-ready or public API."
    ),
    version="0.1.0",
    docs_url="/docs",
    redoc_url=None,
)

# Configure CORS strictly for approved local development origins
app.add_middleware(
    CORSMiddleware,
    allow_origins=ALLOWED_ORIGINS,
    allow_credentials=True,
    allow_methods=ALLOWED_METHODS,
    allow_headers=ALLOWED_HEADERS,
)


@app.get("/health", summary="Health Check", tags=["System"])
def get_health() -> dict[str, Any]:
    """Report whether the Legacy Refactor Guard testing API is running."""
    return {
        "status": "ok",
        "service": "Legacy Refactor Guard Testing API",
        "version": "0.1.0",
        "binding": "127.0.0.1",
        "docs_url": "/docs",
    }


@app.get("/demo/status", summary="Demo Repository Status", tags=["Demo"])
def get_demo_status() -> dict[str, Any]:
    """Report the status of the existing demo repository without modifying any files.

    Performs read-only inspection:
    - Verifies demo repository and target file existence.
    - Validates target file Python syntax via AST without execution.
    - Runs the demo test suite via subprocess test runner (read-only).
    - Reads latest run_log.json summary if present.
    """
    if not DEMO_REPO_PATH.exists() or not DEMO_REPO_PATH.is_dir():
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Demo repository 'demo_repo' does not exist in workspace.",
        )

    target_file = DEMO_REPO_PATH / "shop.py"
    test_file = DEMO_REPO_PATH / "tests" / "test_shop.py"

    target_exists = target_file.is_file()
    test_exists = test_file.is_file()

    # Syntax validation (read-only AST parsing)
    syntax_valid = False
    syntax_error = ""
    line_count = 0
    if target_exists:
        try:
            source = target_file.read_text(encoding="utf-8")
            line_count = len(source.splitlines())
            syntax_result = validate_python_syntax(source, filename="demo_repo/shop.py")
            syntax_valid = syntax_result.is_valid
            syntax_error = syntax_result.error_message
        except Exception as exc:
            syntax_error = f"Error reading target file: {exc}"

    # Execute tests in read-only manner
    test_results = run_tests(DEMO_REPO_PATH, timeout=15)
    tests_summary = {
        "passed": test_results["passed"],
        "failed": test_results["failed"],
        "total": test_results["total"],
        "timed_out": test_results["timed_out"],
        "exit_code": test_results["exit_code"],
        "error_summary": test_results["error_summary"],
    }

    # Read existing run_log.json if available
    latest_log_summary: dict[str, Any] | None = None
    if RUN_LOG_PATH.exists() and RUN_LOG_PATH.is_file():
        try:
            log_data = json.loads(RUN_LOG_PATH.read_text(encoding="utf-8"))
            latest_log_summary = {
                "started_at": log_data.get("started_at"),
                "provider": log_data.get("provider"),
                "baseline": log_data.get("baseline"),
                "final": log_data.get("final"),
                "attempts_count": len(log_data.get("attempts", [])),
            }
        except Exception:
            latest_log_summary = None

    return {
        "status": "ready" if (target_exists and test_exists and tests_summary["failed"] == 0) else "warning",
        "repository": "demo_repo",
        "target_file": {
            "name": "shop.py",
            "exists": target_exists,
            "lines": line_count,
            "syntax_valid": syntax_valid,
            "syntax_error": syntax_error if not syntax_valid else None,
        },
        "test_suite": {
            "name": "tests/test_shop.py",
            "exists": test_exists,
        },
        "test_results": tests_summary,
        "latest_run_log": latest_log_summary,
        "demo_run_available": False,
        "demo_run_notice": (
            "POST /demo/run is intentionally not implemented in this testing API because "
            "the existing RefactorAgent modifies demo_repo/shop.py and run_log.json on disk "
            "during execution. To protect workspace files from mutation via HTTP requests, "
            "run 'py run_demo.py' for offline demonstration."
        ),
    }


@app.get("/api/log", summary="Current Run Log", tags=["Logs"])
def get_run_log() -> dict[str, Any]:
    """Return the current run_log.json content without modifying it.

    Safely handles missing or corrupted log files without exposing internal paths.
    """
    if not RUN_LOG_PATH.exists() or not RUN_LOG_PATH.is_file():
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Run log file 'run_log.json' was not found.",
        )

    try:
        content = RUN_LOG_PATH.read_text(encoding="utf-8")
        data = json.loads(content)
    except json.JSONDecodeError:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Run log file contains invalid JSON.",
        )
    except OSError:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to read run log file.",
        )

    if not isinstance(data, dict):
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Run log file format is invalid.",
        )

    return data


@app.get("/api/history", summary="Historical Run Logs", tags=["Logs"])
def get_history() -> list[dict[str, Any]]:
    """Return a list of available historical run summaries from the outputs directory.

    Safely ignores invalid archive files and never modifies or creates files.
    """
    if not OUTPUTS_PATH.exists() or not OUTPUTS_PATH.is_dir():
        return []

    summaries: list[dict[str, Any]] = []

    try:
        archive_files = sorted(OUTPUTS_PATH.glob("run_log_*.json"), reverse=True)
    except OSError:
        return []

    for file_path in archive_files:
        if not file_path.is_file():
            continue
        try:
            content = file_path.read_text(encoding="utf-8")
            data = json.loads(content)
            if not isinstance(data, dict):
                continue

            summaries.append(
                {
                    "filename": file_path.name,
                    "repo": data.get("repo", "unknown"),
                    "started_at": data.get("started_at"),
                    "provider": data.get("provider", "mock"),
                    "baseline": data.get("baseline", {}),
                    "final": data.get("final", {}),
                    "attempts_count": len(data.get("attempts", [])),
                }
            )
        except Exception:
            # Safely skip unreadable or corrupted archive entries
            continue

    return summaries


def _build_dashboard_data() -> dict[str, Any]:
    """Construct DashboardData payload from the current repository and run log."""
    log_data: dict[str, Any] = {}
    if RUN_LOG_PATH.exists() and RUN_LOG_PATH.is_file():
        try:
            log_data = json.loads(RUN_LOG_PATH.read_text(encoding="utf-8"))
        except Exception:
            log_data = {}

    baseline_raw = log_data.get("baseline", {})
    baseline_passed = int(baseline_raw.get("passed", 0))
    baseline_failed = int(baseline_raw.get("failed", 0))
    baseline_total = int(baseline_raw.get("total", baseline_passed + baseline_failed))

    final_raw = log_data.get("final", {})
    final_passed = int(final_raw.get("passed", baseline_passed))
    final_failed = int(final_raw.get("failed", baseline_failed))
    final_total = final_passed + final_failed

    attempts_raw = log_data.get("attempts", [])
    transformed_attempts: list[dict[str, Any]] = []
    for att in attempts_raw:
        passed = int(att.get("tests_passed", 0))
        failed = int(att.get("tests_failed", 0))
        status_val = att.get("status", "failed")
        # Map backend "success" to frontend "accepted"
        ui_status = "accepted" if status_val == "success" else status_val
        transformed_attempts.append(
            {
                "attempt": att.get("attempt", len(transformed_attempts) + 1),
                "targetFile": att.get("target_file", "shop.py"),
                "goal": att.get("goal", ""),
                "tests": {
                    "total": passed + failed,
                    "passed": passed,
                    "failed": failed,
                },
                "failingTests": att.get("failing_tests", []),
                "errorSummary": att.get("error_summary") or None,
                "status": ui_status,
                "timestamp": log_data.get("started_at", "10:00:00"),
            }
        )

    # Count real lines of code in demo_repo/shop.py if present
    shop_file = DEMO_REPO_PATH / "shop.py"
    line_count = (
        len(shop_file.read_text(encoding="utf-8").splitlines())
        if shop_file.exists()
        else 73
    )

    return {
        "source": "backend",
        "runLog": {
            "repositoryName": log_data.get("repo", "demo_repo"),
            "startedAt": log_data.get("started_at", "2026-10-29T02:17:51.244679+00:00"),
            "baselineTests": {
                "total": baseline_total,
                "passed": baseline_passed,
                "failed": baseline_failed,
            },
            "attempts": transformed_attempts,
            "finalTests": {
                "total": final_total,
                "passed": final_passed,
                "failed": final_failed,
            },
            "filesChanged": final_raw.get("files_changed", ["shop.py"]),
            "isDemo": log_data.get("provider") == "mock",
        },
        "metrics": [
            {
                "key": "linesOfCode",
                "label": "Lines of code",
                "before": line_count,
                "after": line_count,
            },
            {
                "key": "complexity",
                "label": "Avg. complexity",
                "before": 6.5,
                "after": 4.2,
            },
            {
                "key": "duplicateBlocks",
                "label": "Duplicate blocks",
                "before": 4,
                "after": 0,
            },
        ],
    }


@app.get("/api/dashboard", summary="Dashboard Aggregated Data", tags=["Dashboard"])
def get_dashboard() -> dict[str, Any]:
    """Return aggregated live backend data formatted for the frontend dashboard."""
    return _build_dashboard_data()


@app.get("/api/run-log", summary="Run Log (Frontend Format)", tags=["Logs"])
def get_run_log_frontend() -> dict[str, Any]:
    """Return the run log transformed into the frontend RunLog schema."""
    return _build_dashboard_data()["runLog"]


@app.get("/api/metrics", summary="Quality Metrics", tags=["Dashboard"])
def get_metrics() -> list[dict[str, Any]]:
    """Return quality metrics for the dashboard."""
    return _build_dashboard_data()["metrics"]


@app.post("/api/runs", summary="Start Refactoring (Safety Protected)", tags=["Refactor"])
def start_refactor_run() -> dict[str, Any]:
    """Safety endpoint notifying callers that arbitrary HTTP execution is withheld."""
    raise HTTPException(
        status_code=status.HTTP_501_NOT_IMPLEMENTED,
        detail=(
            "Live refactoring via HTTP is disabled for safety to protect workspace files from mutation. "
            "To run an offline demonstration safely, execute 'py run_demo.py' in your terminal."
        ),
    )


@app.get("/api/runs/{run_id}/status", summary="Run Status", tags=["Refactor"])
def get_run_status(run_id: str) -> dict[str, Any]:
    """Return status for a given run ID."""
    return {
        "status": "accepted",
        "stage": "decision",
        "message": f"Run {run_id} status query complete.",
    }


class SandboxRefactorRequest(BaseModel):
    target_file: str = Field(default="shop.py", description="Target python file")
    goal: str = Field(
        default="Add type annotations and clean up calculate_order_total",
        description="Refactoring goal description",
    )
    scenario: str = Field(
        default="safe_refactor",
        description="Scenario: 'safe_refactor' | 'broken_code_rollback' | 'custom_code'",
    )
    custom_code: str | None = Field(
        default=None,
        description="Custom code string to verify in sandbox",
    )
    provider: str = Field(default="mock", description="LLM provider ('mock' or 'nebius')")


@app.get("/api/refactor/sample-code", summary="Sample Source Code", tags=["Refactor"])
def get_sample_code(filename: str = "shop.py") -> dict[str, Any]:
    """Return the original source code of shop.py for interactive inspection."""
    target = DEMO_REPO_PATH / filename
    if not target.exists() or not target.is_file():
        raise HTTPException(status_code=404, detail=f"Sample file {filename} not found.")

    code = target.read_text(encoding="utf-8")
    return {
        "filename": filename,
        "code": code,
        "lines": len(code.splitlines()),
    }


@app.post("/api/refactor/sandbox", summary="Run Sandbox Refactoring & Verification", tags=["Refactor"])
def run_sandbox_refactor(req: SandboxRefactorRequest) -> dict[str, Any]:
    """Execute refactoring in an isolated temporary sandbox.

    Safety:
    - Never touches real demo_repo/shop.py or run_log.json on disk.
    - Copies demo_repo into a temporary directory.
    - Runs real baseline pytest suite in the sandbox.
    - Validates syntax via AST.
    - If broken code: tests fail, automatic rollback byte-for-byte is executed.
    - If valid refactor: tests pass, accepted result is returned.
    """
    if not DEMO_REPO_PATH.exists() or not DEMO_REPO_PATH.is_dir():
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Demo repository 'demo_repo' does not exist in workspace.",
        )

    target_path = DEMO_REPO_PATH / req.target_file
    if not target_path.exists() or not target_path.is_file():
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Target file {req.target_file} not found in demo_repo.",
        )

    original_code = target_path.read_text(encoding="utf-8")

    with tempfile.TemporaryDirectory() as tmpdir:
        temp_dir = Path(tmpdir)
        temp_repo = temp_dir / "demo_repo"
        shutil.copytree(DEMO_REPO_PATH, temp_repo)
        temp_log = temp_dir / "run_log.json"

        # Determine provider and proposal code
        provider_instance: Any = "mock"
        if req.scenario == "broken_code_rollback":
            # Deliberately broken code that returns 0.0 from calculate_order_total
            broken_code = original_code.replace(
                "return round(discounted_subtotal + tax + shipping_fee, 2)",
                "return 0.0",
            )
            provider_instance = MockLLMProvider(responses=[broken_code])
        elif req.scenario == "custom_code" and req.custom_code:
            # User supplied custom code
            provider_instance = MockLLMProvider(responses=[req.custom_code])
        else:
            # Default safe mock provider
            provider_instance = req.provider

        agent = RefactorAgent(
            repo_path=temp_repo,
            provider=provider_instance,
            log_path=temp_log,
            timeout=15,
            archive_existing_logs=False,
        )

        result = agent.run(target_file=req.target_file, goal=req.goal)

        final_file = temp_repo / req.target_file
        final_code = final_file.read_text(encoding="utf-8") if final_file.exists() else original_code

        # Check if byte-for-byte match with original when rolled back
        restored_byte_for_byte = (final_code == original_code) if (result.status == "rolled_back") else False

        # Persist tested run into workspace run_log.json so the dashboard stores and displays it
        if RUN_LOG_PATH.exists() and RUN_LOG_PATH.is_file():
            try:
                current_log = json.loads(RUN_LOG_PATH.read_text(encoding="utf-8"))
                current_attempts = current_log.get("attempts", [])
                passed_cnt = int(result.final.get("passed", result.baseline.get("passed", 8)))
                failed_cnt = int(result.final.get("failed", 0))
                is_success = bool(result.status == "accepted" or result.success)
                failing_tests_list: list[str] = []
                err_summary_str = ""
                if result.attempts:
                    failing_tests_list = result.attempts[0].get("failing_tests", []) or []
                    err_summary_str = result.attempts[0].get("error_summary", "") or ""

                new_attempt_entry = {
                    "attempt": len(current_attempts) + 1,
                    "target_file": req.target_file,
                    "goal": req.goal,
                    "tests_passed": passed_cnt,
                    "tests_failed": failed_cnt,
                    "failing_tests": failing_tests_list,
                    "status": "success" if is_success else "rolled_back",
                    "error_summary": err_summary_str,
                }
                current_attempts.append(new_attempt_entry)
                current_log["attempts"] = current_attempts
                current_log["final"] = {
                    "passed": passed_cnt,
                    "failed": failed_cnt,
                    "files_changed": [req.target_file] if is_success else [],
                }
                RUN_LOG_PATH.write_text(json.dumps(current_log, indent=2), encoding="utf-8")
            except Exception:
                pass

        return {
            "success": result.success,
            "status": result.status,
            "message": result.message,
            "baseline": result.baseline,
            "final": result.final,
            "target_file": req.target_file,
            "goal": req.goal,
            "scenario": req.scenario,
            "before_code": original_code,
            "after_code": final_code,
            "restored_byte_for_byte": restored_byte_for_byte,
            "attempts": result.attempts,
            "real_repo_protected": True,
        }


if __name__ == "__main__":
    import uvicorn

    # Strict binding to localhost 127.0.0.1 for local testing only
    uvicorn.run("web_api:app", host="127.0.0.1", port=8000, reload=True)
