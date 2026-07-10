"""Safe, deterministic filesystem helpers shared by scanners and transactions."""

from __future__ import annotations

import hashlib
import os
from pathlib import Path
from typing import Iterable, Iterator


IGNORED_DIRECTORIES = frozenset({
    ".git", ".hg", ".svn", ".agent", ".ffkb", ".workbuddy", ".workbuddy-ai", "node_modules", "vendor", ".venv",
    "venv", "env", "dist", "build", "target", "bin", "obj", "coverage",
    ".idea", ".vscode", ".aws", ".ssh", ".runtime", "__pycache__", ".mypy_cache", ".pytest_cache",
})
SECRET_NAMES = frozenset({
    ".env", ".env.local", ".env.production", ".env.development", "secrets.json",
    "credentials.json", "id_rsa", "id_ed25519", ".npmrc", ".pypirc",
})
BINARY_SUFFIXES = frozenset({
    ".png", ".jpg", ".jpeg", ".gif", ".webp", ".ico", ".pdf", ".zip",
    ".tar", ".gz", ".7z", ".rar", ".exe", ".dll", ".so", ".dylib",
    ".class", ".jar", ".pdb", ".woff", ".woff2", ".ttf", ".mp3", ".mp4",
    ".mov", ".db", ".sqlite", ".sqlite3", ".pyc",
})
DEFAULT_MAX_FILE_SIZE = 1_000_000
SENSITIVE_DIRECTORIES = frozenset({".ssh", ".aws", ".gnupg"})
SENSITIVE_SUFFIXES = frozenset({".pem", ".key", ".p12", ".pfx"})


def normalize_relative(path: str | Path) -> str:
    """Return a platform-neutral relative path or reject traversal/absolute input."""
    candidate = Path(path)
    if candidate.is_absolute() or any(part == ".." for part in candidate.parts):
        raise ValueError(f"Path is outside the allowed root: {path}")
    normalized = candidate.as_posix()
    while normalized.startswith("./"):
        normalized = normalized[2:]
    if not normalized or normalized == ".":
        raise ValueError("A target file path is required")
    return normalized


def resolve_within(root: Path, relative: str | Path) -> Path:
    """Resolve a relative target and reject lexical or symlink escape."""
    root = root.resolve()
    normalized = normalize_relative(relative)
    target = (root / normalized).resolve(strict=False)
    try:
        target.relative_to(root)
    except ValueError as exc:
        raise ValueError(f"Path is outside the allowed root: {relative}") from exc
    return target


def is_sensitive_relative(path: str | Path) -> bool:
    """Identify paths that installation plans must never read, journal, or replace."""
    normalized = normalize_relative(path)
    candidate = Path(normalized)
    lower_parts = {part.lower() for part in candidate.parts}
    lower_name = candidate.name.lower()
    return (
        bool(lower_parts & SENSITIVE_DIRECTORIES)
        or lower_name in SECRET_NAMES
        or lower_name.startswith(".env")
        or candidate.suffix.lower() in SENSITIVE_SUFFIXES
    )


def is_safe_file(path: Path, max_file_size: int = DEFAULT_MAX_FILE_SIZE) -> bool:
    """Return whether a file is suitable for local structural inspection."""
    lower_name = path.name.lower()
    secret_pattern = lower_name.startswith(".env") or path.suffix.lower() in {".pem", ".key", ".p12", ".pfx"}
    if lower_name in SECRET_NAMES or secret_pattern or path.suffix.lower() in BINARY_SUFFIXES:
        return False
    try:
        if path.stat().st_size > max_file_size:
            return False
        sample = path.read_bytes()[:4096]
    except (OSError, PermissionError):
        return False
    return b"\x00" not in sample


def iter_safe_files(root: Path, max_file_size: int = DEFAULT_MAX_FILE_SIZE) -> Iterator[Path]:
    """Yield inspectable files without following ignored or symlinked directories."""
    root = root.resolve()
    for current, directories, files in os.walk(root, topdown=True, followlinks=False):
        directories[:] = sorted(
            name for name in directories
            if name not in IGNORED_DIRECTORIES and not (Path(current) / name).is_symlink()
        )
        for name in sorted(files):
            path = Path(current) / name
            if path.is_symlink() or not is_safe_file(path, max_file_size):
                continue
            yield path


def sha256_bytes(content: bytes) -> str:
    """Return a lowercase SHA-256 digest for deterministic contracts."""
    return hashlib.sha256(content).hexdigest()


def file_hash(path: Path) -> str | None:
    """Hash a regular file, returning None when it does not exist."""
    if not path.is_file():
        return None
    return sha256_bytes(path.read_bytes())


def workspace_snapshot(root: Path, excluded: Iterable[str] = ()) -> str:
    """Hash safe workspace files, excluding managed operation targets when requested."""
    root = root.resolve()
    excluded_paths = {normalize_relative(item) for item in excluded}
    digest = hashlib.sha256()
    for path in iter_safe_files(root):
        relative = path.relative_to(root).as_posix()
        if relative in excluded_paths:
            continue
        digest.update(relative.encode("utf-8"))
        digest.update(b"\x00")
        digest.update(path.read_bytes())
        digest.update(b"\x00")
    return digest.hexdigest()
