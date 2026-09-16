# 10. NebulaRPC Plan 与路径语义

## 为什么 LearningCI/docs 下没有 docs/history

`plan.json` 中出现的：

```text
docs/history/MYMUDUO_AUDIT.md
docs/history/GAME_RPC_AUDIT.md
docs/history/BREAKPOINT.md
```

**不是 LearningCI 仓库自己的 `docs/` 路径。**

它们来自 NebulaRPC Master Plan，含义始终是：

```text
<TARGET_PROJECT_ROOT>/docs/history/...
```

也就是目标项目 **NebulaRPC** 内的工程产物。

LearningCI 只负责监督和验收，不应该把 NebulaRPC 的项目文档混进自己的方法论文档目录。

## 两类文档必须分开

```text
LearningCI/
├─ docs/                       # LearningCI 方法论 / 软件说明
└─ plans/nebularpc/
   ├─ MASTER_PLAN.md           # NebulaRPC 人类总纲副本
   ├─ plan.json                # 从总纲编译出的冻结执行合同
   └─ target-project-templates/# 目标项目产物的空模板

NebulaRPC/
└─ docs/history/               # 真正由学习任务产生的项目文档
   ├─ MYMUDUO_AUDIT.md
   ├─ GAME_RPC_AUDIT.md
   └─ BREAKPOINT.md
```

## v0.1.1 的修正

Today 页面会明确显示：

> 目标项目产物（不是 LearningCI/docs）

并把路径渲染为：

```text
NebulaRPC/docs/history/...
```

`plan.json` 的每个节点也包含：

```json
{
  "project_anchor": {
    "project": "NebulaRPC",
    "path_base": "TARGET_PROJECT_ROOT",
    "paths": ["docs/history/MYMUDUO_AUDIT.md"]
  }
}
```

因此以后不会再把目标项目路径和 LearningCI 自己的文档目录混在一起。
