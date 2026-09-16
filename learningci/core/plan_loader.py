from __future__ import annotations

import hashlib
import json
from datetime import datetime
from pathlib import Path

from learningci.database import Database


REQUIRED_NODE_FIELDS = {
    "id", "stage", "order", "title", "capability", "tasks", "scoring"
}


def _now() -> str:
    return datetime.now().isoformat(timespec="seconds")


def load_plan_file(path: Path) -> tuple[dict, str]:
    raw = Path(path).read_bytes()
    digest = hashlib.sha256(raw).hexdigest()
    data = json.loads(raw.decode("utf-8"))
    if "plan" not in data or "nodes" not in data:
        raise ValueError("plan.json must contain 'plan' and 'nodes'")
    if not isinstance(data["nodes"], list) or not data["nodes"]:
        raise ValueError("plan must contain at least one node")
    seen: set[str] = set()
    for node in data["nodes"]:
        missing = REQUIRED_NODE_FIELDS - set(node)
        if missing:
            raise ValueError(f"node missing fields: {sorted(missing)}")
        if node["id"] in seen:
            raise ValueError(f"duplicate node id: {node['id']}")
        seen.add(node["id"])
    return data, digest


def ensure_plan_imported(db: Database, path: Path) -> int:
    data, digest = load_plan_file(path)
    plan_meta = data["plan"]
    existing = db.conn.execute(
        "SELECT * FROM plans WHERE plan_code = ?", (plan_meta["id"],)
    ).fetchone()
    if existing:
        if existing["plan_hash"] != digest:
            raise RuntimeError(
                "冻结计划文件在导入后发生了变化。LearningCI 拒绝静默改写正在执行的路线。\n\n"
                "如果这是一次明确的软件升级，请先备份 data/learningci.db；"
                "只有确认要采用新计划版本时才执行迁移或重置。"
            )
        return int(existing["id"])

    now = _now()
    with db.transaction() as conn:
        cur = conn.execute(
            "INSERT INTO plans(plan_code,name,version,plan_hash,source_path,imported_at) VALUES(?,?,?,?,?,?)",
            (
                plan_meta["id"], plan_meta["name"], plan_meta["version"],
                digest, str(path), now,
            ),
        )
        plan_id = int(cur.lastrowid)
        for node in sorted(data["nodes"], key=lambda x: int(x["order"])):
            conn.execute(
                """INSERT INTO nodes(
                    plan_id,node_code,stage,order_index,title,capability,priority,target_score,status,
                    tasks_json,must_learn_json,out_of_scope_json,scoring_json,project_anchor_json,
                    created_at,updated_at
                ) VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
                (
                    plan_id, node["id"], str(node["stage"]), int(node["order"]),
                    node["title"], node["capability"], node.get("priority", "CORE"),
                    int(node.get("target_score", 80)), "READY",
                    json.dumps(node.get("tasks", []), ensure_ascii=False),
                    json.dumps(node.get("must_learn", []), ensure_ascii=False),
                    json.dumps(node.get("out_of_scope", []), ensure_ascii=False),
                    json.dumps(node.get("scoring", {}), ensure_ascii=False),
                    json.dumps(node.get("project_anchor", {}), ensure_ascii=False),
                    now, now,
                ),
            )
    return plan_id
