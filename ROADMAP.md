# Roadmap

## Phase 0 — 方法论冻结

目标：把 LearningCI 的规则先固定，不急着写软件。

完成条件：

- 最小能力节点协议稳定
- 0～100 评分体系稳定
- Daily Learning CI Prompt 稳定
- 14 天路线冻结规则稳定
- Reference Project 验收规则稳定
- AI 评分必须有证据的规则稳定

## Phase 1 — PyQt 打卡 MVP

技术建议：

- Python 3.11+
- PySide6 或 PyQt6
- SQLite
- SQLAlchemy（可选）
- pytest
- matplotlib（仅用于趋势图，可选）

MVP 功能：

1. 今日唯一节点
2. 开始学习 / 结束学习
3. 每日计划
4. PASS / FAIL
5. 五维评分录入
6. Parking Lot
7. 14 天路线锁定
8. 复测日期
9. 项目绑定
10. 每日打卡历史

MVP 暂不做：

- 云同步
- 多设备
- AI 自动调用
- 复杂图表
- 账号系统
- 社交
- 排行榜

## Phase 2 — 能力树与项目系统

增加：

- 技能树可视化
- 前置依赖
- 节点解锁
- 节点拆分
- Reference Project
- Benchmark 记录
- 故障注入记录
- 工程产物链接
- Git commit / test evidence 记录

## Phase 3 — AI Learning CI

增加：

- AI 生成能力树
- AI 生成叶子节点
- AI 每日计划
- AI Training Test
- AI Verification Test
- AI 7 日 / 30 日复测
- AI 评分
- AI 评分证据
- AI 自动把新兴趣放入 Parking Lot

## Phase 4 — 自动化验证

长期方向：

- 自动运行 pytest
- 自动读取 benchmark
- 自动读取 Git commit
- 自动读取测试报告
- 自动对比 Reference Project
- 自动计算性能达到参考实现的百分比

目标不是做一个“学习打卡软件”，而是逐步变成真正的 **Human CI / Learning CI**。


## 当前实现状态（v0.1）

已进入 Phase 1，可运行代码已经落地：

- [x] SQLite Schema / Repository Service
- [x] Frozen Plan JSON + SHA-256 防静默修改
- [x] Today 唯一节点
- [x] 开始学习 / 结束学习
- [x] 日 / 周 / 月专注时间
- [x] 每日任务 Checklist / 完成度
- [x] Manual AI Test / Grade Bridge
- [x] 本地 PASS/FAIL Gate
- [x] FAIL 不前进
- [x] Review Queue / Stable Score
- [x] 日 / 周 / 月 History
- [x] Parking Lot
- [ ] DeepSeek API Provider（v0.2 再做）
- [ ] 自动读取 Git/Test/Benchmark Evidence（后续）
