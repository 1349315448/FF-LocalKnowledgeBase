# L2 Ingest Contract

Use this sequence only after the lesson is verified and qualifies for durable storage.

1. Query and search for an existing canonical page.
2. Compare the new evidence with current truth and identify replacement or conflict semantics.
3. Generate an ingest plan listing page, node, edge, audit, and cache effects.
4. Ask for confirmation when the change alters a public rule or architecture decision.
5. Apply the source changes once, then rebuild derived cache atomically.
6. Run lint and query the learned intent again.
7. Report changed source artifacts and verification evidence.

Edges and audit events are append-only. Node records represent current state and may be updated transactionally by stable ID.
