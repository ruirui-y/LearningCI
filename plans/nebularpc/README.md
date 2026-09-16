# NebulaRPC Learning Plan

本目录有两个不同职责的文件：

- `MASTER_PLAN.md`：NebulaRPC v0.2 人类总纲，保留完整背景、阶段目标、非目标和工程原则。
- `plan.json`：LearningCI 的冻结执行合同，把 Master Plan 编译为可逐日训练和 Verification 的最小节点。

## 路径规则

`plan.json` 中所有 `project_anchor.paths` 都相对于 **NebulaRPC 目标仓库根目录**，不是相对于 LearningCI。

例如：

```text
docs/history/MYMUDUO_AUDIT.md
```

实际意思是：

```text
NebulaRPC/docs/history/MYMUDUO_AUDIT.md
```

不是：

```text
LearningCI/docs/history/MYMUDUO_AUDIT.md
```

## 当前计划

v0.1.1 重新按照 `MASTER_PLAN.md` 编译为完整路线：

- Stage 0~2：Recovery Zone
- Stage 3：Event-Driven Async RPC 真正新起点
- Stage 4：C++20 Coroutine
- Stage 5：Exactly-Once Completion
- Stage 6~12：Multi-Reactor、资源治理、Client Runtime、Observability、Reliability、Performance、Framework Benchmark
- Stage 13~14：OPTIONAL，不阻塞主线
- Stage 15：v1.0 封版

详细节点清单见 `PLAN_OVERVIEW.md`。
