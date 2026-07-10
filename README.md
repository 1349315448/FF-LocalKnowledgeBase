# FF-LocalKnowledgeBase

FF-LocalKnowledgeBase is a local-first knowledge base, Agent Skills bundle, and
transactional onboarding CLI for AI coding agents.

It inspects a repository without executing project code, reports its evidence
for human confirmation, and only then installs compact project knowledge,
portable development Skills, and thin agent entrypoints. It has no runtime
dependencies, network calls, telemetry, hosted service, or model-provider lock-in.

## What It Provides

- `ffkb` CLI for environment detection, architecture scanning, confirmed install
  planning, transactional apply, doctor, rollback, uninstall, query, search,
  compact, and lint.
- A layered Markdown + JSON/JSONL knowledge format optimized for bounded agent
  context.
- Eight portable Agent Skills: bootstrap, KB bridge, develop, knowledge, learn,
  plan, verify, and review.
- Generic, Codex, Claude Code, and WorkBuddy workspace adapters.
- Generic, .NET, Node.js, and Python baseline profiles that remain proposed
  until the user confirms them.

## Requirements

- Python 3.11 or newer
- Git is recommended but not required for read-only scanning

## Install From Source

```bash
git clone <repository-url> FF-LocalKnowledgeBase
cd FF-LocalKnowledgeBase
python -m pip install -e .
ffkb --help
```

No remote is configured in this exported local copy. Replace `<repository-url>`
after publishing it to your chosen forge.

## Safe Two-Phase Onboarding

First generate reports. These commands do not modify the target project:

```bash
ffkb detect /path/to/project
ffkb scan /path/to/project \
  --json-output scan-report.json \
  --markdown-output scan-report.md
```

Review the report and create a confirmed answers file:

```json
{
  "standards_confirmed": true,
  "project_id": "example-project",
  "project_name": "Example Project",
  "locale": "en",
  "profile": "python",
  "adapters": ["generic"],
  "knowledge_path": ".ff-knowledge"
}
```

Generate and review a deterministic installation plan:

```bash
ffkb plan scan-report.json --answers answers.json --output install-plan.json
```

Only after approval, apply and verify it:

```bash
ffkb apply install-plan.json
ffkb doctor /path/to/project
ffkb lint /path/to/project/.ff-knowledge
ffkb query --root /path/to/project/.ff-knowledge --intent "testing standards"
```

Search all routed knowledge or rebuild the replaceable query cache when needed:

```bash
ffkb search /path/to/project/.ff-knowledge "testing"
ffkb compact /path/to/project/.ff-knowledge
```

The plan is bound to the scan snapshot. If the project changes before planning
or applying, FF refuses the stale operation and requires a new scan.

The example selects only `generic`: it creates an `AGENTS.md` managed block and
`.agents/skills/ff-*`, but never creates Claude files. Select `codex` or
`claude` only when that product is actually used; selecting multiple adapters
creates the union of their files.

For WorkBuddy, use `"adapters": ["workbuddy"]`. The plan installs project-level
Skills under `.workbuddy/skills/ff-*` and creates no AGENTS or Claude files.

## Installed Layout

Depending on confirmed adapters, the transaction creates the following files.
For `generic`, only the first, second, third, and last entries apply:

```text
.ff-knowledge/                 canonical project knowledge
.agents/skills/ff-*/           Generic and Codex Agent Skills
.claude/skills/ff-*/           Claude Code Agent Skills
.workbuddy/skills/ff-*/        WorkBuddy project Agent Skills
AGENTS.md                      reviewed FF managed block
CLAUDE.md                      reviewed FF managed block
.ffkb/runtime/                 install journal and manifest
```

Existing `AGENTS.md` and `CLAUDE.md` content is preserved outside the managed
block. Rollback and uninstall refuse to overwrite or delete files modified by
the user after installation.

```bash
ffkb rollback /path/to/project
ffkb uninstall /path/to/project
```

## Knowledge Query Design

`router.json` is the machine routing truth; `INDEX.md` is only its human-readable
display layer. Pages keep short current conclusions in `## compiled_truth`;
history and detailed evidence remain cold. Query returns only a bounded number
of pages and relationships and is side-effect free by default. Cache is derived
and can be rebuilt.

See [architecture](docs/ARCHITECTURE.md),
[installation](docs/INSTALLATION.md),
[knowledge schema](docs/KNOWLEDGE_SCHEMA.md), and
[agent adapters](docs/ADAPTERS.md), and
[Chinese Skills guide](docs/SKILLS.md).

## Development

```bash
python -m unittest discover -s tests -v
python -m ff_local_knowledge.cli --help
```

When running directly from an uninstalled source checkout, prepend `src` to
`PYTHONPATH`, or install the project in editable mode first.

## License

Apache License 2.0. See [LICENSE](LICENSE) and [NOTICE](NOTICE).
