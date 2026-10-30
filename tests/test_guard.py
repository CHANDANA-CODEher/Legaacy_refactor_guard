"""Tests for agent/guard.py."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from agent.guard import (
    FileSnapshot,
    PathSecurityError,
    ProtectedFileError,
    SyntaxValidationError,
    assert_valid_syntax,
    create_snapshot,
    is_test_file,
    restore_snapshot,
    safe_apply_code,
    validate_python_syntax,
    validate_target_path,
)


class TestSyntaxValidation:
    """Tests for validating Python syntax using AST parsing without execution."""

    def test_valid_syntax(self) -> None:
        code = """
def calculate_discount(price: float, discount: float) -> float:
    \"\"\"Calculate discounted price safely.\"\"\"
    if discount < 0 or discount > 1:
        raise ValueError("Invalid discount")
    return price * (1.0 - discount)
"""
        result = validate_python_syntax(code)
        assert result.is_valid is True
        assert result.error_message == ""
        assert result.error_line is None

    def test_empty_code_is_valid(self) -> None:
        result = validate_python_syntax("")
        assert result.is_valid is True

    def test_comments_only_is_valid(self) -> None:
        result = validate_python_syntax("# Just a comment\n# Another comment\n")
        assert result.is_valid is True

    def test_invalid_syntax_detected(self) -> None:
        broken_code = """
