# Agent 适配器

核心工作流定义在可移植的 Agent Skills 与 `ffkb` CLI 中；适配器只负责让不同 Agent 产品能够发现这些能力，以及提供薄入口文件。

## v0.1 支持的适配器

- Generic：在仓库根目录生成简短的 `AGENTS.md` 指针，并复制 Skills 到 `.agents/skills/ff-*`；不会生成任何 Claude 文件。
- Codex：安装 Agent Skills，并可选提供 `agents/openai.yaml` 界面元数据。
- Claude Code：安装 Agent Skills，并在仓库根目录生成简短的 `CLAUDE.md` 指针。

选择 Generic 或 Codex 时，canonical Skills 会安装到 `.agents/skills`；选择 Claude Code 时，同一套 Skills 会安装到 `.claude/skills`。同时选择两类产品时，会从同一份 canonical source 生成两套发现目录，这是预期行为。

`generic` 并不表示“只写一个 `AGENTS.md`”，也不表示“任何第三方 Agent 都能自动发现”。只有目标 Agent 明确支持 `AGENTS.md` 或 `.agents/skills` 时才选择它。未知 Agent 应先声明自己的 Skill 发现目录；随后为其建立专用 adapter，避免把文件写到猜测的位置。

适配器不得复制完整规范或知识页面。它只应告诉 Agent：知识根在哪里、应使用哪个 Skill、以及如何调用 `ffkb`。

## 后续适配器

Gemini、GitHub Copilot、Cursor、MCP 或其他集成，都应复用同一适配器边界，而不修改核心 schema 或工作流。
