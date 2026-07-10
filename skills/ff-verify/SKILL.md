---
name: ff-verify
description: Gather fresh evidence before reporting completion, correctness, or passing status. Use after implementation and before handoff, commits, releases, or any success claim.
---

# FF Verify

Evidence must be current and cover the actual claim.

1. Identify the command or observable check that proves each acceptance criterion.
2. Run the complete command after the latest change.
3. Read the exit code, failures, skips, warnings, and relevant output.
4. Report the actual result. A partial check cannot support a broader claim.
5. If verification changes the implementation, run the covering checks again.

Tests do not prove standards compliance, and a diff does not prove behavior. Hand successful verification to `ff-review` before final delivery when the work is substantial or risk-bearing.
