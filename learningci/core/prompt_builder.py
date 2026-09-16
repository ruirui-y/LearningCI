from __future__ import annotations

import json


def _pretty(value) -> str:
    return json.dumps(value, ensure_ascii=False, indent=2)


def build_test_prompt(node: dict, previous_tests: list[dict] | None = None, is_retest: bool = False) -> str:
    previous_tests = previous_tests or []
    mode = "延迟复测" if is_retest else "正式 Verification"
    anchor = node.get("project_anchor", {})
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
3. implementation / diagnosis 必须要求可验证的代码、测试、日志、抓包或实验依据之一。
4. 题目只能要求当前节点或项目锚点中已经规定的工程产物，禁止临时扩张项目范围。
5. 如果是复测，必须换场景、换数据、换代码，不能复用旧题。
6. 题目总分必须严格等于 100。
7. 返回纯 JSON，不要 markdown fence，不要附加解释。

之前使用过的试卷（不得重复）：
{_pretty(previous_tests[-3:])}

返回格式：
{{
  "node_id": "{node['node_code']}",
  "questions": [
    {{"id":"q1","dimension":"explanation","max_score":15,"question":"..."}},
    {{"id":"q2","dimension":"prediction","max_score":15,"question":"..."}},
    {{"id":"q3","dimension":"implementation","max_score":25,"question":"..."}},
    {{"id":"q4","dimension":"diagnosis","max_score":25,"question":"..."}},
    {{"id":"q5","dimension":"transfer","max_score":20,"question":"..."}}
  ]
}}
"""


def build_grade_prompt(node: dict, test_json: dict, answers: dict[str, str] | str) -> str:
    answer_block = _pretty(answers) if isinstance(answers, dict) else str(answers)
    return f"""你现在是 LearningCI Reviewer。只评分，不重新规划路线。

节点：{node['node_code']} - {node['title']}
能力定义：{node['capability']}

正式试卷：
{_pretty(test_json)}

我的逐题回答与工程证据：
{answer_block}

请严格评分：
- explanation / 15
- prediction / 15
- implementation / 25
- diagnosis / 25
- transfer / 20

要求：
1. 每一分必须能从对应问题的回答或工程证据中解释。
2. 缺少证据的维度不能脑补。
3. implementation / diagnosis 如果只有口头描述、没有题目要求的证据，应明确扣分。
4. 不决定 PASS/FAIL；LearningCI 本地程序会按冻结规则计算。
5. 不给新的学习路线，不要求当前节点之外的新工程内容。
6. 返回纯 JSON，不要 markdown fence，不要额外文字。

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
  "weaknesses": ["..."]
}}
"""
