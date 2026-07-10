---
name: ff-kb-bridge
description: Use ffkb to inspect, query, validate, compact, and recover a project's .ff-knowledge installation when WorkBuddy needs current project standards or transaction state.
---

# FF KB Bridge

Project-local knowledge backed by `ffkb`; use its bounded results as the current source for standards, architecture, and reusable facts.

## Principles

- Read with `query` or `search`; change installation state only through `scan` -> `plan` -> `apply`.
- Run `doctor` before any installation, rollback, or uninstall operation.
- Treat `.ff-knowledge/` as canonical knowledge and `.ffkb/runtime/` as transaction state; never edit their internals to bypass a command.
- Rebuild cache with `compact` only after canonical knowledge changes through the reviewed project workflow.
- Prefer current source when knowledge and code disagree; report the mismatch before changing either.

## Steps

1. Find the project root from the current workspace and run `ffkb doctor <project_root>`.
2. Query `.ff-knowledge/` with the concrete user intent; use `search` only when routing has low confidence.
3. For a bootstrap, reinstall, profile, or adapter change, show `scan` evidence and the plan before `apply`.
4. Run `lint` after an installation or reviewed knowledge change; use `rollback` if the latest installation must be reverted.

## Commands

| Action | Command |
|---|---|
| Health | `ffkb doctor <project_root>` |
| Routed query | `ffkb query --root <project_root>/.ff-knowledge --intent "<intent>"` |
| Keyword search | `ffkb search <project_root>/.ff-knowledge "<keyword>"` |
| Validate knowledge | `ffkb lint <project_root>/.ff-knowledge` |
| Rebuild cache | `ffkb compact <project_root>/.ff-knowledge` |
| Replan installation | `ffkb scan <project_root>` -> `ffkb plan` -> `ffkb apply` |
| Roll back last installation | `ffkb rollback <project_root>` |

## Output Contract

- `query` returns JSON with `pages[]` (`id`, `page`, `score`, `compiled_truth`), `related_edges[]`, and `used_budget`.
- Treat `doctor.status = "healthy"` as the required baseline for installation-changing commands.
- Successful `apply` returns a `transaction_id`; its recovery record is under `.ffkb/runtime/journal/`.
- If `doctor`, `lint`, or `apply` reports an error or conflict, stop the write path and report the result without manual file repair.

## Boundaries

- Do not edit `.ffkb/runtime/journal/` or `.ff-knowledge/pending.jsonl` directly.
- Do not run `scan` -> `apply` unless the user explicitly asks to bootstrap, reinstall, upgrade, or change profile/adapter choices.
- `ffkb` v0.1 does not provide arbitrary knowledge-content writes; use the project's reviewed learning workflow for L1/L2 knowledge changes.
- If a Windows CP936 console garbles Chinese, inspect files through an IDE or UTF-8 terminal instead of retrying a write command.
