# Roadmap

## v0.2.0 — Detailed Execution

已完成：

- Detailed Node Bundle
- 叶子任务树
- 每任务独立计时
- 证据字段
- 固定 Verification 预览
- FAIL 复用同一 Verification
- Retest 换题
- SQLite Git Snapshot
- 可选 DeepSeek 单节点 Compiler

## v0.2.x — 使用反馈修正

只根据真实使用中暴露的问题修：

- Today 页面布局
- 叶子任务粒度过粗/过细
- 证据字段不足
- 固定试卷质量
- Data Sync 操作体验

禁止在这个阶段引入：

- 账号系统
- 云服务器
- Agent 框架
- RAG
- 排行榜
- 社交功能

## v0.3.0 — Node Compiler 工具化

候选：

- UI 内选择尚未开始节点
- DeepSeek API 单节点编译
- JSON Validator
- Diff Preview
- 人工确认后创建“下一计划版本”

重要：Compiler 只能细化节点，不能修改路线。

## v0.4.0 — 自动工程证据

候选：

- 自动执行 pytest / ctest
- 读取 Git commit
- 收集 benchmark 结果
- 读取日志文件
- 自动绑定 artifact evidence

## 长期

LearningCI 最终目标仍然是 Human CI：

```text
能力节点
→ 训练
→ 工程证据
→ Verification
→ PASS/FAIL
→ Retest
→ Stable Mastery
```
