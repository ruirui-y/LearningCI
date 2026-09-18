from __future__ import annotations

import hashlib
import json
from datetime import datetime
from pathlib import Path

from learningci.database import Database

EXPECTED_SCORES = {
    "explanation": 15,
    "prediction": 15,
    "implementation": 25,
    "diagnosis": 25,
    "transfer": 20,
}

VALID_BUNDLE_STATES = {"GENERATED", "REVIEWED", "FROZEN"}

TASK_ITEM_KEYS = ("items", "leaf_tasks", "tasks")


def task_group_items(group: dict) -> list:
    """Return leaf tasks from the canonical field or supported AI aliases."""
    for key in TASK_ITEM_KEYS:
        value = group.get(key)
        if isinstance(value, list) and value:
            return value
    return []


def normalize_bundle_task_groups(bundle: dict) -> dict:
    """Normalize AI aliases to the canonical ``task_groups[].items`` shape.

    Validation accepts leaf_tasks/tasks for import compatibility, but the rest of
    LearningCI intentionally reads only ``items``. Canonicalizing at the boundary
    prevents a bundle from validating successfully and then appearing empty in the UI.
    """
    for group in bundle.get("task_groups", []) or []:
        items = task_group_items(group)
        if items:
            group["items"] = items
        group.pop("leaf_tasks", None)
        group.pop("tasks", None)
    return bundle


def _now() -> str:
    return datetime.now().isoformat(timespec="seconds")


