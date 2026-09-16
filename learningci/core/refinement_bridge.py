from __future__ import annotations

import json
import shutil
import zipfile
from datetime import datetime
from pathlib import Path

from learningci.config import (
    DEFAULT_BUNDLE_DIR,
    MASTER_PLAN_PATH,
    PLAN_DIR,
    REFINE_EXPORT_DIR,
    REFINE_PROPOSED_DIR,
    REPO_ROOT,
)
from learningci.core.bundle_loader import validate_bundle


def _now_stamp() -> str:
    return datetime.now().strftime("%Y%m%d-%H%M%S")


def _json_text(data: object) -> str:
    return json.dumps(data, ensure_ascii=False, indent=2) + "\n"


def _request_text(node: dict, bundle: dict) -> str:
    return f"""# LearningCI 节点细化请求

你现在是 **LearningCI 节点细化器**。

这不是重新规划学习路线。你唯一的任务是：在 **不改变冻结节点定义** 的前提下，把节点 `{node['node_code']}` 细化成可以逐个打卡、逐个留证据的执行包，并生成首次固定正式验收试卷 V1。

## 当前节点

- Node：`{node['node_code']}`
- Title：{node['title']}
- 阶段：Stage {node['stage']}
- 优先级：{node['priority']}
- 目标分数：{node['target_score']}

能力定义：

> {node['capability']}

## 绝对禁止修改的内容

以下内容来自 `plan.json`，属于路线合同：

- Node ID / 顺序 / Stage / Priority / Title
- 能力定义 capability
- must_learn
- out_of_scope
- project_anchor
- 评分门槛

你不能新增 Stage、删除节点、调整路线、引入相邻技术，也不能因为你认为存在更好的方案而改变学习目标。

## 细化标准

1. 把粗任务拆成 **真正可判定完成/未完成的叶子任务**，不能只是把“阅读某文件”机械拆成上半段/下半段。
2. 每个叶子任务必须包含：
   - `id`
   - `title`
   - `detail`
   - `purpose`
   - `estimated_minutes`
   - `required`
   - `evidence_required`
   - `evidence_fields`
   - `done_when`
3. 单个叶子任务通常控制在 5~30 分钟；确实需要更长时可以超过，但必须是一个不可再自然拆分的验证动作。
4. `done_when` 必须是可以逐条检查的完成条件。
5. 涉及真实源码审计/实现/诊断时，必须要求源码路径、函数名、测试、日志、抓包、benchmark、git grep / IDE 调用链等可验证证据。
6. 任务只允许服务于本节点能力定义，严禁触碰 `out_of_scope`。
7. 项目产物只能来自 `project_anchor` 已允许的路径或证据类型，不能临时扩张工程范围。
8. 首次固定试卷必须严格 5 题，总分 100：
   - explanation 15
   - prediction 15
   - implementation 25
   - diagnosis 25
   - transfer 20
9. implementation / diagnosis 必须要求可验证工程证据。
10. 首次固定试卷从节点开始就允许预览；首次未通过后继续使用同一张 V1，只有延迟复测才换题。
11. 任务标题、任务组标题、说明文字、试题正文尽量使用中文；必要的 C++/Linux/API 名称保留英文。
12. **禁止为了“收束”再增加重复总结任务。** 如果前面的叶子任务已经逐项回答并留下证据，不要再要求“形成审计结论 / 再写一遍总结 / 把上面内容重新归纳到文档”。
13. 每个有实际学习内容的任务组应当可以直接用其叶子任务回答与证据进行“小节 AI 验收”。任务组可写 `assessment_required: true`；LearningCI 会把整个小节的现有记录导出给 ChatGPT 打分。
14. 如果项目确实需要长期资产文档，优先由已有叶子证据自动汇总或在最终项目阶段生成，不要把重复抄写当成学习任务。

## 输出要求

只返回一个合法 JSON，结构必须符合 `04-返回文件结构约束.json`。

- `node_id` 必须仍为 `{node['node_code']}`
- `node_title` 必须仍为 `{node['title']}`
- `compiler.status` 必须写 `REVIEWED`
- `verification_paper.paper_id` 建议保持 `{node['node_code']}-V1`
- 不要附带 Markdown fence，不要解释，不要输出第二份方案。

## 当前粗执行包状态

当前叶子任务数量：{bundle.get('task_count', 0)}
当前执行包质量状态：{bundle.get('compiler', {}).get('status', 'GENERATED')}

你可以保留合理任务，也可以重组、合并、拆分；但不能改变节点本身。
"""


def _project_background_text() -> str:
    path = PLAN_DIR / "项目背景与求职证据.md"
    if path.exists():
        return path.read_text(encoding="utf-8")
    return """# 项目背景\n\n本文件缺失。细化时仍必须以节点定义与总计划为唯一学习路线依据。\n"""


