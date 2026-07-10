# 架构说明

FF-LocalKnowledgeBase 将确定性程序能力与 Agent 提示词分离：CLI 负责可验证的读写边界，Skills 负责引导 Agent 选择正确流程。

```text
Agent 或用户
    |
    v
ffkb CLI 与版本化 JSON 契约
    |
    +-- 环境与仓库检测
    +-- 需确认的安装计划
    +-- 事务 apply、rollback 与 uninstall
    +-- 紧凑的本地知识查询与 lint
    |
    +-- 可移植 Agent Skills
    +-- 薄产品适配器
```

## 边界

- 核心：不包含任何公司、仓库、模型供应商、shell 或操作系统绝对路径知识的 Python 模块。
- 知识源：页面、机器路由、图节点/边与审计事件；它们才是可维护的真相源。
- 运行时状态：报告、cache、锁、事务与查询遥测。除仍需 rollback 的事务外，均可重新生成。
- Profile：由检测标记提出的技术栈建议；用户确认前不构成项目规范。
- 适配器：产品特定的文件名与发现提示；绝不拥有项目真相。

## 安装状态机

```text
NEW -> PREFLIGHTED -> SCANNED -> AWAITING_CONFIRMATION
    -> PLAN_APPROVED -> APPLYING -> VALIDATING -> INSTALLED

APPLYING 或 VALIDATING -> ROLLING_BACK -> ROLLED_BACK
                                      -> NEEDS_MANUAL_REPAIR
```

安装计划绑定扫描快照。仓库在扫描后发生变化时，`apply` 会拒绝旧计划，而不是猜测变更是否仍兼容。

## 查询模型

`router.json` 是机器真相源。`compact` 只从它派生有界的页面与图索引。`query` 返回当前的 `compiled_truth` 与少量关联边；完整历史属于按需读取的冷路径。普通查询不会写入命中遥测。
