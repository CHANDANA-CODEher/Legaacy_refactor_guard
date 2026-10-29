"""Tests for agent/runner.py."""

from __future__ import annotations

import subprocess
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from agent.runner import extract_error_summary, parse_pytest_output, run_tests


class TestParsePytestOutput:
    """Unit tests for parse_pytest_output helper."""

    def test_mixed_passed_and_failed(self) -> None:
        raw_output = """
        ============================= test session starts =============================
        collected 4 items

        test_sample.py::test_one PASSED                                          [ 25%]
        test_sample.py::test_two PASSED                                          [ 50%]
        test_sample.py::test_three PASSED                                        [ 75%]
        test_sample.py::test_four FAILED                                         [100%]

        =================================== FAILURES ===================================
        __________________________________ test_four ___________________________________
        def test_four():
        >       assert False
        E       assert False
        =========================== short test summary info ============================
        FAILED test_sample.py::test_four - assert False
        ========================= 1 failed, 3 passed in 0.12s ==========================
        """
        result = parse_pytest_output(raw_output)
        assert result["passed"] == 3
        assert result["failed"] == 1
        assert result["total"] == 4

    def test_all_passed(self) -> None:
        raw_output = "========================= 5 passed in 0.05s =========================="
        result = parse_pytest_output(raw_output)
        assert result["passed"] == 5
        assert result["failed"] == 0
        assert result["total"] == 5

    def test_all_failed(self) -> None:
        raw_output = "========================= 2 failed in 0.02s =========================="
        result = parse_pytest_output(raw_output)
        assert result["passed"] == 0
        assert result["failed"] == 2
        assert result["total"] == 2

    def test_failed_with_errors(self) -> None:
        raw_output = "=================== 1 failed, 2 passed, 1 error in 0.10s ==================="
        result = parse_pytest_output(raw_output)
        assert result["passed"] == 2
        assert result["failed"] == 2  # 1 failed + 1 error
        assert result["total"] == 4

    def test_no_tests_ran(self) -> None:
        raw_output = "======================== no tests ran in 0.00s ========================"
        result = parse_pytest_output(raw_output)
        assert result["passed"] == 0
        assert result["failed"] == 0
        assert result["total"] == 0

    def test_empty_output(self) -> None:
        result = parse_pytest_output("")
        assert result["passed"] == 0
        assert result["failed"] == 0
        assert result["total"] == 0


class TestExtractErrorSummary:
    """Unit tests for extract_error_summary helper."""

    def test_extracts_failed_lines(self) -> None:
        raw_output = (
            "PASSED test_a.py::test_ok\n"
            "FAILED test_b.py::test_fail - AssertionError: 1 != 2\n"
            "ERROR test_c.py - ImportError: cannot import module\n"
        )
        summary = extract_error_summary(raw_output)
        assert "FAILED test_b.py::test_fail - AssertionError: 1 != 2" in summary
        assert "ERROR test_c.py - ImportError: cannot import module" in summary
        assert "PASSED" not in summary

    def test_returns_empty_when_no_errors(self) -> None:
        raw_output = "test_a.py::test_ok PASSED\n=== 1 passed in 0.01s ==="
        assert extract_error_summary(raw_output) == ""


class TestRunTestsInvalidPaths:
    """Tests for validating path handling in run_tests."""

    def test_nonexistent_directory(self, tmp_path: Path) -> None:
        nonexistent = tmp_path / "does_not_exist_folder"
        result = run_tests(nonexistent)

        assert result["timed_out"] is False
        assert result["exit_code"] is None
        assert result["passed"] == 0
        assert result["failed"] == 0
        assert result["total"] == 0
        assert "does not exist" in result["error_summary"].lower()

    def test_file_instead_of_directory(self, tmp_path: Path) -> None:
        dummy_file = tmp_path / "file.txt"
        dummy_file.write_text("hello", encoding="utf-8")
        result = run_tests(dummy_file)

        assert result["timed_out"] is False
        assert result["exit_code"] is None
        assert result["passed"] == 0
        assert result["failed"] == 0
        assert result["total"] == 0
        assert "not a directory" in result["error_summary"].lower()


class TestRunTestsSubprocessErrors:
    """Tests for error handling during subprocess execution."""

    def test_timeout_handling(self, tmp_path: Path) -> None:
        with patch("subprocess.run") as mock_run:
            mock_run.side_effect = subprocess.TimeoutExpired(
                cmd=["pytest"],
                timeout=5,
                output="running tests...",
                stderr="",
            )
            result = run_tests(tmp_path, timeout=5)

            assert result["timed_out"] is True
            assert result["exit_code"] is None
            assert result["passed"] == 0
            assert result["failed"] == 0
            assert result["total"] == 0
            assert "timed out after 5 seconds" in result["error_summary"].lower()
            assert "running tests..." in result["output"]

    def test_unexpected_os_error(self, tmp_path: Path) -> None:
        with patch("subprocess.run") as mock_run:
            mock_run.side_effect = OSError("Access denied or binary missing")
            result = run_tests(tmp_path)

            assert result["timed_out"] is False
            assert result["exit_code"] is None
            assert "Unexpected execution error" in result["error_summary"]
            assert "Access denied" in result["error_summary"]


class TestRunTestsIntegration:
    """Safe integration tests using isolated temporary directories (no project files modified)."""

    def test_passing_tests_in_temp_dir(self, tmp_path: Path) -> None:
        test_file = tmp_path / "test_example.py"
        test_file.write_text(
            "def test_success():\n    assert 1 + 1 == 2\n",
            encoding="utf-8",
        )

        result = run_tests(tmp_path, timeout=15)

        assert result["timed_out"] is False
        assert result["exit_code"] == 0
        assert result["passed"] == 1
        assert result["failed"] == 0
        assert result["total"] == 1
        assert result["error_summary"] == ""
        assert isinstance(result["output"], str)

    def test_failing_tests_in_temp_dir(self, tmp_path: Path) -> None:
        test_file = tmp_path / "test_failing.py"
        test_file.write_text(
            "def test_failure():\n    assert False, 'Deliberate test failure'\n",
            encoding="utf-8",
        )

        result = run_tests(tmp_path, timeout=15)

        assert result["timed_out"] is False
        assert result["exit_code"] != 0
        assert result["passed"] == 0
        assert result["failed"] == 1
        assert result["total"] == 1
        assert "FAILED" in result["error_summary"]
