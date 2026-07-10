# Skills 使用指南

Skills 是给 Agent 的短流程说明，不是项目知识的副本。它们应通过 `ffkb` 查询 canonical knowledge，而不是把整套规范塞进提示词。安装后，Generic/Codex 从 `.agents/skills` 发现 Skills，Claude Code 从 `.claude/skills` 发现 Skills。

本页面向中文使用者说明触发场景；canonical `SKILL.md` 保持简洁英文，以便不同 Agent 和 Windows 终端稳定读取与校验。

## 选择哪个 Skill

| Skill | 什么时候使用 | 不适用的情况 |
|---|---|---|
| `ff-bootstrap` | 首次接入仓库；用户说“初始化、导入、安装、适配开发体系”；需要扫描并征求确认。 | 日常功能开发或只查询知识。 |
| `ff-develop` | 实现功能、修复 bug、重构、架构调整，或需要选择开发流程。 | 只做安装、最终验证或独立评审。 |
| `ff-knowledge` | 开发、排查、评审前需要了解项目规范、模块归属、架构事实或已有决策。 | 已经有足够的当前源码证据，且不需要查询知识库。 |
| `ff-learn` | 任务验证完成后，用户要求“记住”；或形成稳定公共规范、架构决策、高风险规则。 | 临时发现、未验证推测、敏感信息或普通一次性结论。 |
| `ff-plan` | 需求模糊、跨层、高风险、长周期、多阶段或需跨会话交接的工作。 | 单点文案、微小样式、低风险局部修改。 |
| `ff-verify` | 准备声明完成、提交、发布或交付前，需要获取当前验证证据。 | 还未实现、尚未定义验收标准时。 |
| `ff-review` | 对重要变更做需求、回归、安全、复杂度与范围审查。 | 尚未完成实现或没有实际 diff/验证证据时。 |

## 推荐组合

```text
首次接入：ff-bootstrap

普通开发：ff-knowledge -> ff-develop -> ff-verify -> ff-review -> ff-learn

高风险或长周期：ff-knowledge -> ff-plan -> ff-develop -> ff-verify -> ff-review -> ff-learn
```

`ff-learn` 位于验证和审查之后：未经验证的结论不应写入知识库。`ff-bootstrap` 的确认门禁也不能被 `ff-develop` 绕过。

## 各 Skill 的关键边界

- `ff-bootstrap`：scan 只读；必须先展示证据和拟写文件，再等待明确确认。
- `ff-knowledge`：默认使用有预算的 `ffkb query`；低置信才改用 `ffkb search` 或读取冷路径。
- `ff-plan`：只有复杂度或风险需要时才创建持久任务文档，避免给小改动增加仪式负担。
- `ff-verify`：测试通过不等于规范审查通过；必须覆盖本次实际变化。
- `ff-review`：先报告 Critical/Important 发现；修复后重新验证与复审。
