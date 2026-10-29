# Legacy Refactor Guard (Backend)

An autonomous, safety-first Python refactoring agent designed to refactor legacy code without breaking existing functionality.

Legacy Refactor Guard enforces a strict safety lifecycle: it validates baseline test integrity, protects test files and directory boundaries, validates Python syntax using AST parsing before touching disk, creates safe single-file snapshots, and automatically rolls back changes if post-refactor tests fail.

---

## Table of Contents

1. [Overview & Purpose](#overview--purpose)
2. [Safety Guarantees](#safety-guarantees)
3. [Architecture & Module Responsibilities](#architecture--module-responsibilities)
4. [Project Folder Structure](#project-folder-structure)
5. [Environment Setup on Windows](#environment-setup-on-windows)
6. [Running Tests](#running-tests)
7. [Running the Demonstration](#running-the-demonstration)
8. [Refactoring & Rollback Lifecycle](#refactoring--rollback-lifecycle)
9. [LLM Providers & Mock Configuration](#llm-providers--mock-configuration)
10. [Dashboard Contract: run_log.json](#dashboard-contract-run_logjson)
11. [Current Limitations & Unverified Functionality](#current-limitations--unverified-functionality)

---

## Overview & Purpose

Refactoring legacy Python code manually or with unconstrained AI assistants poses high risks: models can hallucinate syntax errors, alter unit tests to pass broken code, traverse directories, or break edge-case business logic.

**Legacy Refactor Guard** solves this by wrapping code generation in a strict, deterministic test harness:
- **Zero test tampering:** Test files cannot be targeted or modified.
- **Fail-early baseline gating:** Refactoring halts immediately if existing tests already fail.
- **Pre-write AST syntax validation:** Generated code is parsed into an Abstract Syntax Tree without executing it. Syntax errors are rejected before touching disk.
- **Atomic, non-destructive rollback:** If any test fails after refactoring, the target file is immediately restored from its in-memory snapshot. Destructive Git commands (`git reset --hard`, `git clean`) are never used.
- **Standardized logging contract:** Every attempt, metric, and rollback is recorded atomically in `run_log.json` for consumption by external dashboards.

---

## Safety Guarantees

| Protection Rule | Implementation Mechanism |
| :--- | :--- |
| **No Test Modification** | `agent.guard.is_test_file` blocks any file starting with `test_`, ending in `_test.py`, named `conftest.py`, or located in a `test/` or `tests/` folder. |
| **No Directory Traversal** | `agent.guard.validate_target_path` resolves paths strictly against the repository root and rejects `../` traversal or escaping symlinks. |
| **No Arbitrary Execution** | Python syntax is verified using `ast.parse`. Code is never `eval`'d, `exec`'d, or imported during syntax validation. |
| **Isolated Rollback** | Single-file snapshots (`agent.guard.FileSnapshot`) store the original file contents before modification and restore only that exact file upon failure. |
| **Subprocess Test Isolation** | Pytest executes via `subprocess.run(sys.executable, "-m", "pytest", shell=False)` with strict timeouts to prevent hangs. |
| **Atomic Reporting** | `agent.logger._atomic_write_json` writes logs to a `.tmp` file and replaces the destination atomically via `os.replace`. |

---

## Architecture & Module Responsibilities

The backend is composed of five core modules under `agent/`:

```
agent/
├── agent.py     # High-level orchestrator (RefactorAgent & refactor_repository)
├── guard.py     # Path security, AST syntax validation, snapshot & restore
├── runner.py    # Pytest execution in subprocess, timeout enforcement, output parsing
├── llm.py       # LLM provider interface, MockLLMProvider, NebiusLLMProvider
└── logger.py    # Standardized run_log.json writer with atomic persistence & archiving
```

### Module Breakdown

- **`agent/agent.py`**
  - **`RefactorAgent`**: Primary controller orchestrating the entire lifecycle.
  - **`refactor_repository()`**: Functional entry point for programmatic execution.
  - Controls baseline checks, path validation, LLM invocation, AST checks, snapshot application, test verification, rollback, and logging.

- **`agent/guard.py`**
  - **`validate_target_path(repo_dir, target_path)`**: Ensures target paths are `.py` files inside the repository and not protected test files.
  - **`validate_python_syntax(code)`**: Parses code via `ast.parse` without execution.
  - **`create_snapshot(repo_dir, target_path)`**: Captures original file contents into a `FileSnapshot`.
  - **`restore_snapshot(snapshot)`**: Restores original contents safely to disk.
  - **`safe_apply_code(repo_dir, target_path, new_code)`**: Validates syntax, snapshots existing code, and writes updates safely.

- **`agent/runner.py`**
  - **`run_tests(repo_path, timeout, extra_args)`**: Runs pytest in the target repository using the active Python executable with a strict timeout.
  - **`parse_pytest_output(output)`**: Extracts passed, failed, and total test counts from pytest stdout/stderr.
  - **`extract_error_summary(output)`**: Extracts failure lines (`FAILED`, `ERROR`, or tracebacks) for concise feedback.

- **`agent/llm.py`**
  - **`LLMProvider`**: Abstract base class defining `refactor(source_code, goal, test_feedback)`.
  - **`MockLLMProvider`**: Deterministic offline provider for testing and demos. Supports queued scripted responses or simulated banner injection.
  - **`NebiusLLMProvider`**: OpenAI-compatible client connecting to Nebius Token Factory (`/chat/completions`). Masks API keys in representations and handles timeouts and network exceptions.
  - **`get_llm_provider(provider_type)`**: Factory function defaulting to the `LLM_PROVIDER` environment variable (defaults to `"mock"`).

- **`agent/logger.py`**
  - **`RunLogger`**: Maintains state conforming strictly to the frontend dashboard contract.
  - **`_archive_previous_log()`**: Automatically archives prior `run_log.json` files to `outputs/` with UTC timestamps.
  - **`_atomic_write_json()`**: Persists logs using atomic replacement to prevent corrupted or partial reads.

---

## Project Folder Structure

```
legacy refactor/
├── .env.example              # Environment configuration template
├── .gitignore                # Git ignore patterns
├── requirements.txt          # Python dependencies
├── run_demo.py               # End-to-end demonstration script
├── run_log.json              # Standardized output log from the latest run
├── README.md                 # Project documentation
│
├── agent/                    # Core backend package
│   ├── __init__.py
│   ├── agent.py              # Refactoring orchestrator
│   ├── guard.py              # Security & rollback guard
│   ├── runner.py             # Subprocess test runner
│   ├── llm.py                # LLM provider abstraction & implementations
│   └── logger.py             # Atomic run logger adhering to dashboard contract
│
├── demo_repo/                # Isolated sample repository for testing
│   ├── shop.py               # E-commerce calculation module
│   └── tests/
│       └── test_shop.py      # 8 comprehensive unit tests for shop.py
│
├── outputs/                  # Archive directory for previous run logs
│
└── tests/                    # Complete backend unit & integration test suite
    ├── test_agent.py         # 9 tests for RefactorAgent workflow
    ├── test_guard.py         # 24 tests for path safety, AST validation & snapshots
    ├── test_llm.py           # 26 tests for mock & Nebius providers
    ├── test_logger.py        # 13 tests for contract schema, atomic writes & archiving
    └── test_runner.py        # 14 tests for pytest subprocess execution & parsing
```

---

## Environment Setup on Windows

### 1. Prerequisites
- Windows OS
- Python 3.10+ (tested on Python 3.13 via the Windows `py` launcher)
- PowerShell or Command Prompt

### 2. Create and Activate Virtual Environment

Using PowerShell:
```powershell
# Create virtual environment
py -m venv .venv

# Activate virtual environment
.\.venv\Scripts\Activate.ps1
```

Using Command Prompt:
```cmd
py -m venv .venv
.venv\Scripts\activate.bat
```

### 3. Install Dependencies

```powershell
py -m pip install --upgrade pip
py -m pip install -r requirements.txt
```

### 4. Configuration (Optional)

Copy `.env.example` to `.env` to customize settings:
```powershell
Copy-Item .env.example .env
```

Default settings in `.env.example`:
```ini
LLM_PROVIDER=mock
TEST_TIMEOUT_SECONDS=10
NEBIUS_BASE_URL=https://api.studio.nebius.ai/v1
NEBIUS_MODEL=meta-llama/Meta-Llama-3.1-70B-Instruct
NEBIUS_API_KEY=your_nebius_api_key_here
```

---

## Running Tests

The test suite contains **94 automated tests** covering core backend safety checks and the demo repository:

### Run All Tests
```powershell
py -m pytest -v
```

### Run Backend Module Tests Only
```powershell
py -m pytest tests/ -v
```

### Run Demo Repository Tests Only
```powershell
py -m pytest demo_repo/tests/ -v
```

### Test Suite Summary

- **`tests/test_guard.py` (24 tests):** Validates AST parsing, rejection of syntax errors, protection against test-file tampering, parent directory traversal (`../`), symlink escapes, and snapshot/restore cycles.
- **`tests/test_llm.py` (26 tests):** Validates mock determinism, scripted responses, code fence extraction, Nebius payload formatting, timeout handling, and malformed response recovery.
- **`tests/test_runner.py` (14 tests):** Validates subprocess pytest execution, output parsing, exit code handling, and timeout containment.
- **`tests/test_logger.py` (13 tests):** Validates dashboard JSON contract compliance, atomic writes, archive preservation, and schema validation.
- **`tests/test_agent.py` (9 tests):** Validates end-to-end refactoring workflows, baseline failure abortion, rollback on test failure, and target file security.
- **`demo_repo/tests/test_shop.py` (8 tests):** Validates discount tiers, coupon codes, shipping fees, tax rates, and edge cases.

---

## Running the Demonstration

An end-to-end demonstration script is included in `run_demo.py`. It runs `RefactorAgent` on `demo_repo/shop.py` using `MockLLMProvider` configured with a clean, type-annotated refactoring:

```powershell
py run_demo.py
```

### What Happens During the Demo:
1. Baseline tests are executed on `demo_repo/` (8 tests pass).
2. `MockLLMProvider` returns a refactored version of `calculate_order_total` with type annotations, named constants, and clean structure.
3. `agent.guard` validates Python syntax via `ast.parse`.
4. A snapshot of `demo_repo/shop.py` is saved.
5. The refactored code is written to `demo_repo/shop.py`.
6. Pytest runs again on `demo_repo/` (all 8 tests pass).
7. The change is kept, and `run_log.json` is updated atomically.

---

## Running the Local Testing Web API

A minimal browser-accessible testing API is available in `web_api.py` to inspect the backend and demo repository in Chrome using Swagger UI (`/docs`).

### Start the API Server (PowerShell)
```powershell
py -m uvicorn web_api:app --host 127.0.0.1 --port 8000 --reload
```

Open Chrome and navigate to:
**http://127.0.0.1:8000/docs**

### Available Endpoints
- **`GET /health`**: Verifies that the API service is active and confirms binding to `127.0.0.1`.
- **`GET /demo/status`**: Performs safe, read-only inspection of `demo_repo` (file existence, AST syntax check, and test verification) without mutating any files on disk.
- **`GET /docs`**: Interactive Swagger UI testing console.

> **Safety Notice:** Bound strictly to `127.0.0.1` (never `0.0.0.0`). The API does not accept arbitrary file paths or source code. `POST /demo/run` is intentionally not implemented to protect workspace files from mutation via HTTP requests.

---

## Refactoring & Rollback Lifecycle

The following flowchart illustrates the exact sequence executed by `RefactorAgent.run()`:

```
[Start Run]
     │
     ▼
[1. Run Baseline Tests] ───────► (Tests Fail / Timeout?)
     │                                      │
     │ (Passed)                             ▼ YES
     │                        [Abort Run: Status 'baseline_failed']
     ▼                        [Target file left untouched]
[2. Validate Target Path]
     │
     ├── Target is a test file? ──────────► [Abort: ProtectedFileError]
     ├── Target escapes repo root (../)? ─► [Abort: PathSecurityError]
     └── Target is not .py? ──────────────► [Abort: PathSecurityError]
     │
     │ (Valid)
     ▼
[3. Request Proposal from LLM]
     │
     ▼
[4. AST Syntax Validation] ────► (Syntax Error?)
     │                                      │
     │ (Valid Syntax)                       ▼ YES
     │                        [Record Attempt: Status 'failed']
     │                        [Target file left untouched]
     ▼
[5. Create Snapshot of Target]
     │
     ▼
[6. Write Refactored Code]
     │
     ▼
[7. Run Post-Refactor Tests] ──► (Any Test Fails / Timeout?)
     │                                      │
     │ (All Passed)                         ▼ YES
     ▼                                [8. AUTOMATIC ROLLBACK]
[Refactor Succeeded]                  [Restore target from snapshot]
[Status: 'success']                   [Re-verify baseline tests]
[Target modification kept]            [Record Attempt: Status 'rolled_back']
     │                                      │
     └───────────────────┬──────────────────┘
                         ▼
             [9. Atomic Log Update]
             [Write to run_log.json]
```

---

## LLM Providers & Mock Configuration

### 1. `MockLLMProvider` (Default & Offline)

Designed for offline development, automated testing, and CI environments without network access.

- **Deterministic:** Returns pre-configured responses or adds an explicit mock banner.
- **Transparent:** Sets `is_mock=True` on every response and prefixes generated comments:
  ```python
  # [MOCK REFACTOR - LOCAL SIMULATION ONLY]
  # Notice: Generated by MockLLMProvider for offline testing.
  # This was NOT generated by a real Nebius AI model.
  ```
- **Scriptable:** Accepts a list of responses via `MockLLMProvider(responses=[code1, code2])` to simulate multi-step attempts or failure scenarios.
- **Limitation:** Mock mode does not perform dynamic AI reasoning or evaluate logic improvements on arbitrary code.

### 2. `NebiusLLMProvider` (Configured Endpoint)

Integrates with the Nebius Token Factory API using an OpenAI-compatible `/chat/completions` schema:

```python
from agent.llm import NebiusLLMProvider

provider = NebiusLLMProvider(
    api_key="your_api_key",
    base_url="https://api.studio.nebius.ai/v1",
    model="meta-llama/Meta-Llama-3.1-70B-Instruct",
    timeout=30.0,
)
```

- **Security:** Masks the API key in object representations (`api_key='sk-1...abcd'`).
- **Resilience:** Traps HTTP timeouts, connection errors, and malformed JSON payloads, raising structured `LLMAPIError` or `MalformedResponseError` without crashing the agent.
- **Code Extraction:** Extracts Python source from markdown code blocks (` ```python ... ``` `).

---

## Dashboard Contract: run_log.json

Every run produces a standardized JSON record at the root of the project (`run_log.json`). This file serves as the strict contract between the backend and external monitoring dashboards.

### Schema Specification

```json
{
  "repo": "demo_repo",
  "started_at": "2026-10-28T15:59:39.687988+00:00",
  "provider": "mock",
  "baseline": {
    "passed": 8,
    "failed": 0,
    "total": 8
  },
  "attempts": [
    {
      "attempt": 1,
      "target_file": "shop.py",
      "goal": "Refactor calculate_order_total with type hints and constants",
      "tests_passed": 8,
      "tests_failed": 0,
      "failing_tests": [],
      "status": "success",
      "error_summary": ""
    }
  ],
  "final": {
    "passed": 8,
    "failed": 0,
    "files_changed": [
      "shop.py"
    ]
  }
}
```

### Permitted Status Values for Attempts
- `"success"`: The refactored code passed all tests and was retained.
- `"failed"`: The attempt failed before applying changes (e.g., syntax error, LLM failure).
- `"rolled_back"`: The refactored code caused post-refactor tests to fail, and the original target file was restored from snapshot.

### Safe Archiving
When a new `RunLogger` instance is created, any existing `run_log.json` is safely archived into `outputs/run_log_<YYYYMMDD_HHMMSS>.json` before the new log is initialized.

---

## Current Limitations & Unverified Functionality

To maintain transparency and engineering integrity:

1. **Nebius Live API Calls Unverified:**
   While `NebiusLLMProvider` is fully implemented and covered by 14 mocked network and error-handling tests, live requests against Nebius Token Factory have **not** been tested with real API credentials in this environment.
2. **Mock Mode Is Not AI:**
   `MockLLMProvider` is an offline deterministic simulator for development and testing. It does not perform semantic code analysis or AI reasoning.
3. **Single-File Refactoring Scope:**
   `RefactorAgent` currently targets one Python file per run. Multi-file refactoring dependencies across packages are not supported in the current backend release.
4. **Backend-Only Repository:**
   This codebase contains only the refactoring agent backend, safety guards, and CLI/demo entrypoints. Frontend visualizations and dashboard components are maintained separately.
5. **Filesystem-Based Rollback:**
   Rollbacks restore individual file contents from snapshots in memory. They do not interact with Git branches, commits, or stashes.
