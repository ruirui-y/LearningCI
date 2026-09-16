# 08. PyQt 严格打卡应用需求草案

## 1. 目标

不是做普通“习惯打卡”。

而是做一个强制执行 LearningCI 规则的桌面工具。

核心目标：

> 降低临时放弃、跳过节点、优化路线和偷跑到新技术的机会。

## 2. 首页

首页只显示：

### Today

- 今日唯一节点
- 当前分数
- 今日状态
- 今日可用时间
- Start Session
- Finish Training
- Start Verification
- PASS / FAIL

### 禁止

首页不展示大量后续节点，避免诱发跳路线。

## 3. 每日流程

```text
打开 App
  ↓
今日节点已锁定
  ↓
Check In
  ↓
显示今天计划
  ↓
Training
  ↓
Verification
  ↓
记录评分
  ↓
PASS / FAIL
```

## 4. 路线锁

普通学习日：

- 能看当前节点
- 能看最近前置节点
- 不能修改主路线

修改路线按钮默认禁用。

只有 Route Review 窗口解锁。

## 5. Parking Lot

任何临时想法只允许：

- 输入一句话
- 自动记录时间
- 不弹出进一步操作

例如：

```text
2026-09-16 21:34
以后研究 io_uring
```

输入后立即返回当前节点。

## 6. 打卡

记录：

- 开始时间
- 结束时间
- 有效学习分钟
- 今日是否执行
- 是否完成 Verification
- PASS / FAIL

注意：

连续打卡只属于 Execution Score，不能提升 Capability Score。

## 7. 评分

UI 五项：

- Explanation / 15
- Prediction / 15
- Implementation / 25
- Diagnosis / 25
- Transfer / 20

自动计算：

- 总分
- 是否满足门槛
- PASS / FAIL

## 8. 复测

节点 PASS 后自动建立：

- +7 days
- +30 days

到期显示 RETEST_DUE。

## 9. Emergency Unlock

如果用户想提前修改路线：

点击 Unlock 后：

1. 输入原因
2. 选择证据
3. App 记录申请
4. 24 小时后按钮才真正可用
5. 再次确认

目的是防止冲动改计划。

## 10. 数据模型

最低实体：

- SkillTree
- SkillNode
- DailySession
- ScoreRecord
- ParkingLotItem
- RouteFreeze
- RouteReview
- ReferenceProject
- ProjectBenchmark
- Retest

## 11. MVP 技术

建议：

- Python 3.11+
- PySide6
- SQLite
- dataclasses / pydantic（可选）
- pytest

第一版完全本地化：

- 无账号
- 无服务器
- 无云同步
- 无 AI API

先证明执行机制有效，再增加复杂功能。
