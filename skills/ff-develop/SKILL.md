---
name: ff-develop
description: Route repository development through project knowledge, evidence, tests, verification, review, and learning. Use for features, bug fixes, refactors, architecture work, or implementation planning after the target repository is known.
---

# FF Develop

Follow the lightest workflow that protects the requested change.

## Start

1. Query project knowledge with the user's intent.
2. Inspect the real source, configuration, VCS state, and nearby patterns.
3. Classify the task as small, medium, or large based on behavior and risk, not line count.

## Routes

- Small non-behavioral change: inspect -> minimal edit -> focused verification -> Learn L0.
- Feature or behavior change: test-first vertical slices -> focused verification -> standards review -> risk-based code review.
- Bug or unexpected behavior: collect evidence and isolate the root cause before writing the failing regression test.
- Cross-layer, public-interface, data, security, performance, or multi-stage work: use `ff-plan` and keep resumable task state.

## Rules

- Preserve user changes and existing project structure.
- Prefer existing capabilities and the smallest clear implementation.
- Never claim completion without fresh evidence from the actual changed behavior.
- Use `ff-learn` only after verification and review; routine discoveries default to pending capture rather than immediate canonical writeback.
