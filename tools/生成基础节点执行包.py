from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
PLAN_PATH = ROOT / "plans" / "nebularpc" / "plan.json"
OUT_DIR = ROOT / "plans" / "nebularpc" / "节点执行包"
OUT_DIR.mkdir(parents=True, exist_ok=True)

DIMENSIONS = [("explanation", 15), ("prediction", 15), ("implementation", 25), ("diagnosis", 25), ("transfer", 20)]

def leaf(code, title, detail, purpose, minutes=25, evidence=True):
    return {
        "id": code, "title": title, "detail": detail, "purpose": purpose,
        "estimated_minutes": minutes, "required": True, "evidence_required": evidence,
        "evidence_fields": ["source_path", "function_name", "note"] if evidence else ["note"],
        "done_when": ["完成该动作本身", "留下足以复核结果的最小证据"],
    }

def groups_for(node):
    mode = str(node.get("execution_mode", "BUILD")).upper()
    cap = node["capability"]
    items = []
    for i, task in enumerate(node.get("tasks", []), 1):
        minutes = 20 if mode == "REVIEW" else 35 if mode == "MIGRATE" else 40 if mode == "BUILD" else 30
        items.append(leaf(f"{node['id']}-T{i:02d}", task, task, cap, minutes, True))
    verify_title = {
        "REVIEW": "确认达到能解释、能修改、能调试",
        "MIGRATE": "编译运行并形成 baseline commit",
        "BUILD": "运行针对性测试并保留失败/修复证据",
        "VALIDATE": "保存可复现命令、原始数据与结论",
    }.get(mode, "验证节点结果")
    items.append(leaf(f"{node['id']}-V01", verify_title, verify_title, cap, 20, True))
    return [{"id": "main", "title": f"{node['title']} · 主任务", "description": "保持节点完整，不再人为拆成二三十个碎片任务。", "items": items}]

def paper_for(node):
    title=node["title"]; cap=node["capability"]
    must="；".join(node.get("must_learn", [])); out="；".join(node.get("out_of_scope", []))
    paths="、".join(node.get("project_anchor", {}).get("paths", [])) or "当前项目锚点"
    ev="、".join(node.get("project_anchor", {}).get("evidence", [])) or "代码/测试/日志/数据"
    return {
        "paper_id": f"{node['id']}-V1", "version": 1, "visible_from_start": True, "frozen": True,
        "questions": [
            {"id":"q1","dimension":"explanation","max_score":15,"question":f"解释 {title} 的核心机制和边界，覆盖：{must}。重点说明因果关系，不背术语。"},
            {"id":"q2","dimension":"prediction","max_score":15,"question":f"给当前能力制造一个新的时序、并发或故障变化，在运行前预测关键状态和失败点。不得进入：{out or '相邻节点'}。"},
            {"id":"q3","dimension":"implementation","max_score":25,"question":f"提交真实工程结果。锚点：{paths}。必须附复现步骤和至少一种证据：{ev}。"},
            {"id":"q4","dimension":"diagnosis","max_score":25,"question":f"从本节点真实运行中选择一个故障/边界，按观察→假设→证据→根因→修复→再验证完成诊断。"},
            {"id":"q5","dimension":"transfer","max_score":20,"question":f"把“{cap}”迁移到一个训练任务未原样出现的新场景，说明不变原则、需要调整的实现与取舍。"},
        ],
    }

def compile_node(node, version):
    groups=groups_for(node)
    return {
        "schema_version":1, "node_id":node["id"], "node_title":node["title"],
        "source_plan_version":version, "source_section":node.get("source_section", ""),
        "compiler":{"type":"LearningCI 简化执行包生成器","status":"REVIEWED","note":"v0.4 默认执行包已可直接开始；只有节点确实过大或边界不清时才使用节点准备重新细化。"},
        "task_policy":{"single_active_leaf_task":True,"leaf_tasks_required_for_verification":True,"parent_progress_is_derived":True,"paper_visible_before_tasks_complete":True},
        "task_groups":groups, "task_count":sum(len(g["items"]) for g in groups),
        "verification_paper":paper_for(node),
        "retest_policy":{"reuse_initial_verification_for_failed_attempts":True,"new_paper_required_for_retest":True,"retest_paper_must_change_scenario":True},
    }

def main():
    data=json.loads(PLAN_PATH.read_text(encoding="utf-8")); version=data["plan"]["version"]
    for old in OUT_DIR.glob("NRPC-*.json"):
        old.unlink()
    index=[]
    for node in data["nodes"]:
        bundle=compile_node(node,version)
        (OUT_DIR/f"{node['id']}.json").write_text(json.dumps(bundle,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
        index.append({"node_id":node["id"],"title":node["title"],"execution_mode":node.get("execution_mode"),"task_count":bundle["task_count"],"compiler_status":"REVIEWED","paper_id":bundle["verification_paper"]["paper_id"]})
    (OUT_DIR/"index.json").write_text(json.dumps({"schema_version":1,"route_version":version,"nodes":index},ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
    print(f"已生成 {len(index)} 个节点执行包，共 {sum(x['task_count'] for x in index)} 个叶子任务")

if __name__ == "__main__":
    main()
