# Changelog

## v0.3.3 - 2026-09-16

- Fix Windows WinError 32 when updating `sync/learningci.db`.
- Write SQLite backup directly to the destination instead of unlink/rename replacement.
- Validate generated snapshots with `PRAGMA integrity_check`.

## v0.2.0 - 2026-09-16

- 新增 Detailed Node Bundle 架构：路线与执行细节分离。
- 为 68 个 NebulaRPC 节点预生成冻结执行包，共 1065 个叶子任务。
- `NRPC-S0-01` 人工细化为 41 个可打卡叶子任务。
- Today 页面改为可展开任务树 + 任务详情面板。
- 每个叶子任务支持独立开始/暂停计时、证据记录和完成打卡。
- 总专注时间继续按日/周/月汇总，叶子任务时间作为分类统计，不重复计时。
- 固定 Verification 试卷从节点开始就可预览，不再等任务完成后临时生成。
- 首次 Verification FAIL 后复用同一张冻结试卷，只创建新的 Attempt。
- Retest 继续要求换场景、换数据、换代码。
- Node Bundle 和 Verification Paper 导入后记录 SHA-256，禁止静默修改。
- 新增 Data Sync 页面，使用 SQLite backup API 生成 `sync/learningci.db`。
- 支持从同步快照恢复；本地 DB 不存在时首次启动自动恢复。
- `.gitignore` 忽略 live DB，但允许提交 `sync/learningci.db`。
- 新增可选 DeepSeek Node Compiler：一次只细化一个冻结节点，输出到 proposed/，不自动改路线。
- 新增 node bundle schema、同步说明和 v0.2.0 设计文档。
- 核心测试扩展到 15 项，覆盖 bundle 冻结、固定试卷复用、叶子任务证据 Gate、任务计时与 SQLite 快照恢复。

## v0.1.1 - 2026-09-16

- 修正 NebulaRPC 项目路径与 LearningCI/docs 的边界。
- 根据 MASTER_PLAN 生成更完整的 68 节点冻结路线。
- Verification 粘贴试卷后自动按题生成独立回答框。
- 补充按钮 hover / pressed / focus / disabled 状态。
- 增加计划 Hash 校验与本地数据重置脚本。

## v0.1.0

- 初始 PyQt6 + SQLite Desktop MVP。
- Today / Frozen Plan / Reviews / History / Parking Lot。
- 总专注计时、五维评分、PASS/FAIL、复测队列。