def broken_calc(price
    return price * 2
"""
        result = validate_python_syntax(broken_code)
        assert result.is_valid is False
        assert "SyntaxError" in result.error_message
        assert result.error_line is not None

    def test_assert_valid_syntax_raises_error(self) -> None:
        with pytest.raises(SyntaxValidationError) as exc_info:
            assert_valid_syntax("def bad(:\n    pass")
        assert "SyntaxError" in str(exc_info.value)

    def test_assert_valid_syntax_passes_on_valid_code(self) -> None:
        assert_valid_syntax("x: int = 42\n")

    def test_ast_does_not_execute_code(self) -> None:
        # Code with runtime exceptions or side effects must NOT be executed
        harmful_code = "raise RuntimeError('This should NEVER be executed!')"
        result = validate_python_syntax(harmful_code)
        # Syntactically it is valid Python statement, but never executed
        assert result.is_valid is True


class TestProtectionOfTestFiles:
    """Tests ensuring test files can never be selected as target files."""

    def test_is_test_file_identifies_test_naming_patterns(self) -> None:
        assert is_test_file(Path("test_shop.py")) is True
        assert is_test_file(Path("tests/test_shop.py")) is True
        assert is_test_file(Path("subfolder/tests/helper.py")) is True
        assert is_test_file(Path("shop_test.py")) is True
        assert is_test_file(Path("conftest.py")) is True
        assert is_test_file(Path("tests/conftest.py")) is True

        assert is_test_file(Path("shop.py")) is False
        assert is_test_file(Path("models/cart.py")) is False
        assert is_test_file(Path("services/billing.py")) is False

    def test_validate_target_path_blocks_test_files(self, tmp_path: Path) -> None:
        tests_dir = tmp_path / "tests"
        tests_dir.mkdir()
        test_file = tests_dir / "test_sample.py"
        test_file.write_text("def test_ok(): pass", encoding="utf-8")

        with pytest.raises(ProtectedFileError) as exc_info:
            validate_target_path(tmp_path, "tests/test_sample.py")
        assert "is a test file and cannot be modified" in str(exc_info.value)

    def test_validate_target_path_blocks_test_prefixed_files(self, tmp_path: Path) -> None:
        test_file = tmp_path / "test_module.py"
        test_file.write_text("def test_foo(): pass", encoding="utf-8")

        with pytest.raises(ProtectedFileError):
            validate_target_path(tmp_path, "test_module.py")

    def test_create_snapshot_blocks_test_files(self, tmp_path: Path) -> None:
        test_file = tmp_path / "test_example.py"
        test_file.write_text("def test_a(): pass", encoding="utf-8")

        with pytest.raises(ProtectedFileError):
            create_snapshot(tmp_path, "test_example.py")


class TestPathSecurity:
    """Tests for repository boundary enforcement, traversal prevention, and extension checks."""

    def test_blocks_parent_directory_traversal(self, tmp_path: Path) -> None:
        repo = tmp_path / "repo"
        repo.mkdir()
        target = "../outside.py"

        with pytest.raises(PathSecurityError) as exc_info:
            validate_target_path(repo, target)
        assert "escapes repository root" in str(exc_info.value)

    def test_blocks_nested_traversal(self, tmp_path: Path) -> None:
        repo = tmp_path / "repo"
        sub = repo / "sub"
        sub.mkdir(parents=True)
        target = "sub/../../outside.py"

        with pytest.raises(PathSecurityError):
            validate_target_path(repo, target)

    def test_blocks_non_python_files(self, tmp_path: Path) -> None:
        req_file = tmp_path / "requirements.txt"
        req_file.write_text("pytest", encoding="utf-8")

        with pytest.raises(PathSecurityError) as exc_info:
            validate_target_path(tmp_path, "requirements.txt")
        assert "must be a Python (.py) file" in str(exc_info.value)

    def test_rejects_nonexistent_repo(self, tmp_path: Path) -> None:
        nonexistent = tmp_path / "missing_repo"
        with pytest.raises(FileNotFoundError):
            validate_target_path(nonexistent, "shop.py")

    def test_rejects_repo_that_is_a_file(self, tmp_path: Path) -> None:
        file_path = tmp_path / "repo.py"
        file_path.write_text("# dummy", encoding="utf-8")

        with pytest.raises(PathSecurityError):
            validate_target_path(file_path, "shop.py")

    def test_rejects_missing_target_file_on_snapshot(self, tmp_path: Path) -> None:
        with pytest.raises(FileNotFoundError):
            create_snapshot(tmp_path, "nonexistent.py")

    def test_rejects_absolute_path_outside_repo(self, tmp_path: Path) -> None:
        repo = tmp_path / "repo"
        repo.mkdir()
        outside_file = tmp_path / "secret.py"
        outside_file.write_text("SECRET=123", encoding="utf-8")

        with pytest.raises(PathSecurityError) as exc_info:
            validate_target_path(repo, outside_file)
        assert "escapes repository root" in str(exc_info.value)

    def test_rejects_unsafe_symlink_when_containment_fails(self, tmp_path: Path) -> None:
        repo = tmp_path / "repo"
        repo.mkdir()
        symlink_candidate = repo / "symlink_file.py"
        symlink_candidate.write_text("# dummy", encoding="utf-8")

        with patch.object(Path, "is_symlink", return_value=True):
            with patch.object(Path, "relative_to", side_effect=ValueError("escaped subpath")):
                with pytest.raises(PathSecurityError) as exc_info:
                    validate_target_path(repo, "symlink_file.py")
                assert "escapes repository root" in str(exc_info.value) or "cannot be safely contained" in str(exc_info.value)


class TestSnapshotAndRollback:
    """Tests for safe file snapshotting, controlled restoration, and non-destructive rollbacks."""

    def test_snapshot_and_restore_cycle(self, tmp_path: Path) -> None:
        shop_file = tmp_path / "shop.py"
        original_code = "def get_total():\n    return 100\n"
        shop_file.write_text(original_code, encoding="utf-8")

        # 1. Create snapshot
        snapshot = create_snapshot(tmp_path, "shop.py")
        assert snapshot.original_content == original_code
        assert snapshot.target_path == shop_file.resolve()

        # 2. Mutate file (simulate a failed or broken refactor)
        mutated_code = "def get_total():\n    return 99999\n"
        shop_file.write_text(mutated_code, encoding="utf-8")
        assert shop_file.read_text(encoding="utf-8") == mutated_code

        # 3. Restore snapshot
        success = restore_snapshot(snapshot)
        assert success is True
        assert shop_file.read_text(encoding="utf-8") == original_code

    def test_convenience_restore_method(self, tmp_path: Path) -> None:
        target = tmp_path / "calc.py"
        target.write_text("X = 1\n", encoding="utf-8")

        snapshot = create_snapshot(tmp_path, "calc.py")
        target.write_text("X = 2\n", encoding="utf-8")

        assert snapshot.restore() is True
        assert target.read_text(encoding="utf-8") == "X = 1\n"

    def test_restore_preserves_unrelated_files(self, tmp_path: Path) -> None:
        target = tmp_path / "target.py"
        unrelated = tmp_path / "unrelated.py"

        target.write_text("TARGET = 1\n", encoding="utf-8")
        unrelated.write_text("UNRELATED_DIRTY_CHANGE = True\n", encoding="utf-8")

        snapshot = create_snapshot(tmp_path, "target.py")

        # Mutate target
        target.write_text("TARGET = 2\n", encoding="utf-8")

        # Restore target
        snapshot.restore()

        # Target restored, unrelated file remains completely untouched!
        assert target.read_text(encoding="utf-8") == "TARGET = 1\n"
        assert unrelated.read_text(encoding="utf-8") == "UNRELATED_DIRTY_CHANGE = True\n"

    def test_safe_apply_code_success(self, tmp_path: Path) -> None:
        target = tmp_path / "service.py"
        target.write_text("def run():\n    return False\n", encoding="utf-8")

        new_code = "def run():\n    return True\n"
        snapshot = safe_apply_code(tmp_path, "service.py", new_code)

        assert target.read_text(encoding="utf-8") == new_code
        assert snapshot.original_content == "def run():\n    return False\n"

        # Roll back
        snapshot.restore()
        assert target.read_text(encoding="utf-8") == "def run():\n    return False\n"

    def test_safe_apply_rejects_invalid_syntax_without_modifying_file(self, tmp_path: Path) -> None:
        target = tmp_path / "service.py"
        original_code = "def run():\n    return True\n"
        target.write_text(original_code, encoding="utf-8")

        invalid_code = "def broken(:\n    pass\n"

        with pytest.raises(SyntaxValidationError):
            safe_apply_code(tmp_path, "service.py", invalid_code)

        # Ensure the file was NEVER modified
        assert target.read_text(encoding="utf-8") == original_code
