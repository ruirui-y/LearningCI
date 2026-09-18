## v0.3.11 - 2026-09-18

Validation performed after relaxing the formal Verification gate:

```text
python -m compileall -q learningci tests
PASS

python -m unittest discover -s tests -v
45 tests
45 / 45 PASS
```

Validated behaviors:

- 70 total points advances the mainline even when an old per-dimension minimum is missed.
- 69 points still remains on the current node.
- 80+ plus all old dimension minimums is reported as stable/mastered.
- 80+ with a weak dimension advances but remains non-mastered.
- Existing databases are reconciled: an old initial Verification score >=70 that was previously stored as FAILED is promoted to PASSED and the next node becomes active.
- Delayed reviews are scheduled when an old trapped score is promoted.
- Section assessment threshold remains unchanged at 80.

PyQt visual smoke was not executed in this environment; Python sources compile successfully and source/layout regression tests pass.

# Validation

## v0.3.10 - 2026-09-17

- `python -m compileall -q learningci tests`：PASS
- `python -m unittest discover -s tests -v`：41 / 41 PASS。
- 新增静态布局回归测试：正式测试必须存在唯一整页 `page_scroll`，不得重新引入 `question_scroll` / `repair_scroll` 两个嵌套滚动容器。
- 当前环境未安装 PyQt6，因此未执行真实 GUI/offscreen 启动；UI 源码通过 compileall，需在本地 PyQt6 环境做最终视觉确认。

## v0.3.9 - 2026-09-17

- `python -m compileall -q learningci tests`：PASS
- `python -m unittest discover -s tests -v`：39 / 39 PASS
- 新增覆盖：结构化修正 issues 持久化、旧评分 fallback 修正卡片、`issues_json` schema migration。
- 当前环境未执行 PyQt6 GUI smoke test；UI Python 源码已通过 compileall。

## v0.3.8 - 2026-09-17

已执行：

```text
python -m compileall -q learningci tests
python -m unittest discover -s tests
```

结果：

```text
35 tests
OK
```

本轮新增/覆盖重点：

- `NRPC-S0-01` 正式试卷升级为 `V1.3`，旧未评分草稿自动 `SUPERSEDED` 且不产生 FAIL。
- `NRPC-S0-02` 正式试卷升级为 `V1.2`。
- 历史审计节点 implementation 使用 `requires_answer=false`，不再要求学习者重复整理源码证据。
- LearningCI 能从 SQLite 自动汇总已完成叶子任务的 `source_path / function_name / evidence_note` 与小节验收结果。
- Reviewer 评分提示词会自动注入上述既有工程证据。
- 历史审计出题 Prompt 强制 Diagnosis 使用具体故障场景，并禁止正式测试重复采证。
- 五维评分 Gate、固定试卷复用、叶子任务证据、小节验收失效机制、SQLite 快照等原有测试继续通过。

当前生成环境未安装 PyQt6，因此无法执行真实 GUI/offscreen 启动 smoke test。`dialogs.py` 等 UI 源码已通过 `compileall`；需要在用户本地 PyQt6 环境做最终视觉验收。