"""Evidence-based, read-only project architecture scanning."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Iterable

from .detection import detect_environment
from .filesystem import iter_safe_files, workspace_snapshot


STACK_MARKERS = {
    "pyproject.toml": "python",
    "requirements.txt": "python",
    "package.json": "node",
    "pnpm-workspace.yaml": "node-monorepo",
    "yarn.lock": "node",
    "global.json": "dotnet",
    "go.mod": "go",
    "Cargo.toml": "rust",
}
RULE_FILES = {"AGENTS.md", "CLAUDE.md", "GEMINI.md", ".editorconfig", "CONTRIBUTING.md"}
FORMATTER_FILES = {".prettierrc", ".prettierrc.json", "eslint.config.js", "ruff.toml"}
CI_FILES = {".gitlab-ci.yml", "azure-pipelines.yml", "Jenkinsfile"}
TEST_DIRECTORY_NAMES = {"test", "tests", "spec", "specs", "__tests__"}
ADAPTER_DESCRIPTIONS = {
    "generic": (
        "Creates an `AGENTS.md` managed block and `.agents/skills/ff-*`; "
        "does not create `.claude/skills` or `CLAUDE.md`. Choose this only when "
        "the target agent understands `AGENTS.md` or `.agents/skills`."
    ),
    "codex": (
        "Creates an `AGENTS.md` managed block and `.agents/skills/ff-*` for Codex; "
        "does not create Claude files."
    ),
    "claude": (
        "Creates a `CLAUDE.md` managed block and `.claude/skills/ff-*` for Claude Code; "
        "does not create `.agents/skills` or `AGENTS.md`."
    ),
}


def _finding(value: object, confidence: str, evidence: Iterable[str], source: str) -> dict:
    """Create a stable evidence-bearing report item."""
    return {"value": value, "confidence": confidence, "evidence": list(evidence), "source": source}


def _detect_manifest(path: Path, relative: str) -> list[dict]:
    """Infer stacks only from known manifest names and extensions."""
    findings: list[dict] = []
    stack = STACK_MARKERS.get(path.name)
    if stack:
        findings.append(_finding(stack, "high", [relative], "manifest-detector"))
    if path.suffix in {".sln", ".csproj", ".fsproj"}:
        findings.append(_finding("dotnet", "high", [relative], "manifest-detector"))
    return findings


def scan_workspace(workspace_root: str | Path) -> dict:
    """Scan safe metadata and return a deterministic report without executing project code."""
    root = Path(workspace_root).resolve()
    environment = detect_environment(root)
    files = list(iter_safe_files(root))
    findings: list[dict] = []
    standards: list[dict] = []
    architecture = {"manifests": [], "test_containers": [], "ci": [], "commands": []}

    seen_findings: set[tuple[str, str]] = set()
    seen_architecture: dict[str, set[str]] = {key: set() for key in architecture}
    for path in files:
        relative = path.relative_to(root).as_posix()
        manifest_findings = _detect_manifest(path, relative)
        for item in manifest_findings:
            key = (str(item["value"]), item["source"])
            if key not in seen_findings:
                findings.append(item)
                seen_findings.add(key)
        if manifest_findings and relative not in seen_architecture["manifests"]:
            architecture["manifests"].append(
                _finding(relative, "high", [relative], "manifest-detector")
            )
            seen_architecture["manifests"].add(relative)
        for part_index, part in enumerate(path.relative_to(root).parts[:-1]):
            if part.lower() in TEST_DIRECTORY_NAMES:
                container = Path(*path.relative_to(root).parts[:part_index + 1]).as_posix()
                if container not in seen_architecture["test_containers"]:
                    architecture["test_containers"].append(
                        _finding(container, "high", [relative], "test-container-detector")
                    )
                    seen_architecture["test_containers"].add(container)
                break
        is_github_workflow = (
            relative.startswith(".github/workflows/")
            and path.suffix.lower() in {".yml", ".yaml"}
        )
        if (path.name in CI_FILES or is_github_workflow) and relative not in seen_architecture["ci"]:
            architecture["ci"].append(_finding(relative, "high", [relative], "ci-detector"))
            seen_architecture["ci"].add(relative)
        if path.name == "package.json":
            try:
                package = json.loads(path.read_text(encoding="utf-8"))
            except (OSError, UnicodeError, json.JSONDecodeError):
                package = {}
            scripts = package.get("scripts") if isinstance(package, dict) else None
            if isinstance(scripts, dict):
                for script_name in sorted(str(name) for name in scripts):
                    command = "npm test" if script_name == "test" else f"npm run {script_name}"
                    if command not in seen_architecture["commands"]:
                        architecture["commands"].append(_finding(
                            command,
                            "high",
                            [f"{relative}:scripts.{script_name}"],
                            "package-script-detector",
                        ))
                        seen_architecture["commands"].add(command)
        if path.name in RULE_FILES:
            standards.append(_finding(relative, "high", [relative], "repository-rules"))
        elif path.name in FORMATTER_FILES:
            standards.append(_finding(relative, "high", [relative], "tool-configuration"))

    if not standards:
        standards.append(_finding(
            "generic-baseline",
            "low",
            [],
            "default-profile",
        ))
    stacks = [str(item["value"]) for item in findings]
    questions = []
    if not stacks:
        questions.append("No known stack was detected. Confirm the language and build system.")
    if not any(item["source"] == "repository-rules" for item in standards):
        questions.append("No repository coding instructions were found. Confirm or supplement the defaults.")

    layout = "multi-repository" if len(environment["git_roots"]) > 1 else "single-workspace"
    proposed_adapters = list(dict.fromkeys(
        str(item["value"]) for item in environment["agents"]
        if item.get("value") in {"generic", "codex", "claude"}
    )) or ["generic"]
    proposed_writes = [".ff-knowledge/", ".ffkb/runtime/"]
    if any(adapter in proposed_adapters for adapter in ("generic", "codex")):
        proposed_writes.extend([".agents/skills/", "AGENTS.md managed block"])
    if "claude" in proposed_adapters:
        proposed_writes.extend([".claude/skills/", "CLAUDE.md managed block"])
    return {
        "schema_version": "1.0",
        "project_root": str(root),
        "environment": environment,
        "workspace": _finding(layout, "medium", environment["git_roots"], "git-layout-detector"),
        "findings": findings,
        "architecture": architecture,
        "standards": standards,
        "adapters": environment["agents"],
        "proposed_adapters": proposed_adapters,
        "adapter_descriptions": {
            adapter: ADAPTER_DESCRIPTIONS[adapter]
            for adapter in proposed_adapters
            if adapter in ADAPTER_DESCRIPTIONS
        },
        "questions": questions,
        "proposed_writes": proposed_writes,
        "snapshot_hash": workspace_snapshot(root),
        "status": "confirmation_required",
    }


def render_markdown_report(report: dict) -> str:
    """Render the JSON report as a reviewable human document."""
    lines = [
        "# FF Local Knowledge Base Scan Report",
        "",
        f"- Project: `{report['project_root']}`",
        f"- Snapshot: `{report['snapshot_hash']}`",
        f"- Status: **Confirmation required**",
        "",
        "## Detected Architecture",
        "",
    ]
    if report["findings"]:
        for item in report["findings"]:
            evidence = ", ".join(item["evidence"]) or "none"
            lines.append(
                f"- `{item['value']}` ({item['confidence']}; {item['source']}) — {evidence}"
            )
    else:
        lines.append("- No known stack detected.")
    lines.extend(["", "## Architecture Evidence", ""])
    for label, items in report["architecture"].items():
        if items:
            lines.append(f"- {label}: " + ", ".join(f"`{item['value']}`" for item in items))
    lines.extend(["", "## Standards", ""])
    for item in report["standards"]:
        lines.append(f"- `{item['value']}` ({item['confidence']}; {item['source']})")
    lines.extend(["", "## Proposed Installation", ""])
    lines.append(f"- Adapters: {', '.join(report['proposed_adapters'])}")
    for adapter in report["proposed_adapters"]:
        description = report.get("adapter_descriptions", {}).get(adapter)
        if description:
            lines.append(f"  - `{adapter}`: {description}")
    if len(report["proposed_adapters"]) > 1:
        lines.append("  - Selecting multiple adapters creates the union of their files.")
    lines.extend(f"- Write after confirmation: `{path}`" for path in report["proposed_writes"])
    lines.extend(["", "## Questions", ""])
    lines.extend(f"- {question}" for question in report["questions"])
    if not report["questions"]:
        lines.append("- Confirm the detected architecture and proposed standards.")
    lines.extend(["", "No project files have been modified.", ""])
    return "\n".join(lines)


def write_scan_reports(report: dict, json_path: Path | None, markdown_path: Path | None) -> None:
    """Write explicitly requested report outputs; scanning itself remains read-only."""
    if json_path:
        json_path.parent.mkdir(parents=True, exist_ok=True)
        json_path.write_text(json.dumps(report, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    if markdown_path:
        markdown_path.parent.mkdir(parents=True, exist_ok=True)
        markdown_path.write_text(render_markdown_report(report), encoding="utf-8")
