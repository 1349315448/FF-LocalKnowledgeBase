---
name: ff-review
description: Review an actual diff against requirements, tests, project standards, regressions, complexity, and scope. Use before delivering substantial, shared, high-risk, or cross-layer engineering work.
---

# FF Review

Review the work product, not the implementer's confidence.

## Order

1. Requirement compliance and unintended behavior.
2. Correctness, error paths, security, data integrity, and compatibility.
3. Test-first and fresh verification evidence.
4. Project standards and architecture boundaries.
5. Complexity, duplication, maintainability, and unrelated scope.

## Findings

- Critical: unsafe to deliver, including data loss or security failure.
- Important: required behavior, regression, or maintainability issue that must be fixed.
- Minor: non-blocking improvement; do not expand scope automatically.

Every finding needs a file/line, impact, and concrete remediation. After fixing a Critical or Important finding, rerun verification and review the new diff. If no such findings remain, state the residual risk explicitly.
