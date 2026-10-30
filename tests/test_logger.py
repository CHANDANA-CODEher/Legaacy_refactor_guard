"""Tests for agent/logger.py."""

from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import patch

import pytest

from agent.logger import LoggerError, RunLogger


class TestRunLoggerContract:
    """Tests ensuring strict compliance with the shared backend-to-dashboard contract."""

    def test_initial_structure_matches_contract(self, tmp_path: Path) -> None:
        log_file = tmp_path / "run_log.json"
        logger = RunLogger(
            repo="demo_repo",
            provider="mock",
            log_path=log_file,
            archive_existing=False,
        )

        data = logger.to_dict()

        # 1. Exact top-level contract keys
        expected_top_keys = {"repo", "started_at", "provider", "baseline", "attempts", "final"}
        assert set(data.keys()) == expected_top_keys

        # 2. Key types and defaults
        assert data["repo"] == "demo_repo"
        assert data["provider"] == "mock"
        assert isinstance(data["started_at"], str)
        assert "T" in data["started_at"]  # ISO-8601 indicator

        # 3. Baseline structure
        assert data["baseline"] == {"passed": 0, "failed": 0, "total": 0}

        # 4. Attempts list
        assert data["attempts"] == []

        # 5. Final structure
        assert data["final"] == {"passed": 0, "failed": 0, "files_changed": []}

    def test_disk_file_is_written_atomically(self, tmp_path: Path) -> None:
        log_file = tmp_path / "run_log.json"
        RunLogger(
            repo="demo_repo",
            provider="mock",
            log_path=log_file,
            archive_existing=False,
        )

        assert log_file.exists()
        with open(log_file, "r", encoding="utf-8") as f:
            disk_data = json.load(f)

        assert disk_data["repo"] == "demo_repo"
        assert disk_data["provider"] == "mock"


class TestRecordingWorkflow:
    """Tests recording baseline, multiple attempts, and final results."""

    def test_record_baseline(self, tmp_path: Path) -> None:
        log_file = tmp_path / "run_log.json"
        logger = RunLogger(log_path=log_file, archive_existing=False)

        logger.record_baseline(passed=4, failed=1, total=5)
        saved = RunLogger.load(log_file)

        assert saved["baseline"]["passed"] == 4
        assert saved["baseline"]["failed"] == 1
        assert saved["baseline"]["total"] == 5

    def test_record_baseline_auto_calculates_total(self, tmp_path: Path) -> None:
        log_file = tmp_path / "run_log.json"
        logger = RunLogger(log_path=log_file, archive_existing=False)

        logger.record_baseline(passed=3, failed=2)
        saved = RunLogger.load(log_file)

        assert saved["baseline"]["total"] == 5

    def test_record_multiple_attempts(self, tmp_path: Path) -> None:
        log_file = tmp_path / "run_log.json"
        logger = RunLogger(log_path=log_file, archive_existing=False)

        # Attempt 1: Failed
        att1 = logger.record_attempt(
            target_file="demo_repo/shop.py",
            goal="Refactor calculate_total",
            tests_passed=2,
            tests_failed=1,
            failing_tests=["test_discount"],
            status="rolled_back",
            error_summary="AssertionError on discount calc",
        )
        assert att1["attempt"] == 1
        assert att1["status"] == "rolled_back"

        # Attempt 2: Succeeded
        att2 = logger.record_attempt(
            target_file="demo_repo/shop.py",
            goal="Refactor calculate_total cleanly",
            tests_passed=3,
            tests_failed=0,
            failing_tests=[],
            status="success",
            error_summary="",
        )
        assert att2["attempt"] == 2
        assert att2["status"] == "success"

        # Check persisted file
        saved = RunLogger.load(log_file)
        assert len(saved["attempts"]) == 2

        # Verify exact attempt field names match contract
        expected_attempt_keys = {
            "attempt",
            "target_file",
            "goal",
            "tests_passed",
            "tests_failed",
            "failing_tests",
            "status",
            "error_summary",
        }
        assert set(saved["attempts"][0].keys()) == expected_attempt_keys
        assert set(saved["attempts"][1].keys()) == expected_attempt_keys

    def test_record_final(self, tmp_path: Path) -> None:
        log_file = tmp_path / "run_log.json"
        logger = RunLogger(log_path=log_file, archive_existing=False)

        logger.record_final(passed=3, failed=0, files_changed=["demo_repo/shop.py"])
        saved = RunLogger.load(log_file)

        assert saved["final"]["passed"] == 3
        assert saved["final"]["failed"] == 0
        assert saved["final"]["files_changed"] == ["demo_repo/shop.py"]


