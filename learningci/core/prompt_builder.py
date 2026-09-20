from __future__ import annotations

import json


def _pretty(value) -> str:
    return json.dumps(value, ensure_ascii=False, indent=2)


def _is_history_audit_node(node: dict) -> bool:
    code = str(node.get("node_code", ""))
    title = str(node.get("title", ""))
    return code in {"NRPC-S0-01", "NRPC-S0-02"} or "历史能力审计" in title


def _history_audit_exam_policy(node: dict) -> str:
    if not _is_history_audit_node(node):
        return ""
    return (
        "\n历史审计节点专用职责边界：\n"
        "- 叶子任务阶段负责一次性采集源码路径、函数、调用链、测试/日志和证据备注；正式测试不得要求学习者把这些材料再抄一遍。\n"
        "- 正式测试的学习者回答只考：机制解释、运行预测、具体故障诊断、当前机制内的技术迁移。\n"
        "- explanation / prediction / diagnosis / transfer 不得因为学习者没有重复写源码绝对路径、行号或粘贴代码而扣分；如果机制本身错误，直接批注错误机制。\n"
        "- implementation 是系统自动复核项：LearningCI 自动附带已保存的叶子工程证据和小节验收结果，学习者无需作答。\n"
        "- diagnosis 必须给一个具体故障/错误改动/异常现象让学习者诊断，不得要求学习者自己再挑问题写一份小型审计报告。\n"
        "- 不得要求学习者判断未来 Stage 应‘复用/最小恢复/重新验证/重做’，这类路线决策属于 Reviewer/架构上下文。\n"
        "- transfer 必须用当前机制内的陌生变化/破坏性修改测试迁移能力，不得让学习者替 Master Plan 做技术路线分类。\n"
        "- Reviewer 必须输出可执行修正方向：不仅说明哪里错，还要说明为什么影响验收、下一步应该补什么证据或重新回答什么。\n"
        "- 如果学习者明确回答“不知道”“没理解”“不会”，不能因为其他题目表现好而给该任务高分；必须降低该任务评分并标记原因。\n"
        "- 评分必须区分：技术不会、证据不足、任务理解不足、流程遗漏，不能混为一个问题。\n"
    )


def build_test_prompt(node: dict, previous_tests: list[dict] | None = None, is_retest: bool = False) -> str:
    previous_tests = previous_tests or []
    mode = "延迟复测" if is_retest else "正式 Verification"
    anchor = node.get("project_anchor", {})
    history = _is_history_audit_node(node)
    history_policy = _history_audit_exam_policy(node)
    evidence_rule = (
        "3. 历史审计节点不得让学习者重复提交源码证据；implementation 必须设置 requires_answer=false，其 25 分由 LearningCI 自动附带的既有工程证据评分；diagnosis 必须给具体故障场景。"
        if history else
        "3. implementation / diagnosis 必须要求可验证的代码、测试、日志、抓包或实验依据之一。"
    )
    question_format = {
        "node_id": node["node_code"],
        "questions": [
            {"id": "q1", "dimension": "explanation", "max_score": 15, "question": "..."},
            {"id": "q2", "dimension": "prediction", "max_score": 15, "question": "..."},
            {
                "id": "q3", "dimension": "implementation", "max_score": 25,
                **({"requires_answer": False, "question": "系统自动复核已有工程证据，无需学习者作答。"} if history else {"question": "..."}),
            },
            {
                "id": "q4", "dimension": "diagnosis", "max_score": 25,
                "question": "给出一个具体故障/错误改动后要求诊断..." if history else "...",
            },
            {"id": "q5", "dimension": "transfer", "max_score": 20, "question": "..."},
        ],
    }
    return f"""你现在是 LearningCI 的严格考官。

当前模式：{mode}
节点 ID：{node['node_code']}
节点名称：{node['title']}
能力定义：{node['capability']}
目标分数：{node['target_score']}

今天冻结计划中的最低任务：
{_pretty(node.get('tasks', []))}

本节点必须掌握：
{_pretty(node.get('must_learn', []))}

本节点明确不考：
{_pretty(node.get('out_of_scope', []))}

项目锚点（路径相对于目标项目根目录，而不是 LearningCI/docs）：
{_pretty(anchor)}

评分结构固定为：
- explanation: 15
- prediction: 15
- implementation: 25
- diagnosis: 25
- transfer: 20

规则：
1. 只围绕当前节点出题，禁止扩展学习路线。
2. 不给答案、不提示关键结论。
{evidence_rule}
4. 题目只能要求当前节点或项目锚点中已经规定的工程产物，禁止临时扩张项目范围。
5. 如果是复测，必须换场景、换数据、换代码，不能复用旧题。
6. 题目总分必须严格等于 100。
7. 返回纯 JSON，不要 markdown fence，不要附加解释。
{history_policy}
之前使用过的试卷（不得重复）：
{_pretty(previous_tests[-3:])}

返回格式：
{_pretty(question_format)}
"""


