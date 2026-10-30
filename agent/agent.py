"""Autonomous refactoring agent module for Legacy Refactor Guard.

Coordinates the complete safe refactoring workflow:
1. Runs baseline tests before making any changes.
2. Stops immediately if baseline tests fail.
3. Validates target paths and protects test files.
4. Generates refactored proposals via configured LLM provider.
5. Validates syntax via AST before touching any file.
6. Creates controlled snapshots and applies code safely.
7. Re-runs tests to verify functionality.
8. Rolls back unsuccessful attempts and preserves original contents.
9. Records every run and attempt atomically in run_log.json.
"""

from __future__ import annotations

import os
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any

from agent.guard import (
    FileSnapshot,
    GuardError,
    PathSecurityError,
    ProtectedFileError,
    SyntaxValidationError,
    restore_snapshot,
    safe_apply_code,
    validate_python_syntax,
    validate_target_path,
)
from agent.llm import LLMError, LLMProvider, get_llm_provider
from agent.logger import RunLogger
from agent.runner import run_tests


@dataclass
class RefactorResult:
    """Outcome of an agent refactoring run."""

    success: bool
    status: str
    message: str
    baseline: dict[str, int]
    final: dict[str, Any]
    attempts: list[dict[str, Any]] = field(default_factory=list)
    files_changed: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        """Convert result to dictionary representation."""
        return asdict(self)


