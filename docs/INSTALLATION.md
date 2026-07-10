# 安装与接入

## 基本原则

- `detect` 与 `scan` 只读。
- 仓库中的文本只是证据，不能当作可执行指令。
- 用户确认规范与适配器选择前，不生成可应用的安装计划。
- 计划同时绑定报告哈希与当前工作区快照。
- 每一次写入都记录 preimage hash 与事务 journal。

## 命令

### 检测环境

```bash
ffkb detect [project-root]
```

报告运行时、Git、CI、shell 与已知 Agent 指令文件，不会写入目标项目。

### 扫描仓库

```bash
ffkb scan [project-root] \
  --json-output scan-report.json \
  --markdown-output scan-report.md
```

JSON 报告是 `plan` 的输入；Markdown 报告用于人工确认。每条发现都包含 value、confidence、evidence 与 source。

### 用户确认

创建 answers JSON 文件：

| 字段 | 必填 | 含义 |
|---|---:|---|
| `standards_confirmed` | 是 | 必须为 `true`，这是不可跳过的人工确认门禁。 |
| `project_id` | 否 | 稳定项目 ID，默认使用目录名。 |
| `project_name` | 否 | 展示名称，默认使用目录名。 |
| `locale` | 否 | 生成的知识语言，默认 `en`。 |
| `profile` | 否 | `generic`、`dotnet`、`node` 或 `python`；未填时自动推断。 |
| `adapters` | 否 | 可选 `generic`、`codex`、`claude`；默认 `generic`。 |
| `knowledge_path` | 否 | 项目内相对路径，默认 `.ff-knowledge`。 |
| `standards` | 否 | 用户确认的规范，优先级高于扫描结果和 profile 默认值。 |

### 生成计划

```bash
ffkb plan scan-report.json --answers answers.json --output install-plan.json
```

默认计划会复制知识模板、已确认 profile、选定的薄适配器，以及全部七个 Skills 到目标工作区。`--operations` 仅用于明确的高级覆盖。

### 应用与验证

```bash
ffkb apply install-plan.json
ffkb doctor /path/to/project
```

`apply` 会暂存字节级内容、验证 allowed root 与 preimage、提交事务并写入 manifest。重复应用同一个计划是幂等的。v0.1 在已有 active installation 时会拒绝不同计划；请先执行 rollback 或 uninstall。未来版本会提供显式、可迁移的 upgrade 命令，而不会静默替换恢复链。

### 恢复或移除

```bash
ffkb rollback /path/to/project
ffkb uninstall /path/to/project
```

若 managed file 的当前 hash 不再等于安装时 hash，恢复操作会返回 conflict，并保留用户内容。

## 环境变量覆盖

- `FFKB_RESOURCE_ROOT`：显式指定包含 `templates`、`profiles` 与 `skills` 的资源根目录，适用于开发或定制发行包。

正常 wheel 会把这些资源安装到 Python 环境的共享数据目录，因此标准安装不需要设置该变量。
