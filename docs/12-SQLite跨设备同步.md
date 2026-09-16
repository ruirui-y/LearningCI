# 12. SQLite 跨电脑同步

LearningCI 明确区分：

```text
data/learningci.db
```

与：

```text
sync/learningci.db
```

## data/learningci.db

这是程序运行时数据库：

- SQLite 可能使用 WAL/SHM；
- 程序运行时持续写入；
- 不进入 Git。

## sync/learningci.db

这是 Git 可提交的一致性快照：

- 通过 SQLite `backup()` API 生成；
- 不直接复制正在运行的数据库文件；
- `.gitignore` 明确允许它进入 Git。

## 标准工作流

电脑 A：

```text
学习完成
↓
数据同步
↓
生成 / 更新 Git 同步快照
↓
git add sync/learningci.db
git commit
git push
```

电脑 B：

```text
git pull
↓
数据同步
↓
从同步快照恢复
↓
继续学习
```

如果电脑 B 本地根本没有 `data/learningci.db`，首次启动时会自动从 `sync/learningci.db` 恢复。

## 单写者规则

SQLite 文件不是可文本 merge 的数据格式。

禁止：

```text
电脑 A 学习 2 小时
电脑 B 同时学习 3 小时
↓
两边分别 commit learningci.db
↓
尝试 git merge
```

正确规则：**同一时间只让一台电脑成为 writer。**

## 数据大小

LearningCI 主要保存文本、时间、状态和 JSON，不保存视频/图片等大对象。

数据库达到几十 MB 甚至几百 MB 对 SQLite 都不是问题，因此不设置 10 MB 人工上限。真正需要控制的是同步纪律，而不是数据库大小。

## 隐私

SQLite 会包含：

- 你的考试回答
- AI 评分
- 学习时间
- 弱点
- 想法停车场
- 任务证据

如果主 LearningCI 仓库是 Public，建议把 `sync/learningci.db` 放在单独 Private 数据仓库，而不是公开提交。
