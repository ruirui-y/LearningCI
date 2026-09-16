# LearningCI

> 用能力树、可验证评分、路线冻结和项目验收，把学习变成可持续执行的个人 CI 系统。

LearningCI 是一套面向“结果导向型学习者”的学习方法论。

它不以“看完多少页、学完多少课程、打卡多少天”作为掌握标准，而是把学习拆成一组可验证的能力节点，并通过解释、预测、实现、诊断、迁移、延迟复测和项目实战来证明真正掌握。

## 核心问题

很多学习者会出现这样的假进度：

- 看完一本书 = 100%
- 看完一个课程 = 100%
- 项目跑起来 = 100%
- 提前知道答案 = 100%

但真实能力可能只有 30%～50%。

LearningCI 的目标是把“进度条”从内容消费进度，改造成能力验证进度。

## 核心原则

1. **不以看完为完成，以通过能力测试为完成。**
2. **不以知道答案为掌握，以能独立推导、预测、实现、诊断和迁移为掌握。**
3. **一个学习日只推进一个最小能力节点。**
4. **路线冻结期间禁止重新规划整条学习路线。**
5. **任何新兴趣、新技术、新路线只进入 Parking Lot，不即时切换。**
6. **核心能力达到 80 分才视为工程掌握。**
7. **学习必须绑定参考项目，知识最终进入真实代码、测试、benchmark 或故障诊断。**
8. **正式评分必须留下证据，AI 不能凭印象随意打分。**
9. **7 日和 30 日复测用于区分“短期记住”与“长期掌握”。**
10. **允许探索成本，但禁止无限优化“最短学习路径”。**

## 仓库结构

```text
LearningCI/
├── README.md
├── ROADMAP.md
├── docs/
│   ├── 00-methodology.md
│   ├── 01-skill-tree.md
│   ├── 02-minimum-skill-node.md
│   ├── 03-scoring-system.md
│   ├── 04-daily-execution-protocol.md
│   ├── 05-route-freeze-and-review.md
│   ├── 06-project-driven-learning.md
│   ├── 07-ai-workflow.md
│   └── 08-checkin-app-spec.md
├── templates/
│   ├── skill-node.md
│   ├── daily-checkin.md
│   ├── route-review.md
│   ├── reference-project.md
│   └── ai-prompts.md
├── examples/
│   └── tcp-stream-framing.md
├── schemas/
│   ├── skill-node.schema.json
│   └── sample-node.json
└── app/
    └── README.md
```

## 推荐使用流程

```text
定义目标岗位 / 技术方向
        ↓
AI 生成能力大树
        ↓
拆成最小能力叶子节点
        ↓
冻结 14 天路线
        ↓
每天只推进一个节点
        ↓
Training → Verification → Score
        ↓
绑定参考项目落地
        ↓
7 日 / 30 日复测
        ↓
固定复盘日才允许调整路线
```

## 评分目标

- 0～39：知道/听说过
- 40～59：能解释并做基础实现
- 60～79：具有基础工程能力，但存在明显短板
- 80～89：工程掌握，可进入后续节点
- 90～100：能够设计、诊断、优化并解释取舍

核心节点默认目标：**>= 80**

## 当前阶段

当前仓库先固定方法论和协议。

下一阶段实现一个 Python + Qt 的桌面打卡应用，用软件强制执行：

- 每天只允许一个活动节点
- 路线冻结
- Parking Lot
- PASS / FAIL
- 节点评分
- 每日打卡
- 复测提醒
- 项目验收
- 学习记录
- 进度树
- 禁止普通学习日修改主路线

详见 `ROADMAP.md` 与 `docs/08-checkin-app-spec.md`。


## Desktop MVP v0.1.1

Python + PyQt6 + SQLite 桌面端已经开始实现。第一版故意不内置 AI API，而采用聊天式 AI 手工桥接：应用生成严格 Prompt，用户粘贴到任意 AI，再把 JSON 结果粘回 LearningCI。本地程序负责最终 PASS/FAIL，不允许 AI 修改冻结路线。

当前已实现：开始/结束学习、日/周/月专注时间、今日任务完成度、五维评分、失败不前进、延迟复测、Stable Score、日/周/月统计、Parking Lot 与只读 Frozen Plan。

v0.1.1 额外修正：

- NebulaRPC Master Plan 已作为冻结计划唯一来源重新编译为 68 个执行节点；
- `docs/history/*` 明确属于目标项目 NebulaRPC，而不是 LearningCI/docs；
- 粘贴试卷后，每道题自动显示独立回答框；
- 按钮补齐 hover / pressed / disabled / focus 状态；
- Stage 13~14 OPTIONAL 分支不阻塞主线。

运行方式见 `app/README.md`，路径说明见 `docs/10-nebularpc-plan-paths.md`。
