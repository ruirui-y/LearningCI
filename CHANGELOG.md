## v0.3.11 - 2026-09-18

- 正式 Verification 主线推进阈值由 80 调整为 70，避免 Recovery Zone 被边界措辞和单维度门槛反复卡住。
- 80 分及原五维最低门槛保留为“稳定掌握”目标，不再作为下一节点解锁条件。
- 70~79 分显示“通过（带薄弱点）”，直接解锁下一节点；issues 保留到后续复测继续验证。
- 低于旧维度最低门槛只产生 advisory warning，不再覆盖 70+ 总分的主线通过结果。
- 自动迁移旧数据库：历史正式 Verification 若总分已经 >=70、但被旧 80/维度硬门槛判为 FAILED，升级后自动改为 PASSED 并推进主线，无需重新粘贴评分。
- 正式测试结果 UI 明确区分“通过（带薄弱点）”和“稳定掌握”。
- Reviewer 提示词明确 70 分推进 / 80 分稳定掌握，避免为了凑旧门槛放大扣分。
- 小节验收仍保持 >=80；本次只放宽节点正式 Verification 的主线推进门槛。

# Changelog

## v0.3.10 - 2026-09-17

### 正式测试改为整页滚动

- 正式测试/复测窗口改为单一外层纵向滚动页面：标题、计时、全部题目、回答框、评分按钮、结果和修正面板都处于同一个滚动区域。
- 删除题目区域自己的嵌套 `QScrollArea`，修正面板变长时不再把上方答题区压缩到几乎不可见。
- 删除正式测试修正面板 180~380px 的独立滚动视口；所有修正卡片按自然高度展开，由窗口总滚动条统一浏览。
- 粘贴 FAIL 评分后自动滚动到修正面板；重新打开或重新作答时保持/回到试卷顶部，方便直接继续作答。
- 保留每道题独立回答框、450ms 自动保存、正式测试计时与叶子任务跳转逻辑。
- 不修改冻结试卷、评分规则、数据库结构或学习路线。

## v0.3.9 - 2026-09-17

### 正式测试 FAIL 修正闭环

- 正式测试未通过后新增“修正面板”，不再只显示总分和 FAIL。
- 每个修正点独立展示：题号、维度、原回答、Reviewer 批注、正确机制/修正方向。
- Reviewer 评分 JSON 新增结构化 `issues`：`question_id / dimension / title / detail / correction / related_task_ids / severity`。
- `related_task_ids` 可直接定位回已经完成的叶子任务证据；关闭正式测试窗口后自动跳转到对应任务。
- 重新作答同一冻结试卷时保留上一轮修正面板，只补本次暴露的问题，不要求重学整个节点。
- 兼容 v0.3.8 及更早的失败评分：没有结构化 `issues` 时，会根据未达门槛的维度和已保存 Reviewer evidence 自动生成修正卡片。
- `score_records` 新增 `issues_json`，数据库启动时自动迁移，不需要删除现有 SQLite 数据。
- 不修改冻结路线、`plan.json` 或正式试卷 V1.3 内容。

## v0.3.8 - 2026-09-17

- 历史能力审计节点正式验收彻底去重：叶子任务阶段只采集一次源码路径、函数、调用链和证据备注，正式测试不再要求重复抄写。
- `NRPC-S0-01` 正式试卷升级为 `V1.3`：Explanation/Prediction 只考机制，Diagnosis 改为具体故障场景，Transfer 只考破坏性修改后的机制迁移。
- `NRPC-S0-02` 同步升级为 `V1.2`，采用相同的“叶子采证一次、正式测试不重复采证”规则。
- 历史审计节点的 implementation 改为系统自动复核项（`requires_answer=false`）：UI 不再显示回答框，用户无需再次整理四条源码证据。
- 复制 Reviewer 评分提示词时，LearningCI 自动附带当前节点已保存的全部叶子工程证据与小节验收结果；implementation 25 分直接基于这些已有证据评分。
- Reviewer 规则明确：Explanation/Prediction/Diagnosis/Transfer 不得因为用户没有重复写源码绝对路径、行号或粘贴代码而扣分；机制错了就直接批注机制。
- 历史审计 Diagnosis 必须由试卷给出具体故障/错误改动，不再要求学习者自己挑一个问题再写一份小型审计报告。
- 未评分的 `V1.2`/旧版草稿升级后自动标记为 `SUPERSEDED`，保留历史回答但不产生 FAIL。
- 自动测试扩展到 35 项。

## v0.3.7 - 2026-09-17

- 修正历史能力审计节点的正式试卷职责边界：学习者只回答技术事实、源码证据、机制预测、诊断和当前机制内迁移。
- `NRPC-S0-01` 正式试卷升级为 `V1.2`，移除要求学习者替 NebulaRPC 判断“复用/恢复/重做”的题目。
- `NRPC-S0-02` 正式试卷升级为 `V1.1`，避免重复要求编写审计文档或提前设计新的 Async RPC。
- 历史审计节点的 implementation 明确定义为“工程证据证明能力”，不强制重新写代码或重复总结文档。
- 历史审计节点的 transfer 改为基于破坏性修改/陌生时序的机制迁移题，不再要求做 Master Plan 分类。
- 正式出卷与评分 Prompt 新增历史审计节点专用职责规则，防止后续复测再次生成职责错位题目。
- 若升级前存在未评分的旧正式试卷草稿，自动标记为 `SUPERSEDED` 并创建新试卷作答，不产生 FAIL 或评分记录。
- 自动测试扩展到 34 项。

## v0.3.4 - 2026-09-16

- 重写 Today 页小节验收结果面板：总分与四维评分独立展示。
- AI 扣分项按 1、2、3、4… 独立卡片显示，不再挤成一段文本。
- 小节问题区域增加独立纵向滚动条，长反馈不会撑坏页面。
- 每条问题显示任务 ID、评分维度、短标题和完整错误说明。
- 支持从扣分卡片一键定位回对应叶子任务并展开任务组。
- 小节评分提示词新增结构化 issues 字段，同时兼容历史 weaknesses 字符串。
- 保留旧数据库评分兼容：历史评分也会自动解析成编号问题卡片。
- 新增小节反馈结构化解析测试，测试总数提升到 26 项。

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