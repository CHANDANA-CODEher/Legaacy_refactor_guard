"""Security, syntax validation, and rollback guard module for Legacy Refactor Guard.

Protects against:
- Modifying test files
- Path traversal and escaping the repository root
- Invalid Python syntax (via AST parsing without execution)
- Uncontrolled changes (via safe single-file snapshots and rollbacks)
- Symlink-based security escapes
"""

from __future__ import annotations

import ast
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path


class GuardError(Exception):
    """Base exception for all guard violations."""


class PathSecurityError(GuardError):
    """Raised when a file path violates containment, directory traversal, or symlink rules."""


class ProtectedFileError(GuardError):
    """Raised when an operation attempts to modify a protected file (e.g., test files)."""


class SyntaxValidationError(GuardError):
    """Raised when code fails AST syntax validation."""


class SnapshotError(GuardError):
    """Raised when creating or restoring a snapshot fails."""


@dataclass(frozen=True)
class SyntaxValidationResult:
    """Outcome of an AST syntax validation check."""

    is_valid: bool
    error_message: str = ""
    error_line: int | None = None
    error_offset: int | None = None


@dataclass
class FileSnapshot:
    """Represents a safe snapshot of a single permitted target file."""

    repo_path: Path
    target_path: Path
    original_content: str
    created_at: str

    def restore(self) -> bool:
        """Restore this file snapshot."""
        return restore_snapshot(self)


def validate_python_syntax(code: str, filename: str = "<string>") -> SyntaxValidationResult:
    """Validate Python source code using ast.parse without executing it.

    Args:
        code: Python source code string to validate.
        filename: Optional label to display in error reports.

    Returns:
        SyntaxValidationResult with is_valid=True or error details.
    """
    try:
        ast.parse(code, filename=filename)
        return SyntaxValidationResult(is_valid=True)
    except SyntaxError as exc:
        msg = f"SyntaxError at line {exc.lineno}, column {exc.offset}: {exc.msg}"
        return SyntaxValidationResult(
            is_valid=False,
            error_message=msg,
            error_line=exc.lineno,
            error_offset=exc.offset,
        )


def assert_valid_syntax(code: str, filename: str = "<string>") -> None:
    """Validate Python source code and raise SyntaxValidationError if invalid.

    Args:
        code: Python source code string to validate.

    Raises:
        SyntaxValidationError: If code contains syntax errors.
    """
    result = validate_python_syntax(code, filename=filename)
    if not result.is_valid:
        raise SyntaxValidationError(result.error_message)


def is_test_file(path: Path) -> bool:
    """Check if a path points to a test file or test directory.

    Matches:
    - Files starting with 'test_'
    - Files ending with '_test.py'
    - 'conftest.py'
    - Any path having a directory component named 'test' or 'tests'

    Args:
        path: Path object to evaluate.

    Returns:
        True if the file is considered a test file, otherwise False.
    """
    name = path.name.lower()
    if name.startswith("test_") or name.endswith("_test.py") or name == "conftest.py":
        return True

    for part in path.parts:
        if part.lower() in ("test", "tests"):
            return True

    return False


def validate_target_path(
    repo_dir: str | Path,
    target_path: str | Path,
    allow_test_files: bool = False,
) -> Path:
    """Validate that a target file is safe to inspect or modify.

    Enforces:
    1. Repository directory exists and is a directory.
    2. Target path resolves strictly inside repository root (no ../ traversal).
    3. Target path does not use symlinks that escape repository containment.
    4. Target file is not a protected test file (unless explicitly allowed).
    5. Target file is a Python file (.py).

    Args:
        repo_dir: Root directory of the repository.
        target_path: Target file path (relative to repo_dir or absolute).
        allow_test_files: If False, raises ProtectedFileError for test files.

    Returns:
        Resolved Path to the validated target file.

    Raises:
        FileNotFoundError: If repository does not exist.
        PathSecurityError: If repository is invalid, path escapes repo root, or symlink is unsafe.
        ProtectedFileError: If target is a test file and allow_test_files is False.
    """
    repo = Path(repo_dir).resolve()
    if not repo.exists():
        raise FileNotFoundError(f"Repository directory does not exist: {repo_dir}")
    if not repo.is_dir():
        raise PathSecurityError(f"Repository path is not a directory: {repo_dir}")

    target = Path(target_path)
    # If relative, resolve relative to repo
    resolved_target = (repo / target).resolve() if not target.is_absolute() else target.resolve()

    # 1. Traversal / Containment check
    try:
        resolved_target.relative_to(repo)
    except ValueError:
        raise PathSecurityError(
            f"Path traversal detected: target '{target_path}' escapes repository root '{repo}'."
        )

    # 2. Symlink containment check
    raw_path = (repo / target) if not target.is_absolute() else target
    if raw_path.is_symlink():
        try:
            link_target = raw_path.resolve()
            if not link_target.is_relative_to(repo):
                raise PathSecurityError(
                    f"Symlink target '{target_path}' resolves outside repository root '{repo}'."
                )
        except (OSError, RuntimeError) as exc:
            raise PathSecurityError(
                f"Failed to safely resolve symlink for '{target_path}': {exc}"
            )

    # 3. Check for protected test files
    if not allow_test_files and is_test_file(resolved_target):
        raise ProtectedFileError(
            f"Protected file error: '{target_path}' is a test file and cannot be modified."
        )

    # 4. Check file extension (.py required)
    if resolved_target.suffix.lower() != ".py":
        raise PathSecurityError(
            f"Target file must be a Python (.py) file, got: '{resolved_target.name}'"
        )

    return resolved_target