def _hash_bytes(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


def _hash_json(data: dict) -> str:
    raw = json.dumps(data, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return _hash_bytes(raw)


def _bundle_state(bundle: dict) -> str:
    raw = str(bundle.get("compiler", {}).get("status", "GENERATED")).upper()
    if raw in {"REVIEWED", "FROZEN"}:
        return raw
    return "GENERATED"


def validate_paper(node_code: str, paper: dict) -> None:
    if not paper.get("paper_id"):
        raise ValueError(f"{node_code}: 固定试卷 paper_id 为空")
    questions = paper.get("questions")
    if not isinstance(questions, list) or len(questions) != 5:
        raise ValueError(f"{node_code}: 固定试卷必须严格包含 5 道题")
    seen = set()
    total = 0
    for q in questions:
        dim = q.get("dimension")
        if dim not in EXPECTED_SCORES:
            raise ValueError(f"{node_code}: 非法评分维度 {dim}")
        if dim in seen:
            raise ValueError(f"{node_code}: 重复评分维度 {dim}")
        seen.add(dim)
        score = int(q.get("max_score", -1))
        if score != EXPECTED_SCORES[dim]:
            raise ValueError(f"{node_code}: {dim} max_score 必须为 {EXPECTED_SCORES[dim]}")
        if not str(q.get("question", "")).strip():
            raise ValueError(f"{node_code}: {dim} 题目为空")
        total += score
    if seen != set(EXPECTED_SCORES) or total != 100:
        raise ValueError(f"{node_code}: 试卷维度或总分不合法")


def validate_bundle(bundle: dict, expected_node_code: str | None = None) -> None:
    node_code = str(bundle.get("node_id", ""))
    if not node_code:
        raise ValueError("节点执行包缺少 node_id")
    if expected_node_code and node_code != expected_node_code:
        raise ValueError(f"执行包 node_id {node_code} != {expected_node_code}")
    groups = bundle.get("task_groups")
    if not isinstance(groups, list) or not groups:
        raise ValueError(f"{node_code}: task_groups 为空")
    seen_tasks: set[str] = set()
    count = 0
    for group in groups:
        if not str(group.get("id", "")).strip() or not str(group.get("title", "")).strip():
            raise ValueError(f"{node_code}: 任务组 id/title 为空")
        # 兼容 AI 生成的不同细化包格式
        # 标准格式: items
        # 兼容格式: leaf_tasks / tasks
        items = task_group_items(group)
        if not isinstance(items, list) or not items:
            raise ValueError(
                f"{node_code}: 任务组 {group.get('id')} 缺少叶子任务列表，支持字段: items / leaf_tasks / tasks"
            )
        for item in items:
            code = str(item.get("id", "")).strip()
            if not code:
                raise ValueError(f"{node_code}: 叶子任务 id 为空")
            if code in seen_tasks:
                raise ValueError(f"{node_code}: 重复叶子任务 id {code}")
            seen_tasks.add(code)
            count += 1
            if not str(item.get("title", "")).strip():
                raise ValueError(f"{node_code}: {code} title 为空")
            if not str(item.get("detail", "")).strip():
                raise ValueError(f"{node_code}: {code} 缺少 detail")
            if not str(item.get("purpose", "")).strip():
                raise ValueError(f"{node_code}: {code} 缺少 purpose")
            if not isinstance(item.get("done_when"), list) or not item.get("done_when"):
                raise ValueError(f"{node_code}: {code} 缺少 done_when")
            if int(item.get("estimated_minutes", 0) or 0) <= 0:
                raise ValueError(f"{node_code}: {code} estimated_minutes 必须大于 0")
    declared = int(bundle.get("task_count", count))
    if declared != count:
        raise ValueError(f"{node_code}: task_count={declared} 与实际 {count} 不一致")
    validate_paper(node_code, bundle.get("verification_paper", {}))


def load_bundle_file(path: Path) -> tuple[dict, str]:
    raw = Path(path).read_bytes()
    data = json.loads(raw.decode("utf-8"))
    validate_bundle(data, Path(path).stem.split("_")[0] if "_已细化" in Path(path).stem else None)
    normalize_bundle_task_groups(data)
    return data, _hash_bytes(raw)


def _node_has_runtime_data(db: Database, node_id: int) -> bool:
    checks = [
        ("SELECT 1 FROM leaf_task_progress WHERE node_id=? AND (completed=1 OR total_seconds>0 OR first_started_at IS NOT NULL) LIMIT 1", (node_id,)),
        ("SELECT 1 FROM focus_sessions WHERE node_id=? LIMIT 1", (node_id,)),
        ("SELECT 1 FROM attempts WHERE node_id=? LIMIT 1", (node_id,)),
        ("SELECT 1 FROM score_records WHERE node_id=? LIMIT 1", (node_id,)),
    ]
    return any(db.conn.execute(sql, params).fetchone() for sql, params in checks)


def _upsert_paper(db: Database, node_id: int, bundle: dict, bundle_hash: str, allow_replace: bool) -> None:
    paper = bundle["verification_paper"]
    paper_code = str(paper["paper_id"])
    paper_hash = _hash_json(paper)
    now = _now()
    existing = db.conn.execute(
        "SELECT id,paper_hash FROM assessment_papers WHERE node_id=? AND paper_kind='VERIFICATION' ORDER BY id DESC LIMIT 1",
        (node_id,),
    ).fetchone()
    if existing:
        if existing["paper_hash"] == paper_hash:
            return
        if not allow_replace:
            raise RuntimeError(f"固定试卷已冻结但内容发生变化：{paper_code}")
        db.conn.execute(
            """UPDATE assessment_papers SET paper_code=?,paper_version=?,paper_hash=?,paper_json=?,
               source_bundle_hash=?,created_at=? WHERE id=?""",
            (
                paper_code, int(paper.get("version", 1)), paper_hash,
                json.dumps(paper, ensure_ascii=False), bundle_hash, now, existing["id"],
            ),
        )
    else:
        db.conn.execute(
            """INSERT INTO assessment_papers(
                node_id,paper_code,paper_kind,paper_version,paper_hash,paper_json,source_bundle_hash,created_at
            ) VALUES(?,?,?,?,?,?,?,?)""",
            (
                node_id, paper_code, "VERIFICATION", int(paper.get("version", 1)), paper_hash,
                json.dumps(paper, ensure_ascii=False), bundle_hash, now,
            ),
        )


def ensure_bundles_imported(db: Database, bundle_dir: Path) -> int:
    """Import baseline node execution packages.

    GENERATED/REVIEWED bundles are still preparation material and may be replaced before any
    runtime evidence exists. FROZEN bundles, or any bundle that already has learning evidence,
    are immutable. This is the key difference from v0.2.0, which prematurely froze all 68 nodes.
    """
    bundle_dir = Path(bundle_dir)
    nodes = db.conn.execute("SELECT id,node_code FROM nodes ORDER BY order_index").fetchall()
    imported = 0
    now = _now()
    for row in nodes:
        node_id = int(row["id"])
        node_code = str(row["node_code"])
        path = bundle_dir / f"{node_code}.json"
        if not path.exists():
            raise RuntimeError(f"缺少节点执行包：{path}")
        bundle, digest = load_bundle_file(path)
        validate_bundle(bundle, node_code)
        file_state = _bundle_state(bundle)
        existing = db.conn.execute("SELECT * FROM node_bundles WHERE node_id=?", (node_id,)).fetchone()
        if existing:
            state = str(existing["bundle_state"] or "GENERATED").upper()
            if existing["bundle_hash"] != digest:
                locked = state == "FROZEN" or _node_has_runtime_data(db, node_id)
                if locked:
                    raise RuntimeError(
                        f"节点执行包已经冻结或已有学习记录，文件却发生变化：{node_code}\n\n"
                        "LearningCI 拒绝覆盖。请恢复原文件；如果只是准备未来节点，请使用“节点准备”页面导入细化结果。"
                    )
                db.conn.execute(
                    """UPDATE node_bundles SET bundle_hash=?,bundle_json=?,source_path=?,bundle_state=?,
                       revision=revision+1,updated_at=? WHERE node_id=?""",
                    (
                        digest, json.dumps(bundle, ensure_ascii=False), str(path), file_state, now, node_id,
                    ),
                )
                _upsert_paper(db, node_id, bundle, digest, allow_replace=True)
                imported += 1
            elif state not in VALID_BUNDLE_STATES:
                db.conn.execute("UPDATE node_bundles SET bundle_state=?,updated_at=? WHERE node_id=?", (file_state, now, node_id))
        else:
            db.conn.execute(
                """INSERT INTO node_bundles(
                    node_id,bundle_hash,bundle_json,source_path,imported_at,bundle_state,revision,updated_at
                ) VALUES(?,?,?,?,?,?,1,?)""",
                (
                    node_id, digest, json.dumps(bundle, ensure_ascii=False), str(path), now, file_state, now,
                ),
            )
            _upsert_paper(db, node_id, bundle, digest, allow_replace=True)
            imported += 1
    db.conn.commit()
    return imported


def bundle_file_hash(path: Path) -> str:
    return _hash_bytes(Path(path).read_bytes())