class RefactorAgent:
    """Orchestrates safe, test-guarded Python refactoring."""

    def __init__(
        self,
        repo_path: str | Path,
        provider: LLMProvider | str | None = None,
        log_path: str | Path = "run_log.json",
        timeout: int | None = None,
        archive_existing_logs: bool = True,
    ) -> None:
        """Initialize RefactorAgent.

        Args:
            repo_path: Root directory of the repository to refactor.
            provider: LLMProvider instance, provider name ('mock' or 'nebius'),
                     or None to use environment default.
            log_path: Destination for dashboard run_log.json.
            timeout: Test execution timeout in seconds.
            archive_existing_logs: Whether to archive prior run_log.json if present.
        """
        self.repo_path = Path(repo_path).resolve()
        if not self.repo_path.exists() or not self.repo_path.is_dir():
            raise FileNotFoundError(f"Repository directory does not exist: {self.repo_path}")

        # Resolve LLM provider
        if hasattr(provider, "refactor"):
            self.llm = provider
        elif isinstance(provider, str):
            self.llm = get_llm_provider(provider)
        else:
            self.llm = get_llm_provider()

        # Enforce timeout configuration
        if timeout is not None:
            self.timeout = int(timeout)
        else:
            self.timeout = int(os.getenv("TEST_TIMEOUT_SECONDS", "30"))

        # Initialize RunLogger
        repo_name = self.repo_path.name or "repo"
        raw_provider_name = getattr(self.llm, "name", "mock")
        provider_name = raw_provider_name if isinstance(raw_provider_name, str) and raw_provider_name else "mock"

        self.logger = RunLogger(
            repo=repo_name,
            provider=provider_name,
            log_path=log_path,
            archive_existing=archive_existing_logs,
        )

    def run(self, target_file: str | Path, goal: str) -> RefactorResult:
        """Execute a guarded refactoring workflow on the specified target file.

        Args:
            target_file: Relative or absolute path to the Python file to refactor.
            goal: Plain-text description of the refactoring goal.

        Returns:
            RefactorResult describing the final outcome.
        """
        target_display = str(target_file).replace("\\", "/")

        # ----------------------------------------------------------------------
        # Step 1: Run Baseline Tests
        # ----------------------------------------------------------------------
        baseline_res = run_tests(self.repo_path, timeout=self.timeout)
        self.logger.record_baseline(
            passed=baseline_res["passed"],
            failed=baseline_res["failed"],
            total=baseline_res["total"],
        )

        # ----------------------------------------------------------------------
        # Step 2: Stop immediately if Baseline Tests are failing
        # ----------------------------------------------------------------------
        baseline_failed = (
            baseline_res["failed"] > 0
            or baseline_res["exit_code"] != 0
            or baseline_res["timed_out"]
        )

        if baseline_failed:
            self.logger.record_final(
                passed=baseline_res["passed"],
                failed=baseline_res["failed"],
                files_changed=[],
            )
            msg = (
                f"Baseline tests are failing ({baseline_res['failed']} failed, "
                f"exit code {baseline_res['exit_code']}). Refactoring aborted "
                f"without modifying the repository."
            )
            return RefactorResult(
                success=False,
                status="baseline_failed",
                message=msg,
                baseline=asdict(self.logger.baseline),
                final=asdict(self.logger.final),
                attempts=self.logger.to_dict()["attempts"],
                files_changed=[],
            )

        # ----------------------------------------------------------------------
        # Step 3: Validate Target File Security
        # ----------------------------------------------------------------------
        try:
            resolved_target = validate_target_path(
                self.repo_path, target_file, allow_test_files=False
            )
            if not resolved_target.exists() or not resolved_target.is_file():
                raise FileNotFoundError(f"Target file does not exist: {target_file}")
            # Format target relative to repository for consistency in logs
            try:
                target_display = str(resolved_target.relative_to(self.repo_path)).replace("\\", "/")
            except ValueError:
                target_display = str(target_file).replace("\\", "/")
        except (PathSecurityError, ProtectedFileError, FileNotFoundError) as exc:
            self.logger.record_final(
                passed=baseline_res["passed"],
                failed=baseline_res["failed"],
                files_changed=[],
            )
            return RefactorResult(
                success=False,
                status="target_validation_failed",
                message=f"Target file validation failed: {exc}",
                baseline=asdict(self.logger.baseline),
                final=asdict(self.logger.final),
                attempts=self.logger.to_dict()["attempts"],
                files_changed=[],
            )

        # Read original code
        try:
            original_code = resolved_target.read_text(encoding="utf-8")
        except OSError as exc:
            self.logger.record_final(
                passed=baseline_res["passed"],
                failed=baseline_res["failed"],
                files_changed=[],
            )
            return RefactorResult(
                success=False,
                status="read_error",
                message=f"Failed to read target file '{target_display}': {exc}",
                baseline=asdict(self.logger.baseline),
                final=asdict(self.logger.final),
                attempts=self.logger.to_dict()["attempts"],
                files_changed=[],
            )

        # ----------------------------------------------------------------------
        # Step 4: Request Refactoring from LLM Provider
        # ----------------------------------------------------------------------
        try:
            llm_response = self.llm.refactor(
                source_code=original_code,
                goal=goal,
                test_feedback=None,
            )
        except (LLMError, Exception) as exc:
            self.logger.record_attempt(
                target_file=target_display,
                goal=goal,
                tests_passed=baseline_res["passed"],
                tests_failed=baseline_res["failed"],
                status="failed",
                error_summary=f"LLM request error: {exc}",
            )
            self.logger.record_final(
                passed=baseline_res["passed"],
                failed=baseline_res["failed"],
                files_changed=[],
            )
            return RefactorResult(
                success=False,
                status="llm_failed",
                message=f"LLM refactoring proposal failed: {exc}",
                baseline=asdict(self.logger.baseline),
                final=asdict(self.logger.final),
                attempts=self.logger.to_dict()["attempts"],
                files_changed=[],
            )

        # ----------------------------------------------------------------------
        # Step 5: Validate Syntax with AST Before Modifying File
        # ----------------------------------------------------------------------
        syntax_check = validate_python_syntax(
            llm_response.code, filename=target_display
        )
        if not syntax_check.is_valid:
            self.logger.record_attempt(
                target_file=target_display,
                goal=goal,
                tests_passed=baseline_res["passed"],
                tests_failed=baseline_res["failed"],
                status="failed",
                error_summary=syntax_check.error_message,
            )
            self.logger.record_final(
                passed=baseline_res["passed"],
                failed=baseline_res["failed"],
                files_changed=[],
            )
            return RefactorResult(
                success=False,
                status="syntax_error",
                message=(
                    f"Refactoring proposal contains invalid Python syntax: "
                    f"{syntax_check.error_message}"
                ),
                baseline=asdict(self.logger.baseline),
                final=asdict(self.logger.final),
                attempts=self.logger.to_dict()["attempts"],
                files_changed=[],
            )

        # ----------------------------------------------------------------------
        # Step 6: Safe Snapshot and Code Application
        # ----------------------------------------------------------------------
        snapshot: FileSnapshot | None = None
        try:
            snapshot = safe_apply_code(self.repo_path, resolved_target, llm_response.code)
        except GuardError as exc:
            self.logger.record_attempt(
                target_file=target_display,
                goal=goal,
                tests_passed=baseline_res["passed"],
                tests_failed=baseline_res["failed"],
                status="failed",
                error_summary=f"Safe apply failed: {exc}",
            )
            self.logger.record_final(
                passed=baseline_res["passed"],
                failed=baseline_res["failed"],
                files_changed=[],
            )
            return RefactorResult(
                success=False,
                status="apply_failed",
                message=f"Failed to safely apply refactoring: {exc}",
                baseline=asdict(self.logger.baseline),
                final=asdict(self.logger.final),
                attempts=self.logger.to_dict()["attempts"],
                files_changed=[],
            )

        # ----------------------------------------------------------------------
        # Step 7: Run Tests with Refactored Code
        # ----------------------------------------------------------------------
        try:
            test_res = run_tests(self.repo_path, timeout=self.timeout)
        except Exception as exc:
            if snapshot is not None:
                restore_snapshot(snapshot)
            self.logger.record_attempt(
                target_file=target_display,
                goal=goal,
                tests_passed=0,
                tests_failed=1,
                status="rolled_back",
                error_summary=f"Test runner error: {exc}",
            )
            self.logger.record_final(
                passed=baseline_res["passed"],
                failed=baseline_res["failed"],
                files_changed=[],
            )
            return RefactorResult(
                success=False,
                status="rolled_back",
                message=f"Test execution error: {exc}. Target file was safely restored.",
                baseline=asdict(self.logger.baseline),
                final=asdict(self.logger.final),
                attempts=self.logger.to_dict()["attempts"],
                files_changed=[],
            )

        tests_passed = (
            test_res["exit_code"] == 0
            and test_res["failed"] == 0
            and not test_res["timed_out"]
        )

        # ----------------------------------------------------------------------
        # Step 8: Keep on Success, Roll Back on Failure
        # ----------------------------------------------------------------------
        if tests_passed:
            self.logger.record_attempt(
                target_file=target_display,
                goal=goal,
                tests_passed=test_res["passed"],
                tests_failed=test_res["failed"],
                status="success",
                error_summary="",
            )
            self.logger.record_final(
                passed=test_res["passed"],
                failed=test_res["failed"],
                files_changed=[target_display],
            )
            return RefactorResult(
                success=True,
                status="success",
                message="Refactoring verified and applied successfully. All tests passed.",
                baseline=asdict(self.logger.baseline),
                final=asdict(self.logger.final),
                attempts=self.logger.to_dict()["attempts"],
                files_changed=[target_display],
            )
        else:
            # Rollback: restore the original file contents
            if snapshot is not None:
                restore_snapshot(snapshot)

            # Re-verify baseline state after rollback
            post_rollback_res = run_tests(self.repo_path, timeout=self.timeout)

            self.logger.record_attempt(
                target_file=target_display,
                goal=goal,
                tests_passed=test_res["passed"],
                tests_failed=test_res["failed"],
                status="rolled_back",
                error_summary=test_res["error_summary"],
            )
            self.logger.record_final(
                passed=post_rollback_res["passed"],
                failed=post_rollback_res["failed"],
                files_changed=[],
            )

            err_info = test_res["error_summary"] or f"Exit code {test_res['exit_code']}"
            return RefactorResult(
                success=False,
                status="rolled_back",
                message=f"Post-refactor tests failed ({err_info}). Changes were rolled back.",
                baseline=asdict(self.logger.baseline),
                final=asdict(self.logger.final),
                attempts=self.logger.to_dict()["attempts"],
                files_changed=[],
            )


def refactor_repository(
    repo_path: str | Path,
    target_file: str | Path,
    goal: str,
    provider: LLMProvider | str | None = None,
    log_path: str | Path = "run_log.json",
    timeout: int | None = None,
) -> RefactorResult:
    """Convenience functional interface to execute RefactorAgent.

    Args:
        repo_path: Root directory of the repository.
        target_file: Python file to refactor.
        goal: Plain-text refactoring goal.
        provider: Provider name or instance.
        log_path: Path for run_log.json.
        timeout: Subprocess test timeout.

    Returns:
        RefactorResult with run details.
    """
    agent = RefactorAgent(
        repo_path=repo_path,
        provider=provider,
        log_path=log_path,
        timeout=timeout,
    )
    return agent.run(target_file=target_file, goal=goal)
