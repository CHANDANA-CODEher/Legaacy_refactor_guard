"""Tests for agent/agent.py."""

from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from agent.agent import RefactorAgent, RefactorResult, refactor_repository
from agent.llm import LLMAPIError, MockLLMProvider


@pytest.fixture
def sample_repo(tmp_path: Path) -> Path:
    """Create a temporary repository with a working module and passing test."""
    repo = tmp_path / "demo_repo"
    repo.mkdir()

    # Target source module
    calc_file = repo / "calculator.py"
    calc_file.write_text(
        "def add(a: int, b: int) -> int:\n"
        "    return a + b\n\n"
        "def multiply(a: int, b: int) -> int:\n"
        "    return a * b\n",
        encoding="utf-8",
    )

    # Test suite
    tests_dir = repo / "tests"
    tests_dir.mkdir()
    test_file = tests_dir / "test_calculator.py"
    test_file.write_text(
        "from calculator import add, multiply\n\n"
        "def test_add():\n"
        "    assert add(2, 3) == 5\n\n"
        "def test_multiply():\n"
        "    assert multiply(3, 4) == 12\n",
        encoding="utf-8",
    )

    return repo


class TestRefactorAgentWorkflow:
    """Tests for end-to-end agent workflow execution."""

    def test_successful_refactor_keeps_changes_and_records_success(
        self, sample_repo: Path, tmp_path: Path
    ) -> None:
        log_file = tmp_path / "run_log.json"
        improved_code = (
            "def add(a: int, b: int) -> int:\n"
            "    \"\"\"Add two numbers.\"\"\"\n"
            "    return a + b\n\n"
            "def multiply(a: int, b: int) -> int:\n"
            "    \"\"\"Multiply two numbers.\"\"\"\n"
            "    return a * b\n"
        )
        mock_llm = MockLLMProvider(responses=[improved_code])

        agent = RefactorAgent(
            repo_path=sample_repo,
            provider=mock_llm,
            log_path=log_file,
            archive_existing_logs=False,
        )

        result = agent.run(target_file="calculator.py", goal="Add docstrings")

        assert result.success is True
        assert result.status == "success"
        assert result.files_changed == ["calculator.py"]
        assert result.baseline["passed"] == 2
        assert result.final["passed"] == 2

        # Verify target file has the new code
        target_content = (sample_repo / "calculator.py").read_text(encoding="utf-8")
        assert '"""Add two numbers."""' in target_content

        # Verify run_log.json matches contract
        saved_log = json.loads(log_file.read_text(encoding="utf-8"))
        assert saved_log["attempts"][0]["status"] == "success"
        assert saved_log["final"]["files_changed"] == ["calculator.py"]

    def test_baseline_failure_aborts_without_llm_call(
        self, sample_repo: Path, tmp_path: Path
    ) -> None:
        # Break test so baseline fails
        (sample_repo / "tests" / "test_calculator.py").write_text(
            "def test_broken():\n    assert False, 'Baseline failure'\n",
            encoding="utf-8",
        )

        log_file = tmp_path / "run_log.json"
        mock_llm = MagicMock()

        agent = RefactorAgent(
            repo_path=sample_repo,
            provider=mock_llm,
            log_path=log_file,
            archive_existing_logs=False,
        )

        original_content = (sample_repo / "calculator.py").read_text(encoding="utf-8")
        result = agent.run(target_file="calculator.py", goal="Simplify")

        # Must report failure, must NOT call LLM
        assert result.success is False
        assert result.status == "baseline_failed"
        assert "Baseline tests are failing" in result.message
        mock_llm.refactor.assert_not_called()

        # File on disk must NOT be modified
        assert (sample_repo / "calculator.py").read_text(encoding="utf-8") == original_content

        # Log must record baseline and empty attempts
        saved_log = json.loads(log_file.read_text(encoding="utf-8"))
        assert saved_log["baseline"]["failed"] >= 1
        assert saved_log["attempts"] == []
        assert saved_log["final"]["files_changed"] == []

    def test_invalid_generated_syntax_is_rejected_without_modifying_file(
        self, sample_repo: Path, tmp_path: Path
    ) -> None:
        log_file = tmp_path / "run_log.json"
        broken_syntax = "def broken(:\n    pass\n"
        mock_llm = MockLLMProvider(responses=[broken_syntax])

        agent = RefactorAgent(
            repo_path=sample_repo,
            provider=mock_llm,
            log_path=log_file,
            archive_existing_logs=False,
        )

        original_content = (sample_repo / "calculator.py").read_text(encoding="utf-8")
        result = agent.run(target_file="calculator.py", goal="Fix syntax")

        assert result.success is False
        assert result.status == "syntax_error"
        assert "invalid Python syntax" in result.message

        # Target file must remain untouched
        assert (sample_repo / "calculator.py").read_text(encoding="utf-8") == original_content

        # Log records failed attempt
        saved_log = json.loads(log_file.read_text(encoding="utf-8"))
        assert saved_log["attempts"][0]["status"] == "failed"
        assert "SyntaxError" in saved_log["attempts"][0]["error_summary"]

    def test_post_refactor_test_failure_causes_rollback(
        self, sample_repo: Path, tmp_path: Path
    ) -> None:
        log_file = tmp_path / "run_log.json"
        # Code that compiles but fails tests: add returns subtraction
        buggy_code = (
            "def add(a: int, b: int) -> int:\n"
            "    return a - b  # Bug!\n\n"
            "def multiply(a: int, b: int) -> int:\n"
            "    return a * b\n"
        )
        mock_llm = MockLLMProvider(responses=[buggy_code])

        agent = RefactorAgent(
            repo_path=sample_repo,
            provider=mock_llm,
            log_path=log_file,
            archive_existing_logs=False,
        )

        original_content = (sample_repo / "calculator.py").read_text(encoding="utf-8")
        result = agent.run(target_file="calculator.py", goal="Refactor math")

        assert result.success is False
        assert result.status == "rolled_back"
        assert "rolled back" in result.message

        # Verify the file was restored to original content
        restored_content = (sample_repo / "calculator.py").read_text(encoding="utf-8")
        assert restored_content == original_content

        # Verify log records rolled_back status
        saved_log = json.loads(log_file.read_text(encoding="utf-8"))
        assert saved_log["attempts"][0]["status"] == "rolled_back"
        assert saved_log["final"]["files_changed"] == []

    def test_test_file_cannot_be_selected_as_target(
        self, sample_repo: Path, tmp_path: Path
    ) -> None:
        log_file = tmp_path / "run_log.json"
        mock_llm = MockLLMProvider()

        agent = RefactorAgent(
            repo_path=sample_repo,
            provider=mock_llm,
            log_path=log_file,
            archive_existing_logs=False,
        )

        test_path = "tests/test_calculator.py"
        original_test_code = (sample_repo / test_path).read_text(encoding="utf-8")

        result = agent.run(target_file=test_path, goal="Modify tests")

        assert result.success is False
        assert result.status == "target_validation_failed"
        assert "test file and cannot be modified" in result.message

        # Test file must be completely untouched
        assert (sample_repo / test_path).read_text(encoding="utf-8") == original_test_code

    def test_path_outside_repository_is_rejected(
        self, sample_repo: Path, tmp_path: Path
    ) -> None:
        log_file = tmp_path / "run_log.json"
        mock_llm = MockLLMProvider()

        agent = RefactorAgent(
            repo_path=sample_repo,
            provider=mock_llm,
            log_path=log_file,
            archive_existing_logs=False,
        )

        result = agent.run(target_file="../outside.py", goal="Escape repo")

        assert result.success is False
        assert result.status == "target_validation_failed"
        assert "escapes repository root" in result.message

    def test_llm_failure_preserves_target_file(
        self, sample_repo: Path, tmp_path: Path
    ) -> None:
        log_file = tmp_path / "run_log.json"
        mock_llm = MagicMock()
        mock_llm.name = "nebius"
        mock_llm.refactor.side_effect = LLMAPIError("Nebius connection error")

        agent = RefactorAgent(
            repo_path=sample_repo,
            provider=mock_llm,
            log_path=log_file,
            archive_existing_logs=False,
        )

        original_content = (sample_repo / "calculator.py").read_text(encoding="utf-8")
        result = agent.run(target_file="calculator.py", goal="Refactor")

        assert result.success is False
        assert result.status == "llm_failed"
        assert "Nebius connection error" in result.message
        assert (sample_repo / "calculator.py").read_text(encoding="utf-8") == original_content

    def test_convenience_function_refactor_repository(
        self, sample_repo: Path, tmp_path: Path
    ) -> None:
        log_file = tmp_path / "run_log.json"
        mock_llm = MockLLMProvider(
            responses=[
                "def add(a: int, b: int) -> int:\n    return a + b\n\n"
                "def multiply(a: int, b: int) -> int:\n    return a * b\n"
            ]
        )

        result = refactor_repository(
            repo_path=sample_repo,
            target_file="calculator.py",
            goal="Clean up",
            provider=mock_llm,
            log_path=log_file,
        )

        assert isinstance(result, RefactorResult)
        assert result.success is True

    def test_exception_during_post_refactor_test_run_safely_rolls_back(
        self, sample_repo: Path, tmp_path: Path
    ) -> None:
        log_file = tmp_path / "run_log.json"
        mock_llm = MockLLMProvider(
            responses=[
                "def add(a: int, b: int) -> int:\n    return a + b\n\n"
                "def multiply(a: int, b: int) -> int:\n    return a * b\n"
            ]
        )

        agent = RefactorAgent(
            repo_path=sample_repo,
            provider=mock_llm,
            log_path=log_file,
            archive_existing_logs=False,
        )

        original_content = (sample_repo / "calculator.py").read_text(encoding="utf-8")

        # Simulate baseline test passing, but post-refactor test run crashing with an unexpected error
        original_run_tests = agent.run_tests if hasattr(agent, "run_tests") else None
        call_count = 0

        def flaky_run_tests(repo_path: Path, timeout: int) -> dict:
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                # Baseline passes
                return {
                    "passed": 2,
                    "failed": 0,
                    "total": 2,
                    "timed_out": False,
                    "exit_code": 0,
                    "output": "2 passed",
                    "error_summary": "",
                }
            # Post-refactor crashes unexpectedly
            raise RuntimeError("Subprocess execution harness crashed")

        with patch("agent.agent.run_tests", side_effect=flaky_run_tests):
            result = agent.run(target_file="calculator.py", goal="Test resilience")

            assert result.success is False
            assert result.status == "rolled_back"
            assert "Subprocess execution harness crashed" in result.message

            # Target file MUST have been rolled back to original content
            restored_content = (sample_repo / "calculator.py").read_text(encoding="utf-8")
            assert restored_content == original_content
