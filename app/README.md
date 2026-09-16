# LearningCI Desktop v0.1.1

当前桌面端：

- PyQt6 深色 UI
- SQLite 本地数据库
- 冻结 `plan.json`
- 68 个 NebulaRPC 执行节点（含 OPTIONAL 研究分支）
- Today 唯一 CORE 节点
- 开始学习 / 结束学习
- 今日 / 本周 / 本月专注时间
- 每日任务 Checklist 与完成度
- Verification 粘贴试卷后自动生成“问题 + 独立回答框”
- Manual AI Bridge：复制出题 Prompt、粘贴试卷 JSON、复制评分 Prompt、粘贴评分 JSON
- 本地五维 PASS/FAIL Gate
- FAIL 不前进，可立即生成不同试卷
- PASS 自动安排延迟复测
- Review Queue / Stable Score
- 日 / 周 / 月历史统计
- Parking Lot

## 运行

```bash
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
python main.py
```

Windows 也可以直接运行：

```text
run.bat
```

## 从 v0.1.0 升级

v0.1.1 修正了 NebulaRPC 冻结计划，`plan.json` 的 SHA-256 会与旧数据库不同。

如果 v0.1.0 还没有正式学习数据，可以运行：

```text
reset_local_data.bat
```

它会先把旧数据库备份到：

```text
data/learningci.backup.db
```

再删除旧运行状态，让新计划重新导入。

如果旧数据库已经包含重要学习记录，不要直接 reset，应先保留备份。

## 计划文件

```text
plans/nebularpc/MASTER_PLAN.md   # 人类总纲
plans/nebularpc/plan.json        # 冻结机器执行合同
plans/nebularpc/PLAN_OVERVIEW.md # 人工审查 68 个节点
```

注意：`plan.json` 里的目标项目路径属于 **NebulaRPC 仓库**，不是 LearningCI 自己的 `docs/`。
