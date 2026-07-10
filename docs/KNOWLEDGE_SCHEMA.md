# 知识库 Schema

## 源目录结构

```text
knowledge.json
router.json
INDEX.md              # 仅供人读展示；router.json 仍是机器真相源
pages/
  standards/
  projects/
  features/
  decisions/
graph/
  nodes.jsonl
  edges.jsonl
pending.jsonl
logs/
cache/                 # 派生产物，不是写回真相源
```

## 页面契约

页面使用受限的 frontmatter，并包含以下章节：

- `## compiled_truth`：默认加载的简短当前结论。
- `## key_entities`：可选的稳定图实体 ID。
- `## relations`：可选的人类可读关系摘要。
- `## timeline`：仅追加的历史。
- `## reference_details`：按需加载的冷细节。

解析器仅支持已记录的标量与一维列表 frontmatter，不承诺兼容完整 YAML。

## 图契约

节点表示以稳定 ID 标识的当前状态，可进行事务更新。边是仅追加的关系事件。已废弃节点仍作为历史可查询，并应通过 superseding relation 指向替代节点。

每条边的两个端点都必须存在。每个页面节点必须与页面 ID、相对路径、状态和更新日期一致。`ffkb lint` 会校验这些约束。

## 学习分级

- L0：没有可长期复用的价值，不写入。
- L1：追加待确认的证据事件。
- L2：审查后更新 canonical page、graph 与审计记录，然后只重建一次派生 cache，并回查对应意图。
