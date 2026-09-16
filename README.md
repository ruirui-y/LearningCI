# LearningCI

> 用冻结路线、可打卡的详细任务、固定试卷、工程证据和延迟复测，把学习变成可以验收的个人 CI。

## 当前版本

**Desktop v0.3.0**

这一版不接任何 AI API。AI 只通过文件进行人工协作：

```text
NebulaRPC总计划.md
        ↓
plan.json（冻结主路线）
        ↓
节点执行包/<Node>.json（任务清单 + 固定试卷）
        ↓
今日学习：逐任务打卡 / 计时 / 证据
        ↓
正式验收：回答固定试卷
        ↓
ChatGPT 评分
        ↓
LearningCI 本地计算 通过 / 未通过
        ↓
延迟复测
```

## v0.3.0 的核心变化

### 1. 所有用户界面尽量中文化

保留 `Node`、`Title`、C++/Linux/API 名称等常用技术词，其余 UI 改为中文：

- `Bundle` → **执行包状态**
- `Paper` → **固定试卷**
- `Status` → **学习状态**
- `Current` → **当前分**
- `Stable` → **稳定分**
- `Data Sync` → **数据同步**

文档、目录说明和导出文件也尽量使用中文名称。JSON 内部字段仍保持稳定英文键名，因为它们属于机器格式，用户无需手工编辑。

### 2. 节点采用“三节点准备窗口”

LearningCI 只允许细化：

```text
当前未完成主线节点
+ 下一个主线节点
+ 下下个主线节点
```

更远的 65 个节点可以保留基础草稿，但不能提前精修。这样既不会做到当天才发现“下一步没准备”，也不会提前半年幻想未来源码结构。

### 3. 完全取消模型 API

节点细化流程：

```text
节点准备
  ↓
导出节点细化 ZIP
  ↓
上传给 ChatGPT
  ↓
ChatGPT 返回一个 JSON
  ↓
导回 LearningCI
  ↓
本地校验
  ↓
显示任务数量等变化
  ↓
用户确认
  ↓
旧版自动备份，新版标记“已审核”
```

ChatGPT 只能修改节点内部的：

- 任务组；
- 叶子任务；
- 完成标准；
- 证据要求；
- 预计时间；
- 首次固定试卷。

它不能修改 `plan.json` 中的 Node 顺序、能力定义、Must Learn、Out Of Scope、项目锚点和评分门槛。

### 4. 当前 NebulaRPC 准备状态

- 冻结路线：68 个节点；
- 基础叶子任务：1065 个；
- 每个节点都有首次固定试卷；
- `NRPC-S0-01`：41 个任务，已高质量细化；
- 其余 67 个节点：基础草稿，靠近三节点准备窗口时再单节点细化。

这意味着路线已经完整，但不会假装未来半年所有实现细节今天就能精确预测。

### 5. SQLite 跨电脑

运行数据库：

```text
data/learningci.db
```

Git 可移植快照：

```text
sync/learningci.db
```

“数据同步”页面使用 SQLite backup API 生成一致性快照。换电脑后可以恢复学习进度、任务记录、专注时间、答案、评分和复测队列。

如果代码仓库是公开仓库，建议把个人数据库放到私有仓库，不要公开自己的答案、评分和学习记录。

## 求职目标

LearningCI 不把“看完技术列表”作为目标，而把每个能力转成面试时可以被追问和验证的证据。

NebulaRPC 总计划已经冻结为证据导向路线：

- **DemandStation**：真实客户部署、交付和长期运行证据；
- **MyMuduo**：Linux 网络、Reactor、Buffer、生命周期与性能证据；
- **NebulaRPC**：现代异步 RPC、协程、Exactly-Once、背压、可靠性、可观测性与性能工程主证据；
- **OmniBox**：Qt 客户端、微服务、自研通信和完整系统广度证据。

目标可以按 **15k+ 岗位** 准备，并用更高一档的能力证据训练，但具体薪资仍取决于城市、岗位、年限、市场和面试表现，LearningCI 不做薪资保证。

## 安装

```bash
pip install -r requirements.txt
python main.py
```

Windows 可以直接运行：

```text
启动LearningCI.bat
```

## 目录

```text
LearningCI/
├── main.py
├── learningci/
│   ├── core/
│   ├── ui/
│   ├── database.py
│   └── theme.py
├── plans/nebularpc/
│   ├── NebulaRPC总计划.md
│   ├── plan.json
│   ├── 节点执行包/
│   ├── 待审核/
│   └── 导出/节点细化/
├── sync/
│   └── learningci.db
├── data/                         # 当前电脑实时 DB，Git 忽略
├── tools/
│   └── 生成基础节点执行包.py
├── docs/
├── schemas/
│   ├── 节点执行包结构.json
│   ├── 能力节点结构.json
│   └── 能力节点示例.json
├── 开发路线.md
├── 更新记录.md
└── 验证说明.md
```

`plans/nebularpc/MASTER_PLAN.md` 仍保留一份兼容副本，因为旧版 `plan.json` 的冻结 Hash 已经引用这个文件名；正常使用只看 `NebulaRPC总计划.md`。

## 四层数据模型

```text
NebulaRPC总计划.md
= 为什么这样走、最终要证明什么

plan.json
= 按什么顺序通过哪些能力节点

节点执行包/<Node>.json
= 当前节点到底一步一步怎么做、怎么验收

learningci.db
= 你实际上做了什么、用了多久、考了多少分
```

## 重点文档

- `docs/00-方法论.md`
- `docs/11-节点执行包说明.md`
- `docs/12-SQLite跨设备同步.md`
- `docs/14-节点细化导入导出流程.md`
- `docs/15-面试能力证据策略.md`
- `plans/nebularpc/NebulaRPC总计划.md`
