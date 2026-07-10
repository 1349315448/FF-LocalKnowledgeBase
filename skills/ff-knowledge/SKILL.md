---
name: ff-knowledge
description: Query and navigate compact local project knowledge before coding or reviewing. Use when an agent needs current standards, project ownership, architecture facts, public abstractions, decisions, or graph relationships.
---

# FF Knowledge

Use `ffkb query` as the default entrypoint. Consume only returned compiled truth and bounded related edges.

## Retrieval Order

1. Query by the user's concrete intent with the default page and character budgets.
2. If confidence is low, use `ffkb search` with shorter stable terms.
3. Read a full page or history only when the task requires the missing detail.
4. Follow graph relationships only after the page result identifies the relevant entities.
5. Treat deprecated nodes as historical evidence and follow their superseding relationship.

## Boundaries

- Do not load every standard, page, log, or graph file into context.
- Do not treat generated cache as a writeback source; canonical pages, router, and graph sources own the truth.
- Keep normal queries side-effect free. Enable local query telemetry only through explicit project configuration.
- When knowledge conflicts with current source code, report the mismatch and verify before changing either source.
