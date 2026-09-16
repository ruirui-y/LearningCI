# 09. LearningCI Desktop MVP v0.1.1

## 产品边界

第一版不是 AI Agent，也不是新的学习路线生成器。它只执行已经冻结的 `plan.json`：

```text
Frozen Plan
  -> Today Node
  -> Tasks
  -> Focus Session
  -> Verification
  -> Local PASS/FAIL Gate
  -> Review Queue
```

## UI

采用统一深色主题：深灰黑背景、卡片式布局、蓝色主操作、绿色 PASS、红色 FAIL。

颜色全部集中在 `learningci/theme.py`，按钮包含独立的：

- normal
- hover
- pressed
- disabled
- focus

状态，不在页面里散落颜色。

## Verification v0.1.1

粘贴试卷 JSON 后，不再使用“一个大回答框 + 自己记 Q1/Q2”的方式。

应用会自动生成：

```text
Q1 题目
[Q1 独立回答框]

Q2 题目
[Q2 独立回答框]

...
```

每道问题固定显示在对应回答框上方，回答按 `question id` 保存到 SQLite，评分 Prompt 也会按逐题 JSON 发送给 AI。

## 严格执行规则

1. Today 只显示一个 CORE 主线节点。
2. OPTIONAL 节点存在于 Frozen Plan，但不会阻塞主线，也不能在普通学习日临时激活。
3. Plan 页面只读。
4. 当日最低任务未全部完成，Verification 按钮不可用。
5. 学习计时未结束，Verification 不可用。
6. AI 只负责出题和五维评分；本地代码计算 PASS/FAIL。
7. FAIL 后节点不前进；必须生成不同试卷重新验证。
8. PASS 后按分数安排 3/7/14/30 日复测。
9. 复测 FAIL 不回退主线，但 Stable Score 会下降，并生成 Repair Review。
10. 新想法只允许进入 Parking Lot。
11. `plan.json` 首次导入后保存 SHA-256；静默修改会被拒绝。

## 专注统计

`focus_sessions` 保存每次开始/结束学习：

- Today：当天累计秒数
- Week：本周累计
- Month：本月累计

History 同时提供 Daily / Weekly / Monthly：

- Focus Time
- Task Completion
- Average Verification Score
- Exams
- Passed

执行指标和能力分不会互相补偿。

## NebulaRPC 路径语义

`plan.json` 中：

```text
docs/history/...
```

始终表示：

```text
NebulaRPC/docs/history/...
```

不是 `LearningCI/docs/history/...`。

详见 `docs/10-nebularpc-plan-paths.md`。