class TestArchivingAndSafety:
    """Tests for safe archiving on new runs and input validation."""

    def test_archives_existing_run_log(self, tmp_path: Path) -> None:
        log_file = tmp_path / "run_log.json"
        archive_dir = tmp_path / "outputs"

        # 1. Create existing log from prior run
        log_file.write_text('{"repo": "prior_run"}', encoding="utf-8")

        # 2. Start a new run with archiving enabled
        RunLogger(
            repo="new_run",
            log_path=log_file,
            archive_dir=archive_dir,
            archive_existing=True,
        )

        # Check that previous log was copied to archive_dir
        archived_files = list(archive_dir.glob("run_log_*.json"))
        assert len(archived_files) == 1
        assert "prior_run" in archived_files[0].read_text(encoding="utf-8")

        # Check that new log file has the new run data
        new_data = json.loads(log_file.read_text(encoding="utf-8"))
        assert new_data["repo"] == "new_run"

    def test_archiving_failure_raises_logger_error_and_preserves_existing_log(
        self, tmp_path: Path
    ) -> None:
        log_file = tmp_path / "run_log.json"
        archive_dir = tmp_path / "outputs"

        prior_content = '{"repo": "vital_prior_run_data"}'
        log_file.write_text(prior_content, encoding="utf-8")

        # Simulate an OSError during shutil.copy2 (e.g. disk full, permission denied)
        with patch("shutil.copy2", side_effect=OSError("Disk full or permission denied")):
            with pytest.raises(LoggerError) as exc_info:
                RunLogger(
                    repo="new_run_attempt",
                    log_path=log_file,
                    archive_dir=archive_dir,
                    archive_existing=True,
                )
            assert "Failed to archive existing run log" in str(exc_info.value)

        # Confirm the original run_log.json was NOT overwritten or truncated
        assert log_file.read_text(encoding="utf-8") == prior_content

    def test_invalid_status_raises_error(self, tmp_path: Path) -> None:
        log_file = tmp_path / "run_log.json"
        logger = RunLogger(log_path=log_file, archive_existing=False)

        with pytest.raises(ValueError) as exc_info:
            logger.record_attempt(
                target_file="demo_repo/shop.py",
                goal="test",
                tests_passed=1,
                tests_failed=0,
                status="invalid_status",
            )
        assert "Invalid attempt status" in str(exc_info.value)

    def test_negative_counts_raise_error(self, tmp_path: Path) -> None:
        log_file = tmp_path / "run_log.json"
        logger = RunLogger(log_path=log_file, archive_existing=False)

        with pytest.raises(ValueError):
            logger.record_baseline(passed=-1, failed=0)

    def test_load_nonexistent_file_raises_error(self, tmp_path: Path) -> None:
        with pytest.raises(FileNotFoundError):
            RunLogger.load(tmp_path / "missing.json")

    def test_load_invalid_json_raises_logger_error(self, tmp_path: Path) -> None:
        corrupt = tmp_path / "corrupt.json"
        corrupt.write_text("{not valid json", encoding="utf-8")

        with pytest.raises(LoggerError):
            RunLogger.load(corrupt)

    def test_load_missing_required_keys_raises_logger_error(self, tmp_path: Path) -> None:
        incomplete = tmp_path / "incomplete.json"
        incomplete.write_text('{"repo": "demo"}', encoding="utf-8")

        with pytest.raises(LoggerError) as exc_info:
            RunLogger.load(incomplete)
        assert "missing required contract fields" in str(exc_info.value)
