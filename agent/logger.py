"""Structured atomic logger for Legacy Refactor Guard.

Maintains the agreed backend-to-dashboard contract in run_log.json.
Uses atomic writes (temporary file + replace) to prevent corruption.
Never logs source code, secrets, or API keys.
"""

from __future__ import annotations

import json
import os
import shutil
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


class LoggerError(Exception):
    """Base exception for all RunLogger errors."""


VALID_STATUSES = {"success", "failed", "rolled_back"}


@dataclass
class BaselineMetrics:
    """Baseline test results prior to refactoring."""

    passed: int = 0
    failed: int = 0
    total: int = 0


@dataclass
class AttemptRecord:
    """Record of a single refactoring attempt."""

    attempt: int
    target_file: str
    goal: str
    tests_passed: int
    tests_failed: int
    failing_tests: list[str] = field(default_factory=list)
    status: str = "failed"
    error_summary: str = ""

    def __post_init__(self) -> None:
        if self.status not in VALID_STATUSES:
            raise ValueError(
                f"Invalid attempt status '{self.status}'. Must be one of: {sorted(VALID_STATUSES)}"
            )


@dataclass
class FinalMetrics:
    """Final test results and list of modified files after all attempts."""

    passed: int = 0
    failed: int = 0
    files_changed: list[str] = field(default_factory=list)


def _atomic_write_json(file_path: Path, data: dict[str, Any]) -> None:
    """Write dictionary to a file atomically via a temporary file in the same directory."""
    target = file_path.resolve()
    parent_dir = target.parent
    parent_dir.mkdir(parents=True, exist_ok=True)

    temp_file = parent_dir / f"{target.name}.tmp.{os.getpid()}"
    try:
        with open(temp_file, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2)
            f.flush()
            os.fsync(f.fileno())
        os.replace(temp_file, target)
    except Exception as exc:
        if temp_file.exists():
            try:
                temp_file.unlink()
            except OSError:
                pass
        raise LoggerError(f"Failed to atomically write log to '{target}': {exc}") from exc


