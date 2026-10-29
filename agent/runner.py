"""Safe test-runner module for Legacy Refactor Guard.

Executes pytest in a controlled subprocess, enforces strict timeouts,
parses test results, and returns consistent summary metrics without
modifying any repository files.
"""

from __future__ import annotations

import re
import subprocess
import sys
from pathlib import Path
from typing import Any


def parse_pytest_output(output: str) -> dict[str, int]:
    """Parse pytest stdout/stderr to extract passed, failed, and total test counts.

    Handles summary formats including:
    - '3 passed, 1 failed'
    - '5 passed in 0.02s'
    - '1 failed, 2 errors in 0.15s'
    - '= 1 failed, 2 passed ='
    - 'no tests ran in 0.00s'

    Args:
        output: Raw text output from pytest.

    Returns:
        Dictionary with 'passed', 'failed', and 'total' counts.
    """
    if not output:
        return {"passed": 0, "failed": 0, "total": 0}

    # Inspect lines from the end to find the final pytest summary line
    summary_line = ""
    for line in reversed(output.splitlines()):
        line_clean = line.strip("= ").strip()
        if (
            re.search(r"\b\d+\s+(?:passed|failed|errors?|skipped|xfailed|xpassed)\b", line_clean)
            or "no tests ran" in line_clean
        ):
            summary_line = line_clean
            break

    target = summary_line if summary_line else output

    passed_match = re.search(r"\b(\d+)\s+passed\b", target)
    failed_match = re.search(r"\b(\d+)\s+failed\b", target)
    error_match = re.search(r"\b(\d+)\s+errors?\b", target)

    passed = int(passed_match.group(1)) if passed_match else 0
    failed = int(failed_match.group(1)) if failed_match else 0
    errors = int(error_match.group(1)) if error_match else 0

    total_failures = failed + errors
    total = passed + total_failures

    return {
        "passed": passed,
        "failed": total_failures,
        "total": total,
    }


def extract_error_summary(output: str) -> str:
    """Extract concise error and failure lines from pytest output.

    Args:
        output: Raw text output from pytest.

    Returns:
        A concise multi-line summary of failed tests or errors.
    """
    if not output:
        return ""

    error_lines: list[str] = []
    for line in output.splitlines():
        line_clean = line.strip()
        if line_clean.startswith("FAILED ") or line_clean.startswith("ERROR "):
            error_lines.append(line_clean)

    if error_lines:
        return "\n".join(error_lines)

    # Fallback: look for common exception or pytest error indicators
    for line in reversed(output.splitlines()):
        line_clean = line.strip()
        if any(indicator in line_clean for indicator in ("Error:", "Exception:", "pytest: error:")):
            return line_clean

    return ""


def run_tests(
    repo_path: str | Path,
    timeout: int = 30,
    extra_args: list[str] | None = None,
) -> dict[str, Any]:
    """Execute pytest inside the target repository with a strict timeout.

    Runs pytest using the current Python interpreter via subprocess (shell=False),
    captures all output, parses test metrics, and ensures no repository files
    are modified by the runner.

    Args:
        repo_path: Path to the target repository or folder containing tests.
        timeout: Maximum execution time in seconds before terminating.
        extra_args: Optional additional command-line arguments to pass to pytest.

    Returns:
        A dictionary containing:
        - passed: Number of passing tests
        - failed: Number of failing tests (including errors)
        - total: Total number of evaluated tests
        - timed_out: True if execution timed out, otherwise False
        - exit_code: Process return code (or None if timed out / invalid path)
        - output: Combined stdout and stderr text
        - error_summary: Summary of failure or error reasons (empty if all passed)
    """
    target = Path(repo_path)

    # 1. Validate repository path
    if not target.exists():
        return {
            "passed": 0,
            "failed": 0,
            "total": 0,
            "timed_out": False,
            "exit_code": None,
            "output": "",
            "error_summary": f"Repository path does not exist: {repo_path}",
        }

    if not target.is_dir():
        return {
            "passed": 0,
            "failed": 0,
            "total": 0,
            "timed_out": False,
            "exit_code": None,
            "output": "",
            "error_summary": f"Repository path is not a directory: {repo_path}",
        }

    # 2. Build subprocess command using current Python interpreter (sys.executable)
    cmd = [sys.executable, "-m", "pytest"]
    if extra_args:
        cmd.extend(extra_args)

    # 3. Execute subprocess safely with timeout
    try:
        process = subprocess.run(
            cmd,
            cwd=str(target.resolve()),
            capture_output=True,
            text=True,
            timeout=timeout,
            shell=False,
        )
    except subprocess.TimeoutExpired as exc:
        raw_out = exc.stdout or ""
        raw_err = exc.stderr or ""
        out_str = raw_out if isinstance(raw_out, str) else raw_out.decode("utf-8", errors="replace")
        err_str = raw_err if isinstance(raw_err, str) else raw_err.decode("utf-8", errors="replace")
        combined_output = out_str + ("\n" + err_str if err_str else "")

        return {
            "passed": 0,
            "failed": 0,
            "total": 0,
            "timed_out": True,
            "exit_code": None,
            "output": combined_output,
            "error_summary": f"Test execution timed out after {timeout} seconds.",
        }
    except FileNotFoundError as exc:
        return {
            "passed": 0,
            "failed": 0,
            "total": 0,
            "timed_out": False,
            "exit_code": None,
            "output": "",
            "error_summary": f"Python executable or command not found: {exc}",
        }
    except Exception as exc:
        return {
            "passed": 0,
            "failed": 0,
            "total": 0,
            "timed_out": False,
            "exit_code": None,
            "output": "",
            "error_summary": f"Unexpected execution error: {exc}",
        }

    # 4. Process output and exit status
    stdout = process.stdout or ""
    stderr = process.stderr or ""
    combined_output = stdout + ("\n" + stderr if stderr else "")

    parsed = parse_pytest_output(combined_output)
    passed = parsed["passed"]
    failed = parsed["failed"]
    total = parsed["total"]

    # If pytest exited with a failure code but counts were 0 (e.g., collection/syntax error),
    # ensure it is marked as a failure so baseline/guard checks are not bypassed.
    if process.returncode != 0 and total == 0:
        failed = 1
        total = 1

    if process.returncode == 0:
        error_summary = ""
    else:
        error_summary = extract_error_summary(combined_output)
        if not error_summary:
            lines = [ln.strip() for ln in combined_output.splitlines() if ln.strip()]
            error_summary = lines[-1] if lines else f"pytest failed with exit code {process.returncode}"

    return {
        "passed": passed,
        "failed": failed,
        "total": total,
        "timed_out": False,
        "exit_code": process.returncode,
        "output": combined_output,
        "error_summary": error_summary,
    }
