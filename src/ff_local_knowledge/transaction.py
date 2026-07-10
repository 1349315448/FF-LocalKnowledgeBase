"""Transactional application and conflict-safe lifecycle management."""

from __future__ import annotations

import base64
import json
import os
import shutil
import uuid
from pathlib import Path

from .filesystem import file_hash, resolve_within, workspace_snapshot
from .planning import validate_plan_hash


class InstallationError(RuntimeError):
    """Raised when a plan cannot be applied without violating transaction invariants."""


def _state_paths(root: Path) -> tuple[Path, Path, Path]:
    """Return runtime root, current manifest and journal directory."""
    runtime = root / ".ffkb" / "runtime"
    return runtime, runtime / "install-manifest.json", runtime / "journal"


def _load_json(path: Path) -> dict | None:
    """Read an optional JSON object from disk."""
    if not path.is_file():
        return None
    return json.loads(path.read_text(encoding="utf-8"))


def _write_json(path: Path, value: dict) -> None:
    """Atomically write a JSON state file in its owning directory."""
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(path.name + ".tmp")
    temporary.write_text(json.dumps(value, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    os.replace(temporary, path)


def _validate_allowed_target(root: Path, plan: dict, relative: str) -> Path:
    """Enforce both the project boundary and the plan's explicit allowed-root contract."""
    allowed = {str(Path(item).resolve()) for item in plan.get("allowed_roots", [])}
    if str(root) not in allowed:
        raise InstallationError("Project root is not present in plan allowed roots")
    try:
        return resolve_within(root, relative)
    except ValueError as exc:
        raise InstallationError(str(exc)) from exc


def _current_install_matches(root: Path, manifest: dict, plan: dict) -> bool:
    """Return whether the active manifest already represents this exact plan."""
    if manifest.get("plan_hash") != plan.get("content_hash"):
        return False
    return all(
        file_hash(resolve_within(root, item["path"])) == item["installed_hash"]
        for item in manifest.get("files", [])
    )


def apply_plan(plan: dict) -> dict:
    """Stage, journal and atomically write all plan operations or restore all preimages."""
    if not validate_plan_hash(plan):
        raise InstallationError("Plan content hash is invalid")
    root = Path(plan["project_root"]).resolve()
    if not root.is_dir():
        raise InstallationError(f"Project root does not exist: {root}")
    excluded = [item["path"] for item in plan["operations"]]
    if workspace_snapshot(root, excluded) != plan["snapshot_hash"]:
        raise InstallationError("Workspace snapshot changed after the plan was created")

    runtime, manifest_path, journal_dir = _state_paths(root)
    active_manifest = _load_json(manifest_path)
    if active_manifest:
        if _current_install_matches(root, active_manifest, plan):
            return {
                "status": "already_applied",
                "transaction_id": active_manifest["transaction_id"],
                "manifest": str(manifest_path),
            }
        raise InstallationError(
            "a different installation is already active; rollback or uninstall it before applying another plan"
        )

    transaction_id = uuid.uuid4().hex
    staging = runtime / "staging" / transaction_id
    staged_files: list[tuple[Path, Path]] = []
    journal_files: list[dict] = []

    # 1. Validate every preimage before creating transaction state.
    for operation in plan["operations"]:
        target = _validate_allowed_target(root, plan, operation["path"])
        current_hash = file_hash(target)
        if current_hash != operation["preimage_hash"]:
            raise InstallationError(f"Preimage conflict for {operation['path']}")
        preimage = target.read_bytes() if target.is_file() else None
        journal_files.append({
            "path": operation["path"],
            "preimage_hash": current_hash,
            "preimage_base64": base64.b64encode(preimage).decode("ascii") if preimage is not None else None,
            "installed_hash": operation["target_hash"],
            "mode": operation["mode"],
            "marker": operation.get("marker"),
        })

    # 2. Materialize deterministic contents in staging and persist the recovery journal.
    for operation in plan["operations"]:
        staged = staging / operation["path"]
        staged.parent.mkdir(parents=True, exist_ok=True)
        staged.write_bytes(operation["content"].encode("utf-8"))
        if file_hash(staged) != operation["target_hash"]:
            raise InstallationError(f"Staging hash mismatch for {operation['path']}")
        staged_files.append((staged, _validate_allowed_target(root, plan, operation["path"])))
    journal = {
        "schema_version": "1.0",
        "transaction_id": transaction_id,
        "project_root": str(root),
        "plan_hash": plan["content_hash"],
        "status": "prepared",
        "files": journal_files,
    }
    journal_path = journal_dir / f"{transaction_id}.json"
    _write_json(journal_path, journal)

    manifest = {
        "schema_version": "1.0",
        "transaction_id": transaction_id,
        "project_root": str(root),
        "plan_hash": plan["content_hash"],
        "files": journal_files,
        "owned_paths": [item["path"] for item in journal_files],
    }

    # 3. Commit targets and state; any failure restores every already-written target.
    written: list[dict] = []
    try:
        for staged, target in staged_files:
            target.parent.mkdir(parents=True, exist_ok=True)
            os.replace(staged, target)
            written.append(next(item for item in journal_files if item["path"] == target.relative_to(root).as_posix()))
        _write_json(manifest_path, manifest)
        journal["status"] = "committed"
        _write_json(journal_path, journal)
    except Exception:
        for item in reversed(written):
            _restore_preimage(root, item)
        if manifest_path.exists():
            manifest_path.unlink()
        journal["status"] = "rolled_back_after_error"
        _write_json(journal_path, journal)
        raise
    finally:
        shutil.rmtree(staging, ignore_errors=True)
    return {"status": "applied", "transaction_id": transaction_id, "manifest": str(manifest_path)}


def _restore_preimage(root: Path, item: dict) -> None:
    """Restore one journaled file or remove it when it did not exist before installation."""
    target = resolve_within(root, item["path"])
    encoded = item.get("preimage_base64")
    if encoded is None:
        if target.exists():
            target.unlink()
        return
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_bytes(base64.b64decode(encoded))


def doctor(project_root: str | Path) -> dict:
    """Check whether every currently managed file still matches its installed hash."""
    root = Path(project_root).resolve()
    _, manifest_path, _ = _state_paths(root)
    manifest = _load_json(manifest_path)
    if not manifest:
        return {"status": "not_installed", "files": []}
    files = []
    for item in manifest.get("files", []):
        actual = file_hash(resolve_within(root, item["path"]))
        files.append({"path": item["path"], "expected": item["installed_hash"], "actual": actual})
    return {"status": "healthy" if all(item["expected"] == item["actual"] for item in files) else "conflict", "files": files}


def _restore_manifest(project_root: str | Path, success_status: str) -> dict:
    """Restore an active manifest only when no managed file has user modifications."""
    root = Path(project_root).resolve()
    _, manifest_path, journal_dir = _state_paths(root)
    manifest = _load_json(manifest_path)
    if not manifest:
        return {"status": "not_installed", "conflicts": []}
    conflicts = [
        item["path"] for item in manifest.get("files", [])
        if file_hash(resolve_within(root, item["path"])) != item["installed_hash"]
    ]
    if conflicts:
        return {"status": "conflict", "conflicts": conflicts}
    for item in reversed(manifest.get("files", [])):
        _restore_preimage(root, item)
    manifest_path.unlink()
    journal_path = journal_dir / f"{manifest['transaction_id']}.json"
    journal = _load_json(journal_path)
    if journal:
        journal["status"] = success_status
        _write_json(journal_path, journal)
    return {"status": success_status, "conflicts": []}


def rollback(project_root: str | Path) -> dict:
    """Restore the active transaction's preimages without overwriting user modifications."""
    return _restore_manifest(project_root, "rolled_back")


def uninstall(project_root: str | Path) -> dict:
    """Remove installation-owned changes only when all managed hashes still match."""
    return _restore_manifest(project_root, "uninstalled")
