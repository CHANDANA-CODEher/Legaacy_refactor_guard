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
from pathlib import Path
from typing import Any

from fastapi import FastAPI, HTTPException, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from agent.guard import validate_python_syntax
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

ALLOWED_METHODS = ["GET", "OPTIONS", "HEAD"]
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


if __name__ == "__main__":
    import uvicorn

    # Strict binding to localhost 127.0.0.1 for local testing only
    uvicorn.run("web_api:app", host="127.0.0.1", port=8000, reload=True)