class RunLogger:
    """Records one complete refactoring run conforming to the dashboard contract.

    Contract format:
    {
      "repo": "demo_repo",
      "started_at": "ISO-8601 timestamp",
      "provider": "mock or nebius",
      "baseline": {
        "passed": 0,
        "failed": 0,
        "total": 0
      },
      "attempts": [
        {
          "attempt": 1,
          "target_file": "demo_repo/shop.py",
          "goal": "Simplify calculation",
          "tests_passed": 0,
          "tests_failed": 0,
          "failing_tests": [],
          "status": "success, failed, or rolled_back",
          "error_summary": ""
        }
      ],
      "final": {
        "passed": 0,
        "failed": 0,
        "files_changed": []
      }
    }

    Behavior on new run:
    When a new run begins, if an existing run_log.json is present, it is archived
    to the configured archive directory (defaulting to 'outputs/') with a timestamped
    filename so historical data is never silently erased.
    """

    def __init__(
        self,
        repo: str = "demo_repo",
        provider: str = "mock",
        log_path: str | Path = "run_log.json",
        archive_dir: str | Path | None = "outputs",
        archive_existing: bool = True,
        auto_save: bool = True,
    ) -> None:
        """Initialize a new RunLogger.

        Args:
            repo: Name or relative path of the repository being refactored.
            provider: LLM provider name ('mock' or 'nebius').
            log_path: Destination path for run_log.json.
            archive_dir: Directory where previous logs are archived if present.
            archive_existing: If True, archive any existing run_log.json before writing.
            auto_save: If True, automatically save on every record update.
        """
        if not repo or not isinstance(repo, str):
            raise ValueError("repo must be a non-empty string.")
        if not provider or not isinstance(provider, str):
            raise ValueError("provider must be a non-empty string.")

        self.repo = repo
        self.provider = provider.lower()
        self.log_path = Path(log_path).resolve()
        self.archive_dir = Path(archive_dir).resolve() if archive_dir else None
        self.auto_save = auto_save

        self.started_at = datetime.now(timezone.utc).isoformat()
        self.baseline = BaselineMetrics()
        self.attempts: list[AttemptRecord] = []
        self.final = FinalMetrics()

        # Archive existing log file if present
        if archive_existing and self.log_path.exists():
            self._archive_previous_log()

        if self.auto_save:
            self.save()

    def _archive_previous_log(self) -> None:
        """Safely copy the existing log file to the archive directory."""
        dest_dir = self.archive_dir or self.log_path.parent
        try:
            dest_dir.mkdir(parents=True, exist_ok=True)
            timestamp = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
            archive_file = dest_dir / f"run_log_{timestamp}.json"
            shutil.copy2(self.log_path, archive_file)
        except OSError as exc:
            raise LoggerError(
                f"Failed to archive existing run log '{self.log_path}' to '{dest_dir}': {exc}"
            ) from exc

    def record_baseline(self, passed: int, failed: int, total: int | None = None) -> None:
        """Record baseline test results before any refactoring attempts.

        Args:
            passed: Number of passed tests.
            failed: Number of failed tests.
            total: Optional total count (defaults to passed + failed).
        """
        if passed < 0 or failed < 0:
            raise ValueError("Test counts must be non-negative.")

        calculated_total = (passed + failed) if total is None else total
        self.baseline = BaselineMetrics(
            passed=passed,
            failed=failed,
            total=calculated_total,
        )
        if self.auto_save:
            self.save()

    def record_attempt(
        self,
        target_file: str,
        goal: str,
        tests_passed: int,
        tests_failed: int,
        status: str,
        failing_tests: list[str] | None = None,
        error_summary: str = "",
    ) -> dict[str, Any]:
        """Append a refactoring attempt record.

        Args:
            target_file: Path of the target file being modified.
            goal: The refactoring goal.
            tests_passed: Number of tests passed after the change.
            tests_failed: Number of tests failed after the change.
            status: 'success', 'failed', or 'rolled_back'.
            failing_tests: Optional list of failing test names.
            error_summary: Error details or failure diagnostics.

        Returns:
            Dictionary representation of the appended attempt.
        """
        if tests_passed < 0 or tests_failed < 0:
            raise ValueError("Test counts must be non-negative.")

        attempt_num = len(self.attempts) + 1
        record = AttemptRecord(
            attempt=attempt_num,
            target_file=target_file,
            goal=goal,
            tests_passed=tests_passed,
            tests_failed=tests_failed,
            failing_tests=list(failing_tests) if failing_tests else [],
            status=status,
            error_summary=error_summary or "",
        )
        self.attempts.append(record)

        if self.auto_save:
            self.save()

        return asdict(record)

    def record_final(
        self,
        passed: int,
        failed: int,
        files_changed: list[str] | None = None,
    ) -> None:
        """Record final test metrics and changed files at the end of the run.

        Args:
            passed: Final count of passing tests.
            failed: Final count of failing tests.
            files_changed: List of files that were modified and retained.
        """
        if passed < 0 or failed < 0:
            raise ValueError("Test counts must be non-negative.")

        self.final = FinalMetrics(
            passed=passed,
            failed=failed,
            files_changed=list(files_changed) if files_changed else [],
        )
        if self.auto_save:
            self.save()

    def to_dict(self) -> dict[str, Any]:
        """Convert current run state to the exact dashboard contract dictionary."""
        return {
            "repo": self.repo,
            "started_at": self.started_at,
            "provider": self.provider,
            "baseline": asdict(self.baseline),
            "attempts": [asdict(att) for att in self.attempts],
            "final": asdict(self.final),
        }

    def save(self) -> Path:
        """Atomically persist run log to disk.

        Returns:
            Path to the saved log file.
        """
        data = self.to_dict()
        _atomic_write_json(self.log_path, data)
        return self.log_path

    @classmethod
    def load(cls, path: str | Path) -> dict[str, Any]:
        """Load and validate an existing run_log.json file.

        Args:
            path: Path to the log file.

        Returns:
            The parsed dictionary.

        Raises:
            FileNotFoundError: If the log file does not exist.
            LoggerError: If the file is not valid JSON or violates schema.
        """
        target = Path(path).resolve()
        if not target.exists():
            raise FileNotFoundError(f"Log file does not exist: {target}")

        try:
            with open(target, "r", encoding="utf-8") as f:
                data = json.load(f)
        except Exception as exc:
            raise LoggerError(f"Failed to parse JSON from '{target}': {exc}") from exc

        # Contract schema validation
        required_keys = {"repo", "started_at", "provider", "baseline", "attempts", "final"}
        if not required_keys.issubset(data.keys()):
            missing = required_keys - set(data.keys())
            raise LoggerError(f"Log file is missing required contract fields: {missing}")

        return data