def create_snapshot(repo_dir: str | Path, target_path: str | Path) -> FileSnapshot:
    """Create a safe snapshot of a permitted target file's current contents.

    Args:
        repo_dir: Root directory of the repository.
        target_path: Path to the target file.

    Returns:
        FileSnapshot instance containing original contents and metadata.

    Raises:
        FileNotFoundError: If the target file does not exist on disk.
        PathSecurityError: If target is a directory or fails security validation.
        ProtectedFileError: If target is a test file.
        SnapshotError: If reading the file fails due to filesystem errors.
    """
    resolved_target = validate_target_path(repo_dir, target_path, allow_test_files=False)

    if not resolved_target.exists():
        raise FileNotFoundError(f"Target file does not exist: {resolved_target}")
    if not resolved_target.is_file():
        raise PathSecurityError(f"Target path is not a regular file: {resolved_target}")

    try:
        content = resolved_target.read_text(encoding="utf-8")
    except OSError as exc:
        raise SnapshotError(f"Failed to read target file '{resolved_target}': {exc}")

    return FileSnapshot(
        repo_path=Path(repo_dir).resolve(),
        target_path=resolved_target,
        original_content=content,
        created_at=datetime.now(timezone.utc).isoformat(),
    )


def restore_snapshot(snapshot: FileSnapshot) -> bool:
    """Restore a target file to its snapshot contents.

    Ensures only the specific target file is restored and verifies containment
    before writing. Does not use git reset or affect other files.

    Args:
        snapshot: The FileSnapshot to restore.

    Returns:
        True if restoration succeeded.

    Raises:
        PathSecurityError: If the target path escapes its repository root.
        ProtectedFileError: If the snapshot target is a test file.
        SnapshotError: If writing to the file fails.
    """
    repo = snapshot.repo_path.resolve()
    target = snapshot.target_path.resolve()

    # Re-verify containment and safety before restoring
    try:
        target.relative_to(repo)
    except ValueError:
        raise PathSecurityError(
            f"Cannot restore file: target '{target}' escapes repository root '{repo}'."
        )

    if is_test_file(target):
        raise ProtectedFileError(
            f"Refusing to restore protected test file: '{target}'."
        )

    try:
        target.write_text(snapshot.original_content, encoding="utf-8")
        return True
    except OSError as exc:
        raise SnapshotError(f"Failed to restore file '{target}' from snapshot: {exc}")


def safe_apply_code(
    repo_dir: str | Path,
    target_path: str | Path,
    new_code: str,
) -> FileSnapshot:
    """Safely validate syntax and apply changes to a target file.

    Takes a snapshot of the target file BEFORE modifying it.
    Validates Python syntax using AST parsing before touching the file.
    If writing fails, attempts an immediate rollback.

    Args:
        repo_dir: Root directory of the repository.
        target_path: Path to the target file.
        new_code: New Python source code to write.

    Returns:
        The FileSnapshot of the file prior to the change, for subsequent rollback
        if tests fail.

    Raises:
        SyntaxValidationError: If new_code is not valid Python syntax.
        ProtectedFileError: If target_path is a test file.
        PathSecurityError: If target_path violates containment or safety.
        SnapshotError: If writing to the file fails.
    """
    # 1. Validate syntax BEFORE touching anything
    assert_valid_syntax(new_code, filename=str(target_path))

    # 2. Take a snapshot of original contents
    snapshot = create_snapshot(repo_dir, target_path)

    # 3. Write new code safely
    try:
        snapshot.target_path.write_text(new_code, encoding="utf-8")
    except OSError as exc:
        try:
            snapshot.target_path.write_text(snapshot.original_content, encoding="utf-8")
        except OSError:
            pass
        raise SnapshotError(f"Failed to write new code to '{snapshot.target_path}': {exc}")

    return snapshot
