---
name: ff-plan
description: Create and maintain resumable requirements, plans, tasks, execution evidence, and reviews. Use for ambiguous, cross-layer, high-risk, multi-stage, long-running, or cross-session engineering work.
---

# FF Plan

Use `ORIENT -> SPECIFY -> CLARIFY -> PLAN -> TASKS -> IMPLEMENT -> REVIEW -> LEARN`.

Read [the artifact contract](references/artifacts.md) before creating task files.

## Requirements And Plan

- Record goal, non-goals, user scenarios, exact requirements, edge cases, and measurable success criteria.
- Ask only questions that materially affect behavior, data, permissions, compatibility, or acceptance.
- Record verified current evidence before the technical approach.
- Define public interfaces, dependency direction, risks, tests, and verification commands without placeholders.

## Tasks And Execution

- Split work by independently testable result and map every requirement to a task.
- Record RED, GREEN, refactor, verification, and deviations immediately.
- Update requirements and plan before implementing a changed requirement.
- Review requirements, test evidence, standards, and code quality as separate gates.

Stop at the phase requested by the user. Planning permission does not imply implementation permission.
