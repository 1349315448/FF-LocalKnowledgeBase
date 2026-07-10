"""Read-only environment and agent-surface detection."""

from __future__ import annotations

import os
import platform
import shutil
import sys
from pathlib import Path

from .filesystem import IGNORED_DIRECTORIES


def _fact(value: object, confidence: str, evidence: list[str], source: str) -> dict:
    """Build the common evidence-bearing finding shape."""
    return {"value": value, "confidence": confidence, "evidence": evidence, "source": source}


def detect_environment(workspace_root: str | Path) -> dict:
    """Inspect runtime capabilities and visible agent entry files without writing files."""
    root = Path(workspace_root).resolve()
    if not root.is_dir():
        raise ValueError(f"Workspace root does not exist: {root}")

    system = platform.system().lower()
    os_name = {"windows": "windows", "linux": "linux", "darwin": "macos"}.get(system, system)
    agents: list[dict] = []
    agent_files = (("AGENTS.md", "generic"), ("CLAUDE.md", "claude"), ("GEMINI.md", "gemini"))
    for file_name, agent_name in agent_files:
        if (root / file_name).is_file():
            agents.append(_fact(agent_name, "high", [file_name], "instruction-file-detector"))
    workbuddy_skill_locations = (
        (root / ".workbuddy" / "skills", "high", ".workbuddy/skills"),
        (root / ".workbuddy-ai" / "skills", "high", ".workbuddy-ai/skills"),
        (Path.home() / ".workbuddy" / "skills", "medium", "HOME:.workbuddy/skills"),
        (Path.home() / ".workbuddy-ai" / "skills", "medium", "HOME:.workbuddy-ai/skills"),
    )
    for skills_path, confidence, evidence in workbuddy_skill_locations:
        if skills_path.is_dir():
            agents.append(_fact(
                "workbuddy",
                confidence,
                [evidence],
                "skill-directory-detector",
            ))
            break
    detected_agent_names = {str(item["value"]) for item in agents}
    for command, agent_name in (("codex", "codex"), ("claude", "claude"), ("gemini", "gemini")):
        if shutil.which(command) and agent_name not in detected_agent_names:
            agents.append(_fact(agent_name, "high", [f"PATH:{command}"], "executable-detector"))
            detected_agent_names.add(agent_name)
    if os.environ.get("CODEX_HOME") and not any(item["value"] == "codex" for item in agents):
        agents.append(_fact("codex", "medium", ["environment:CODEX_HOME"], "environment-detector"))

    git_roots: list[str] = []
    if (root / ".git").exists():
        git_roots.append(str(root))
    else:
        for current, directories, _ in os.walk(root, topdown=True, followlinks=False):
            current_path = Path(current)
            depth = len(current_path.relative_to(root).parts)
            directories[:] = [
                name for name in directories
                if name not in IGNORED_DIRECTORIES and name != ".git" and not (current_path / name).is_symlink()
            ]
            if depth > 3:
                directories[:] = []
                continue
            if (current_path / ".git").exists():
                git_roots.append(str(current_path))
                directories[:] = []
        if not git_roots:
            for candidate in root.parents:
                if (candidate / ".git").exists():
                    git_roots.append(str(candidate))
                    break

    return {
        "schema_version": "1.0",
        "workspace_root": str(root),
        "os": _fact(os_name, "high", [f"platform.system={platform.system()}"], "python-runtime"),
        "python": _fact(
            f"{sys.version_info.major}.{sys.version_info.minor}.{sys.version_info.micro}",
            "high",
            [f"sys.executable={sys.executable}"],
            "python-runtime",
        ),
        "python_supported": _fact(
            sys.version_info >= (3, 11),
            "high",
            ["requires Python >=3.11"],
            "runtime-compatibility",
        ),
        "shell": _fact(
            os.environ.get("SHELL") or os.environ.get("COMSPEC") or "unknown",
            "medium",
            ["environment:SHELL|COMSPEC"],
            "environment-detector",
        ),
        "git": _fact(bool(shutil.which("git")), "high", ["PATH lookup only"], "executable-detector"),
        "git_roots": git_roots,
        "agents": agents,
        "ci": _fact(bool(os.environ.get("CI")), "high", ["environment:CI"], "environment-detector"),
    }
