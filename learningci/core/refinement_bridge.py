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
from learningci.core.bundle_loader import normalize_bundle_task_groups, task_group_items, validate_bundle


def _now_stamp() -> str:
    return datetime.now().strftime("%Y%m%d-%H%M%S")


def _json_text(data: object) -> str:
    return json.dumps(data, ensure_ascii=False, indent=2) + "\n"


RECOMMENDED_LEAF_TASK_MIN = 20
RECOMMENDED_LEAF_TASK_MAX = 30
SOFT_LEAF_TASK_MIN = 15
SOFT_LEAF_TASK_MAX = 35

# Node refinement is intentionally narrow: AI may change task groups/task_count/compiler only.
# Stable bundle metadata and assessment policy must be copied from the current bundle unchanged.
PROTECTED_REFINEMENT_FIELDS = (
    "schema_version",
    "node_id",
    "node_title",
    "source_plan_version",
    "source_section",
    "task_policy",
    "verification_paper",
    "retest_policy",
)


def _task_count(bundle: dict) -> int:
    return sum(len(task_group_items(group)) for group in bundle.get("task_groups", []) or [])


def _group_outline(bundle: dict) -> str:
    lines: list[str] = []
    for group in bundle.get("task_groups", []) or []:
        lines.append(
            f"- `{group.get('id', '')}`：{group.get('title', '')}（{len(task_group_items(group))} 个叶子任务）"
        )
    return "\n".join(lines) if lines else "- （当前执行包没有任务组）"


def analyze_refinement_structure(original: dict, candidate: dict) -> dict:
    """Compare a refinement with the current bundle's section boundaries.

    Existing task-group ids are stable section boundaries because section assessment
    is keyed by group id. AI may split a group into additional groups, but it must not
    remove/merge existing groups. Task-count guidance is advisory: coverage matters
    more than hitting a number, while 20-30 is the normal target.
    """
    old_groups = original.get("task_groups", []) or []
    new_groups = candidate.get("task_groups", []) or []
    old_ids = [str(group.get("id", "")).strip() for group in old_groups]
    new_ids = [str(group.get("id", "")).strip() for group in new_groups]
    missing_ids = [group_id for group_id in old_ids if group_id and group_id not in new_ids]
    old_tasks = _task_count(original)
    new_tasks = _task_count(candidate)

    errors: list[str] = []
    warnings: list[str] = []

    changed_protected: list[str] = []
    for field in PROTECTED_REFINEMENT_FIELDS:
        if field in original and candidate.get(field) != original.get(field):
            changed_protected.append(field)
    if changed_protected:
        errors.append(
            "节点细化只能修改 task_groups / task_count / compiler；以下稳定字段必须与当前执行包完全一致："
            + ", ".join(changed_protected)
        )

    if len(new_groups) < len(old_groups):
        errors.append(
            f"禁止合并既有任务组：当前执行包 {len(old_groups)} 组，导入结果只有 {len(new_groups)} 组。"
            "任务组是小节验收边界，只允许保留或进一步拆分。"
        )
    if missing_ids:
        errors.append(
            "导入结果删除了既有任务组 ID：" + ", ".join(missing_ids) +
            "。请保留这些任务组及其技术语义；需要细分时新增子主题组，不要覆盖原组。"
        )
    if len(new_groups) > len(old_groups):
        warnings.append(
            f"任务组从 {len(old_groups)} 增加到 {len(new_groups)}；允许合理拆分，请确认新增组确实代表独立技术小节。"
        )

    if new_tasks < RECOMMENDED_LEAF_TASK_MIN or new_tasks > RECOMMENDED_LEAF_TASK_MAX:
        warnings.append(
            f"当前细化结果有 {new_tasks} 个叶子任务；通常建议控制在 "
            f"{RECOMMENDED_LEAF_TASK_MIN}~{RECOMMENDED_LEAF_TASK_MAX} 个。"
            "数量不是硬门槛，优先保证 must_learn 全覆盖且没有重复总结任务。"
        )
    if new_tasks < SOFT_LEAF_TASK_MIN:
        warnings.append(
            f"叶子任务少于 {SOFT_LEAF_TASK_MIN} 个，容易把多个机制压进同一任务；请重点检查 must_learn 是否逐项可验证。"
        )
    elif new_tasks > SOFT_LEAF_TASK_MAX:
        warnings.append(
            f"叶子任务超过 {SOFT_LEAF_TASK_MAX} 个，容易重新出现碎片化和重复整理；请检查是否存在可合并的重复证据任务。"
        )

    oversized = [
        (str(group.get("id", "")), len(task_group_items(group)))
        for group in new_groups
        if len(task_group_items(group)) > 10
    ]
    if oversized:
        detail = ", ".join(f"{group_id}={count}" for group_id, count in oversized)
        warnings.append(
            f"单个任务组叶子任务过多（{detail}）；建议把独立技术主题拆成新的验收小节，避免一个大组承载全部学习内容。"
        )

    return {
        "old_groups": len(old_groups),
        "new_groups": len(new_groups),
        "old_tasks": old_tasks,
        "new_tasks": new_tasks,
        "missing_group_ids": missing_ids,
        "errors": errors,
        "warnings": warnings,
        "recommended_task_range": [RECOMMENDED_LEAF_TASK_MIN, RECOMMENDED_LEAF_TASK_MAX],
    }