def build_grade_prompt(
    node: dict,
    test_json: dict,
    answers: dict[str, str] | str,
    system_evidence: dict | None = None,
) -> str:
    answer_block = _pretty(answers) if isinstance(answers, dict) else str(answers)
    history = _is_history_audit_node(node)
    history_policy = _history_audit_exam_policy(node)
    evidence_block = _pretty(system_evidence or {}) if history else "{}"
    evidence_rule = (
        "3. implementation 的 25 分只依据 LearningCI 自动附带的既有工程证据评分；学习者不需要也不应该在 q3 重复作答。"
        " explanation / prediction / diagnosis / transfer 不得因未重复写源码路径而扣分，只按技术机制是否正确评分。"
        if history else
        "3. implementation / diagnosis 如果只有口头描述、没有题目要求的证据，应明确扣分。"
    )
    return f"""你现在是 LearningCI Reviewer。只评分，不重新规划路线。

节点：{node['node_code']} - {node['title']}
能力定义：{node['capability']}

正式试卷：
{_pretty(test_json)}

我的逐题回答：
{answer_block}

LearningCI 自动附带的既有工程证据（不是学习者本次重复作答）：
{evidence_block}

请严格评分：
- explanation / 15
- prediction / 15
- implementation / 25
- diagnosis / 25
- transfer / 20

要求：
1. 每一分必须能从对应回答或系统附带工程证据中解释。
2. 缺少证据的维度不能脑补。
{evidence_rule}
4. 不决定 PASS/FAIL；LearningCI 本地程序计算结果：总分 >=70 即可推进主线，80 分及原维度门槛作为稳定掌握目标。维度短板应写入 issues，但不得为了凑门槛夸大扣分。

5. 历史审计节点必须保持评分克制：
   - 不能因为学习者给出正确方向就默认完整掌握。
   - 如果缺少关键源码证据、异常路径、生命周期边界或失败场景分析，必须明确扣除对应维度分数。
   - explanation/prediction 重点评价机制理解，不因没有重复粘贴源码扣分；但遗漏关键状态变化、所有权关系、错误分支时必须扣分。
   - diagnosis 必须区分“发现问题方向”和“完成完整诊断”。只有包含观察、源码依据、失败场景、根因和实际后果时才能获得高分。
   - evidence 只能证明工程事实，不能替代学习者对机制的解释。
5. 不给新的学习路线，不要求当前节点之外的新工程内容。
6. 如果当前节点属于历史能力审计，不得因为学习者没有替未来 Stage 做“复用/恢复/重做”规划而扣分。
7. 对学习者机制回答有错误或漏项时，直接指出具体机制错误；不要要求其重新整理一遍已有源码材料。
8. 如果存在需要修正的技术机制，必须逐条写入 issues。每条只写一个问题，给出 question_id、dimension、短标题、具体错误、正确机制/修正方向；related_task_ids 只能引用系统附带证据中真实存在的 task_id，找不到就返回空数组，禁止编造。
9. correction 必须直接告诉学习者“正确机制是什么/应该改正哪一个认知”，不能只写“再复习”“重新阅读源码”。
10. Reviewer 必须同时提供标准答案基准。标准答案不是让学习者背诵，而是用于说明当前回答与正确机制之间的差距。对于每个存在问题的回答，issues 中必须包含：
   - standard_answer：该问题对应的正确机制/完整答案要点；
   - learner_gap：当前回答缺失或错误的部分。
   如果回答正确，也需要在 evidence 中说明其覆盖了哪些标准机制。
10. 返回纯 JSON，不要 markdown fence，不要额外文字。
{history_policy}
返回格式：
{{
  "scores": {{
    "explanation": 0,
    "prediction": 0,
    "implementation": 0,
    "diagnosis": 0,
    "transfer": 0
  }},
  "evidence": {{
    "explanation": "...",
    "prediction": "...",
    "implementation": "...",
    "diagnosis": "...",
    "transfer": "..."
  }},
  "issues": [
    {{
      "question_id": "q2",
      "dimension": "prediction",
      "title": "一句话短标题",
      "detail": "具体指出当前回答错在哪里或漏了哪一步",
      "standard_answer": "该问题对应的标准机制/正确答案要点",
      "learner_gap": "当前回答与标准机制之间的差距",
      "correction": "直接写正确机制或应该修正成什么理解",
      "related_task_ids": ["S0-01-TC-04"],
      "severity": "error"
    }}
  ],
  "weaknesses": ["兼容旧版本的简短薄弱点列表；与 issues 保持一致"]
}}
"""


