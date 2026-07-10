"""Deterministic installation-plan construction after explicit confirmation."""

from __future__ import annotations

import json
from pathlib import Path

from .filesystem import (
    file_hash,
    is_sensitive_relative,
    normalize_relative,
    resolve_within,
    sha256_bytes,
    workspace_snapshot,
)
from .resources import build_default_operations


def _canonical_hash(value: dict) -> str:
    """Hash a JSON-compatible contract using stable serialization."""
    payload = json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode("utf-8")
    return sha256_bytes(payload)


def _managed_block(existing: str, content: str, marker: str) -> str:
    """Add or replace one explicitly owned block while preserving surrounding user content."""
    if not marker or any(character in marker for character in "\r\n<>"):
        raise ValueError("Managed block marker must be a simple non-empty identifier")
    begin = f"<!-- BEGIN {marker} -->"
    end = f"<!-- END {marker} -->"
    block = f"{begin}\n{content.rstrip()}\n{end}"
    if begin in existing or end in existing:
        if existing.count(begin) != 1 or existing.count(end) != 1:
            raise ValueError(f"Managed block {marker!r} is malformed")
        start = existing.index(begin)
        finish = existing.index(end, start) + len(end)
        return existing[:start] + block + existing[finish:]
    separator = "" if not existing else ("\n" if existing.endswith("\n") else "\n\n")
    return existing + separator + block + "\n"


def create_install_plan(report: dict, answers: dict, operations: list[dict] | None = None) -> dict:
    """Create an apply-ready plan whose targets and preimages are bound by hashes."""
    if not isinstance(report, dict):
        raise ValueError("report must be an object")
    if not isinstance(answers, dict):
        raise ValueError("answers must be an object")
    if report.get("schema_version") != "1.0" or not report.get("snapshot_hash"):
        raise ValueError("A valid v1 scan report is required")
    if answers.get("standards_confirmed") is not True:
        raise ValueError("standards_confirmed must be true before planning installation")
    adapters = answers.get("adapters")
    if adapters is not None and (
        not isinstance(adapters, list)
        or not adapters
        or any(not isinstance(item, str) or not item for item in adapters)
    ):
        raise ValueError("adapters must be a non-empty array of strings")
    standards = answers.get("standards")
    if standards is not None and (
        not isinstance(standards, list)
        or any(
            not isinstance(item, str)
            or not item
            or "\n" in item
            or "\r" in item
            for item in standards
        )
    ):
        raise ValueError("standards must be an array of non-empty single-line strings")
    profile = answers.get("profile")
    if profile is not None and profile not in {"generic", "dotnet", "node", "python"}:
        raise ValueError("profile must be one of: generic, dotnet, node, python")
    locale = answers.get("locale")
    if locale is not None and (not isinstance(locale, str) or not locale.strip()):
        raise ValueError("locale must be a string")
    if operations is not None and not isinstance(operations, list):
        raise ValueError("operations must be an array")
    root = Path(report["project_root"]).resolve()
    if workspace_snapshot(root) != report["snapshot_hash"]:
        raise ValueError("Workspace changed after the scan snapshot; run scan again")
    default_operations, resource_selection = build_default_operations(report, answers) if operations is None else ([], {})
    raw_operations = default_operations if operations is None else operations
    resolved_standards = _resolve_standards(report, answers, resource_selection)
    if operations is None:
        _inject_confirmed_standards(raw_operations, resolved_standards)
    prepared: list[dict] = []
    target_paths: set[str] = set()

    for raw in raw_operations:
        if not isinstance(raw, dict):
            raise ValueError("operation must be an object")
        relative = normalize_relative(raw.get("path", ""))
        if is_sensitive_relative(relative):
            raise ValueError(f"Installation operation targets a sensitive path: {relative}")
        if relative in target_paths:
            raise ValueError(f"Duplicate operation target: {relative}")
        target_paths.add(relative)
        target = resolve_within(root, relative)
        mode = raw.get("mode", "managed_file")
        content = str(raw.get("content", ""))
        marker = raw.get("marker")
        if mode == "managed_block":
            existing = target.read_text(encoding="utf-8") if target.is_file() else ""
            content = _managed_block(existing, content, str(marker or "ffkb"))
        elif mode != "managed_file":
            raise ValueError(f"Unsupported operation mode: {mode}")
        encoded = content.encode("utf-8")
        prepared.append({
            "path": relative,
            "mode": mode,
            "marker": marker,
            "content": content,
            "target_hash": sha256_bytes(encoded),
            "preimage_hash": file_hash(target),
        })

    report_hash = _canonical_hash(report)
    plan_body = {
        "schema_version": "1.0",
        "project_root": str(root),
        "allowed_roots": [str(root)],
        "report_hash": report_hash,
        "report_snapshot_hash": report["snapshot_hash"],
        "snapshot_hash": workspace_snapshot(root, target_paths),
        "answers": answers,
        "resource_selection": resource_selection,
        "resolved_standards": resolved_standards,
        "operations": prepared,
    }
    plan_body["content_hash"] = _canonical_hash(plan_body)
    return plan_body


def _resolve_standards(report: dict, answers: dict, resource_selection: dict) -> dict:
    """Resolve standards using user, repository, profile, then generic precedence."""
    user_standards = answers.get("standards")
    if user_standards:
        return {"source": "user_confirmation", "items": list(user_standards)}
    repository_standards = [
        item["value"] for item in report.get("standards", [])
        if item.get("source") in {"repository-rules", "tool-configuration"}
    ]
    if repository_standards:
        return {
            "source": "repository",
            "items": [
                f"Follow the confirmed repository rule source: `{path}`."
                for path in repository_standards
            ],
        }
    profile_standards = resource_selection.get("profile_standards", [])
    if profile_standards:
        return {"source": "stack_profile", "items": profile_standards}
    return {"source": "generic_baseline", "items": ["Make minimal changes and verify them with current evidence."]}


def _inject_confirmed_standards(operations: list[dict], resolved_standards: dict) -> None:
    """Insert the resolved standard set into the canonical standards page operation."""
    marker = "{{CONFIRMED_STANDARDS}}"
    bullets = "\n".join(f"- {item}" for item in resolved_standards.get("items", []))
    for operation in operations:
        if str(operation.get("path", "")).endswith("pages/standards/coding-standards.md"):
            content = str(operation.get("content", ""))
            if marker not in content:
                raise ValueError("Canonical coding standards template is missing the standards marker")
            operation["content"] = content.replace(marker, bullets)
            return
    raise ValueError("Canonical coding standards operation is missing")


def validate_plan_hash(plan: dict) -> bool:
    """Verify that a serialized plan has not been edited after creation."""
    supplied = plan.get("content_hash")
    payload = dict(plan)
    payload.pop("content_hash", None)
    return bool(supplied) and supplied == _canonical_hash(payload)