def build_refinement_ai_prompt(node: dict, bundle: dict) -> str:
    """Return the exact prompt copied to the clipboard after exporting a refinement ZIP."""
    paper = bundle.get("verification_paper", {}) or {}
    paper_id = str(paper.get("paper_id", "")).strip() or f"{node['node_code']}-V1"
    paper_version = int(paper.get("version", 1) or 1)
    return f"""我会同时上传一个 LearningCI 导出的节点细化 ZIP。

请把 ZIP 作为本次任务的唯一事实来源，并先完整读取压缩包内所有文件，尤其是：
- `01-节点细化要求.md`：本次细化规则
- `02-当前节点定义_禁止修改.json`：冻结路线合同
- `03-当前节点执行包.json`：必须作为返回 JSON 的结构骨架
- `04-返回文件结构约束.json`：机器导入约束

你的任务：严格按 ZIP 内规则细化 `{node['node_code']}`。

返回前必须同时满足以下硬约束：
1. 只返回 **一个合法 JSON 对象**；不要 Markdown fence，不要解释，不要第二份方案。
2. `node_id` 必须是 `{node['node_code']}`，`node_title` 必须保持为 `{node['title']}`。
3. 以 `03-当前节点执行包.json` 为结构骨架。除 `task_groups`、`task_count`、`compiler` 外，其余已有顶层字段必须原样复制，不能删除或改写。
4. 叶子任务必须使用规范字段 `task_groups[].items[]`；不要输出 `leaf_tasks` 或 `tasks`。
5. 必须保留 03 中所有既有 `task_group.id` 及其技术语义；禁止合并、删除或改名。允许为了独立技术小节新增任务组。
6. 单节点通常细化到 **20~30 个高质量叶子任务**；15~35 是弹性范围。覆盖完整优先，禁止用重复总结、重复抄文档凑数量。
7. `must_learn` 每一项都必须被至少一个叶子任务显式覆盖，并能通过 `done_when` 与证据字段验证。
8. `task_count` 必须等于全部 `task_groups[].items[]` 的实际数量。
9. `compiler.status` 必须是 `REVIEWED`。
10. `verification_paper`、`task_policy`、`retest_policy` 等稳定字段必须从 `03-当前节点执行包.json` **原样复制**。当前固定试卷标识为 `{paper_id}`，version={paper_version}；不得改题、改 ID、改版本。
11. 不得修改冻结 Node 定义、Stage、Priority、capability、must_learn、out_of_scope、project_anchor 或评分门槛。
12. 输出前请自行对照 `04-返回文件结构约束.json` 做一次结构自检，再返回最终 JSON。

不要向我提问，也不要先给方案。直接读取 ZIP 后输出最终 JSON。
"""