def build_section_grade_prompt(node: dict, group: dict, route_context: dict | None = None) -> str:
    """Build a strict, no-API prompt that grades one task section from existing leaf evidence.

    The user should not have to write another summary. The examiner must judge mastery only from
    the leaf-task records already entered in LearningCI.
    """
    lines = [
        "你现在是 LearningCI 的严格小节考官。",
        "",
        "你不是学习路线推荐者，也不要要求我再写一份总结。",
        "你的任务是：只根据这个小节已经完成的叶子任务回答与工程证据，判断我是否真正掌握。",
        "",
        f"Node：{node['node_code']}",
        f"Title：{node['title']}",
        f"节点能力：{node['capability']}",
        f"小节 ID：{group.get('id')}",
        f"小节名称：{group.get('title')}",
        f"小节说明：{group.get('description', '')}",
    ]

    if route_context:
        current = route_context.get("current_node", {}) or {}
        lines.extend([
            "",
            "冻结路线上下文（仅供考官做复用/恢复/重做边界判断，不是要求学习者额外回答）：",
            f"路线：{route_context.get('plan', {}).get('name', 'NebulaRPC')} {route_context.get('plan', {}).get('version', '')}",
            f"当前 Stage：{current.get('stage', node.get('stage', ''))}",
            "当前节点必须掌握：" + _pretty(current.get("must_learn", node.get("must_learn", []))),
            "当前节点明确不做：" + _pretty(current.get("out_of_scope", node.get("out_of_scope", []))),
            f"节点来源章节：{current.get('source_section', '')}",
            "",
            "相邻主线节点（仅帮助你理解当前能力在整条路线中的位置）：",
        ])
        for nearby in route_context.get("nearby_mainline", []):
            marker = " ← 当前" if str(nearby.get("node_code")) == str(node.get("node_code")) else ""
            lines.append(
                f"- {nearby.get('node_code')} / Stage {nearby.get('stage')} / {nearby.get('title')}："
                f"{nearby.get('capability')}{marker}"
            )
        excerpts = route_context.get("master_plan_excerpts", []) or []
        if excerpts:
            lines.extend(["", "Master Plan 相关冻结原文："] )
            for excerpt in excerpts:
                lines.extend([
                    f"\n【§{excerpt.get('ref')} · {excerpt.get('title', '')}】",
                    str(excerpt.get("text", "")).strip(),
                ])
        lines.extend([
            "",
            "边界判断责任：",
            "- 学习者只负责当前叶子任务里的技术事实、源码位置、调用链、实验/日志等工程证据。",
            "- 你负责结合上述冻结路线判断这些已证明能力在 NebulaRPC 中应复用、最小恢复、重新验证还是确实需要重做。",
            "- 不得因为学习者没有主动规划未来 Stage、没有主动写“哪些该复用”而扣边界判断分。",
            "- 只有当叶子证据不足以支撑某个复用/恢复结论，或者叶子结论与冻结路线冲突时，才在边界判断维度扣分。",
        ])

    lines.extend([
        "",
        "评分结构固定为：",
        "- 理解准确度：35",
        "- 源码证据：30",
        "- 边界判断：25",
        "- 覆盖完整度：10",
        "总分 100，LearningCI 本地以 >=80 判定小节通过。",
        "",
        "严格规则：",
        "1. 只能依据下面已有叶子任务记录评分，不能因为措辞像正确答案就脑补缺失证据。",
        "2. 不要求我重新归纳总结；叶子任务中的证据备注本身就是我的回答。",
        "3. 源码路径、函数名、调用链、测试/日志等证据不充分时必须扣分。",
        "4. 如果结论存在明显错误，即使任务全部勾选，也必须扣分并指出具体任务。",
        "5. 不扩展到本节点 out_of_scope，不提供新的学习路线。",
        "6. 边界判断由考官结合冻结路线上下文完成；不得因为学习者没有主动规划 NebulaRPC 后续实现、没有主动写复用结论而扣分。只有现有工程证据不足以支持路线中的复用/恢复边界，或与冻结路线冲突时，才扣边界判断分。",
        "7. 每个扣分点单独写入 issues；能定位到叶子任务时必须填写 task_id，dimension 只能是理解准确度/源码证据/边界判断/覆盖完整度之一。",
        "8. issues.title 写一句短标题，issues.detail 说明具体错在哪里或缺什么证据；severity 只能是 error/warning/info；不要把多个问题揉成一条。",
        "9. 只返回纯 JSON，不要 Markdown fence，不要附加解释。",
        "",
        "当前小节叶子任务记录：",
    ])
    for idx, item in enumerate(group.get("items", []), start=1):
        lines.extend([
            f"\n[{idx}] {item.get('title', '')}",
            f"任务 ID：{item.get('id', '')}",
            f"目的：{item.get('purpose', '')}",
            f"操作：{item.get('detail', '')}",
            "完成标准：" + "；".join(str(x) for x in item.get("done_when", [])),
            f"完成状态：{'已完成' if item.get('completed') else '未完成'}",
            f"源码/产物路径：{item.get('source_path', '')}",
            f"函数/入口：{item.get('function_name', '')}",
            f"证据备注：{item.get('evidence_note', '')}",
        ])
    lines.extend([
        "",
        "返回格式：",
        "{",
        f'  "node_id": "{node["node_code"]}",',
        f'  "section_id": "{group.get("id")}",',
        '  "scores": {',
        '    "理解准确度": 0,',
        '    "源码证据": 0,',
        '    "边界判断": 0,',
        '    "覆盖完整度": 0',
        "  },",
        '  "evidence": ["指出哪些叶子回答证明了掌握"],',
        '  "issues": [',
        '    {',
        '      "task_id": "S0-01-EL-02",',
        '      "dimension": "源码证据",',
        '      "title": "调用链证据不完整",',
        '      "detail": "具体说明错在哪里、缺什么证据或哪条结论不严谨",',
        '      "severity": "warning"',
        '    }',
        '  ],',
        '  "weaknesses": ["兼容旧版本的简短薄弱点列表；如果 issues 已完整，可保持与 issues 同步"]',
        "}",
    ])
    return "\n".join(lines)