def export_refinement_package(
    node: dict,
    bundle: dict,
    previous_context: dict,
    schema_path: Path,
    output_path: Path | None = None,
) -> Path:
    """Create a self-contained ZIP that can be uploaded to a chat AI without any API integration."""
    validate_bundle(bundle, node["node_code"])
    REFINE_EXPORT_DIR.mkdir(parents=True, exist_ok=True)
    output = Path(output_path) if output_path else REFINE_EXPORT_DIR / f"{node['node_code']}_节点细化包_{_now_stamp()}.zip"
    output.parent.mkdir(parents=True, exist_ok=True)

    master_text = MASTER_PLAN_PATH.read_text(encoding="utf-8") if MASTER_PLAN_PATH.exists() else ""
    schema_text = Path(schema_path).read_text(encoding="utf-8")
    node_contract = {
        "id": node["node_code"],
        "stage": node["stage"],
        "order": node["order_index"],
        "title": node["title"],
        "capability": node["capability"],
        "priority": node["priority"],
        "target_score": node["target_score"],
        "tasks": node["tasks"],
        "must_learn": node["must_learn"],
        "out_of_scope": node["out_of_scope"],
        "scoring": node["scoring"],
        "project_anchor": node["project_anchor"],
    }

    clean_bundle = {k: v for k, v in bundle.items() if not str(k).startswith("_")}
    clean_bundle = json.loads(json.dumps(clean_bundle, ensure_ascii=False))
    clean_bundle.setdefault("compiler", {})["note"] = (
        "这是 LearningCI 自动生成的基础执行包。接近执行窗口时通过导出/导入方式交给 ChatGPT 单节点细化；"
        "不使用任何模型 API，不允许改变 plan.json 路线。"
    )
    files: dict[str, str] = {
        "01-节点细化要求.md": _request_text(node, bundle),
        "02-当前节点定义_禁止修改.json": _json_text(node_contract),
        "03-当前节点执行包.json": _json_text(clean_bundle),
        "04-返回文件结构约束.json": schema_text if schema_text.endswith("\n") else schema_text + "\n",
        "05-NebulaRPC总计划.md": master_text,
        "06-前置节点学习结果.json": _json_text(previous_context),
        "07-项目背景与求职证据.md": _project_background_text(),
        "08-返回文件说明.txt": (
            "把这个 ZIP 上传给 ChatGPT，并说：‘按 01-节点细化要求.md 细化当前节点。’\n"
            "ChatGPT 返回一个 JSON 后，将它保存为："
            f"{node['node_code']}_已细化.json\n"
            "然后回到 LearningCI → 节点准备 → 导入细化结果。\n"
            "不要手工覆盖 plan.json；不要手工修改已经冻结的节点执行包。\n"
        ),
    }
    with zipfile.ZipFile(output, "w", zipfile.ZIP_DEFLATED) as zf:
        for name, text in files.items():
            zf.writestr(name, text.encode("utf-8"))
    return output


def stage_candidate_file(source: Path, node_code: str) -> tuple[dict, Path]:
    raw = Path(source).read_text(encoding="utf-8")
    data = json.loads(raw)
    validate_bundle(data, node_code)
    if str(data.get("node_title", "")).strip() == "":
        raise ValueError("导入结果缺少 node_title")
    compiler = data.setdefault("compiler", {})
    compiler["status"] = "REVIEWED"
    compiler["type"] = "ChatGPT 手工导出导入细化"
    compiler["note"] = "由 LearningCI 导出细化包，经聊天式 AI 生成后人工导回；未使用任何模型 API。"
    REFINE_PROPOSED_DIR.mkdir(parents=True, exist_ok=True)
    staged = REFINE_PROPOSED_DIR / f"{node_code}_已细化_{_now_stamp()}.json"
    staged.write_text(_json_text(data), encoding="utf-8")
    return data, staged


def backup_bundle_file(node_code: str, revision: int) -> Path | None:
    source = DEFAULT_BUNDLE_DIR / f"{node_code}.json"
    if not source.exists():
        return None
    history = DEFAULT_BUNDLE_DIR / "历史版本"
    history.mkdir(parents=True, exist_ok=True)
    target = history / f"{node_code}_第{revision}版_{_now_stamp()}.json"
    shutil.copy2(source, target)
    return target


def install_reviewed_bundle(node_code: str, data: dict) -> Path:
    validate_bundle(data, node_code)
    target = DEFAULT_BUNDLE_DIR / f"{node_code}.json"
    target.write_text(_json_text(data), encoding="utf-8")
    return target