def _request_text(node: dict, bundle: dict) -> str:
    return f"""# LearningCI 节点细化请求

你现在是 **LearningCI 节点细化器**。

这不是重新规划学习路线。你唯一的任务是：在 **不改变冻结节点定义** 的前提下，把节点 `{node['node_code']}` 细化成可以逐个打卡、逐个留证据的执行包，并 **原样保留当前执行包中已经存在的固定正式验收试卷**。

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
8. 当前 `verification_paper` 已经是固定正式试卷；本次任务细化必须从 `03-当前节点执行包.json` 原样复制，禁止重新出题或修改任何题目。
9. `task_policy`、`retest_policy`、source metadata 等稳定字段也必须原样保留；本次 AI 允许修改的业务内容只有 `task_groups` 与由其推导的 `task_count`，以及 `compiler.status/note`。
10. 细化后的任务必须为现有固定试卷提供足够学习覆盖，但不能为了迎合试题而改变冻结节点能力边界。
11. 任务标题、任务组标题、说明文字、试题正文尽量使用中文；必要的 C++/Linux/API 名称保留英文。
12. **禁止为了“收束”再增加重复总结任务。** 如果前面的叶子任务已经逐项回答并留下证据，不要再要求“形成审计结论 / 再写一遍总结 / 把上面内容重新归纳到文档”。
13. 每个有实际学习内容的任务组应当可以直接用其叶子任务回答与证据进行“小节 AI 验收”。任务组可写 `assessment_required: true`；LearningCI 会把整个小节的现有记录导出给 ChatGPT 打分。
14. 如果项目确实需要长期资产文档，优先由已有叶子证据自动汇总或在最终项目阶段生成，不要把重复抄写当成学习任务。
15. **任务组是稳定的小节验收边界，禁止把多个既有 task_group 合并成一个大组。** 必须保留当前所有 task_group 的 `id` 与核心技术语义；如果确实需要更细，可以新增任务组，但不能删除既有组。
16. 每个任务组应围绕一个可独立验收的技术主题组织叶子任务。不要建立 `rpc_history_audit` / `all_tasks` 之类把所有主题重新塞回一个大组的总括组。
17. 单节点通常建议 **20~30 个高质量叶子任务**。15~35 只作为合理弹性范围；不要为了凑数量制造重复总结，也不要为了减少数量把多个机制压成一个任务。
18. `must_learn` 中的每一项都必须至少由一个叶子任务显式覆盖，并且能通过 `done_when` 和证据字段判断是否真正掌握。输出前自行核对覆盖完整性，但不要额外生成“覆盖检查/总结”任务。
19. 当前执行包如果只有基础粗任务，应通过有意义的机制拆分、预测、异常路径、源码验证等方式细化到合理粒度；严禁用重复抄文档填充 20~30 的数量目标。
20. 返回 JSON 必须以 `03-当前节点执行包.json` 为结构骨架。本次只允许调整 `task_groups`、`task_count` 与 `compiler.status/note`；其余已有顶层字段必须原样保留。叶子任务使用规范字段 `task_groups[].items[]`。`leaf_tasks` / `tasks` 仅属于导入兼容别名，AI 正常输出禁止使用。
21. `task_count` 必须与全部 `items` 的实际数量严格一致。
22. `verification_paper`、`task_policy`、`retest_policy` 等稳定字段绝对不能省略，并且必须从 `03-当前节点执行包.json` 原样保留。细化任务不等于重新出卷或改验收策略。
23. 输出前必须自行对照 `04-返回文件结构约束.json` 完成一次机器结构自检；不能只保证内容合理而忽略导入格式。

## 输出要求

只返回一个合法 JSON，结构必须符合 `04-返回文件结构约束.json`。

- `node_id` 必须仍为 `{node['node_code']}`
- `node_title` 必须仍为 `{node['title']}`
- `compiler.status` 必须写 `REVIEWED`
- 除 `task_groups`、`task_count`、`compiler.status/note` 外，其余已有顶层字段必须原样保留
- `verification_paper` 必须原样保留当前执行包中的固定试卷，不得修改 ID、版本或题目
- 规范叶子任务字段必须是 `task_groups[].items[]`
- `task_count` 必须与实际叶子任务数严格一致
- 不要附带 Markdown fence，不要解释，不要输出第二份方案。

## 当前粗执行包状态

当前任务组数量：{len(bundle.get('task_groups', []))}
当前叶子任务数量：{bundle.get('task_count', 0)}
当前执行包质量状态：{bundle.get('compiler', {}).get('status', 'GENERATED')}

当前任务组边界（必须保留这些 ID，不得合并删除）：

{_group_outline(bundle)}

你可以保留、细化、拆分合理任务，也可以新增新的技术任务组；但不能合并/删除既有任务组，不能改变节点本身。
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
        "00-复制给AI的提示词.txt": build_refinement_ai_prompt(node, bundle),
        "01-节点细化要求.md": _request_text(node, bundle),
        "02-当前节点定义_禁止修改.json": _json_text(node_contract),
        "03-当前节点执行包.json": _json_text(clean_bundle),
        "04-返回文件结构约束.json": schema_text if schema_text.endswith("\n") else schema_text + "\n",
        "05-NebulaRPC总计划.md": master_text,
        "06-前置节点学习结果.json": _json_text(previous_context),
        "07-项目背景与求职证据.md": _project_background_text(),
        "08-返回文件说明.txt": (
            "LearningCI 导出本 ZIP 时，会同时把 `00-复制给AI的提示词.txt` 的内容复制到系统剪贴板。\n"
            "正确流程：① 上传这个 ZIP；② 直接粘贴剪贴板提示词并发送；③ AI 只返回一个 JSON；"
            "④ 保存为 " f"{node['node_code']}_已细化.json；⑤ 回到节点准备页面导入。\n"
            "如果剪贴板内容丢失，直接打开 ZIP 内的 00-复制给AI的提示词.txt 重新复制即可。\n"
            "不要手工覆盖 plan.json；不要手工修改已经冻结的节点执行包。\n"
        ),
        "09-生成前自检清单.md": (
            "# AI 返回前自检清单\n\n"
            "- [ ] 只输出一个合法 JSON 对象，没有 Markdown fence。\n"
            f"- [ ] node_id = `{node['node_code']}`，node_title 未修改。\n"
            "- [ ] 完整保留 03 中所有既有 task_group.id，没有合并/删除/改名。\n"
            "- [ ] 叶子任务统一位于 task_groups[].items[]。\n"
            "- [ ] task_count 等于实际 items 总数。\n"
            "- [ ] must_learn 全覆盖，没有靠重复总结任务凑数量。\n"
            "- [ ] verification_paper / task_policy / retest_policy 等稳定字段与 03 完全一致。\n"
            "- [ ] 已逐项对照 04-返回文件结构约束.json。\n"
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
    normalize_bundle_task_groups(data)
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
    normalize_bundle_task_groups(data)
    validate_bundle(data, node_code)
    target = DEFAULT_BUNDLE_DIR / f"{node_code}.json"
    target.write_text(_json_text(data), encoding="utf-8")
    return target
