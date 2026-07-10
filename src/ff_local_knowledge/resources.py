"""Single seam for repository-shipped profiles, templates and adapter resources."""

from __future__ import annotations

import os
import json
import sysconfig
from pathlib import Path

from .filesystem import normalize_relative


class ResourceUnavailableError(RuntimeError):
    """Raised when a non-editable installation cannot locate required shared resources."""


def locate_resource_root() -> Path:
    """Locate configured, source-checkout, or installed-wheel shared resources."""
    configured = os.environ.get("FFKB_RESOURCE_ROOT")
    candidates = [Path(configured)] if configured else []
    module_path = Path(__file__).resolve()
    if len(module_path.parents) > 2:
        candidates.append(module_path.parents[2])
    candidates.append(Path.cwd())
    candidates.append(Path(sysconfig.get_path("data")) / "share" / "ff-local-knowledge-base")
    for candidate in candidates:
        root = candidate.resolve()
        if (
            (root / "templates" / "knowledge").is_dir()
            and (root / "profiles").is_dir()
            and (root / "skills").is_dir()
        ):
            return root
    raise ResourceUnavailableError(
        "FFKB resources are unavailable. Reinstall the package with shared resources or set "
        "FFKB_RESOURCE_ROOT to a checkout containing templates and profiles."
    )


def _render(content: str, values: dict[str, str]) -> str:
    """Replace the small documented template token set deterministically."""
    for key, value in values.items():
        content = content.replace("{{" + key + "}}", value)
    return content


def build_default_operations(report: dict, answers: dict) -> tuple[list[dict], dict]:
    """Build knowledge, profile and thin-adapter operations from confirmed choices."""
    resource_root = locate_resource_root()
    knowledge_path = normalize_relative(answers.get("knowledge_path", ".ff-knowledge"))
    project_root = Path(report["project_root"])
    project_id = str(answers.get("project_id") or project_root.name.lower().replace(" ", "-"))
    project_name = str(answers.get("project_name") or project_root.name)
    values = {
        "PROJECT_ID": project_id,
        "PROJECT_NAME": project_name,
        "LOCALE": str(answers.get("locale", "en")),
        "KNOWLEDGE_ROOT": knowledge_path,
    }
    operations: list[dict] = []
    knowledge_source = resource_root / "templates" / "knowledge"
    knowledge_sources = {
        source.relative_to(knowledge_source).as_posix(): source
        for source in knowledge_source.rglob("*")
        if source.is_file()
    }
    if values["LOCALE"].casefold().startswith("zh"):
        localized_source = resource_root / "templates" / "locales" / "zh-CN"
        if localized_source.is_dir():
            for source in localized_source.rglob("*"):
                if source.is_file():
                    knowledge_sources[source.relative_to(localized_source).as_posix()] = source
    for relative, source in sorted(knowledge_sources.items()):
        operations.append({
            "path": f"{knowledge_path}/{relative}",
            "content": _render(source.read_text(encoding="utf-8"), values),
            "mode": "managed_file",
        })

    detected_stacks = [str(item.get("value")) for item in report.get("findings", [])]
    profile_name = str(answers.get("profile") or next(
        (name for name in ("dotnet", "node", "python") if name in detected_stacks),
        "generic",
    ))
    profile_source = resource_root / "profiles" / profile_name / "profile.json"
    if not profile_source.is_file():
        raise ResourceUnavailableError(f"Confirmed profile is unavailable: {profile_name}")
    profile_content = profile_source.read_text(encoding="utf-8")
    operations.append({
        "path": f"{knowledge_path}/profile.json",
        "content": profile_content,
        "mode": "managed_file",
    })

    selected = list(dict.fromkeys(str(item) for item in answers.get("adapters", ["generic"])))
    if "codex" in selected and "generic" in selected:
        selected.remove("generic")
    adapter_targets = {"generic": "AGENTS.md", "codex": "AGENTS.md", "claude": "CLAUDE.md"}
    for adapter in selected:
        target = adapter_targets.get(adapter)
        if target is None:
            raise ResourceUnavailableError(f"Unsupported adapter: {adapter}")
        template = resource_root / "templates" / "adapters" / adapter / f"{target}.tmpl"
        if not template.is_file():
            raise ResourceUnavailableError(f"Adapter template is unavailable: {adapter}")
        operations.append({
            "path": target,
            "content": _render(template.read_text(encoding="utf-8"), values),
            "mode": "managed_block",
            "marker": f"ffkb-{adapter}",
        })

    skill_targets: list[str] = []
    if any(adapter in selected for adapter in ("generic", "codex")):
        skill_targets.append(".agents/skills")
    if "claude" in selected:
        skill_targets.append(".claude/skills")
    skills_source = resource_root / "skills"
    for target_root in skill_targets:
        for source in sorted(path for path in skills_source.rglob("*") if path.is_file()):
            relative = source.relative_to(skills_source).as_posix()
            operations.append({
                "path": f"{target_root}/{relative}",
                "content": source.read_text(encoding="utf-8"),
                "mode": "managed_file",
            })
    return operations, {
        "resource_root": str(resource_root),
        "profile": profile_name,
        "profile_standards": json.loads(profile_content).get("standards", []),
        "adapters": selected,
        "skill_targets": skill_targets,
        "knowledge_path": knowledge_path,
    }
