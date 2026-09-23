from __future__ import annotations

import copy

from learningci.core.bundle_loader import normalize_bundle_for_learning
from learningci.core.refinement_bridge import analyze_refinement_structure, build_refinement_ai_prompt


def _paper():
    dims = [
        ("q1", "explanation", 15),
        ("q2", "prediction", 15),
        ("q3", "implementation", 25),
        ("q4", "diagnosis", 25),
        ("q5", "transfer", 20),
    ]
    return {
        "paper_id": "NRPC-S1-01-V1",
        "version": 1,
        "visible_from_start": True,
        "frozen": True,
        "questions": [
            {"id": qid, "dimension": dim, "max_score": score, "question": f"{dim} question"}
            for qid, dim, score in dims
        ],
    }


def _task(task_id: str, title: str = "task"):
    return {
        "id": task_id,
        "title": title,
        "detail": "do real work",
        "purpose": "verify capability",
        "estimated_minutes": 15,
        "required": True,
        "evidence_required": True,
        "evidence_fields": ["source_path", "note"],
        "done_when": ["build passes"],
    }


def _bundle():
    return {
        "schema_version": 1,
        "node_id": "NRPC-S1-01",
        "node_title": "EventLoop 可读事件完整路径",
        "source_plan_version": "x",
        "source_section": "§8",
        "compiler": {"status": "FROZEN"},
        "task_policy": {"single_active_leaf_task": True},
        "task_groups": [
            {"id": "g1", "title": "实现 read path", "items": [_task("T1")]},
            {"id": "must", "title": "能力核对", "items": [_task("M1")]},
            {"id": "gate", "title": "验收准备", "items": [_task("GATE-1")]},
        ],
        "task_count": 3,
        "verification_paper": _paper(),
        "retest_policy": {"new_paper_required_for_retest": True},
    }


def _node():
    return {
        "node_code": "NRPC-S1-01",
        "title": "EventLoop 可读事件完整路径",
        "stage": "1",
        "priority": "CORE",
        "target_score": 80,
        "capability": "write and verify event loop read path",
    }


def test_legacy_gate_is_removed_and_count_recomputed():
    bundle = _bundle()
    normalize_bundle_for_learning(bundle)
    assert [g["id"] for g in bundle["task_groups"]] == ["g1", "must"]
    assert bundle["task_count"] == 2


def test_stage1_prompt_is_coding_first_and_forbids_gate():
    bundle = _bundle()
    normalize_bundle_for_learning(bundle)
    prompt = build_refinement_ai_prompt(_node(), bundle)
    assert "【BUILD 节点硬规则】" in prompt
    assert "第一组第一个实质任务必须尽快产生真实工程修改" in prompt
    assert "至少一半任务" in prompt
    assert "禁止生成 gate / 验收准备任务组" in prompt


def test_structure_diff_allows_legacy_gate_removal_but_protects_technical_groups():
    old = _bundle()
    new = copy.deepcopy(old)
    new["task_groups"] = [g for g in new["task_groups"] if g["id"] != "gate"]
    new["task_count"] = 2
    result = analyze_refinement_structure(old, new)
    assert result["errors"] == []
    assert result["old_groups"] == 2
    assert result["new_groups"] == 2

    broken = copy.deepcopy(new)
    broken["task_groups"] = [g for g in broken["task_groups"] if g["id"] != "g1"]
    broken["task_count"] = 1
    result = analyze_refinement_structure(new, broken)
    assert result["errors"]


def test_structure_diff_detects_modified_task():
    old = _bundle()
    normalize_bundle_for_learning(old)
    new = copy.deepcopy(old)
    new["task_groups"][0]["items"][0]["detail"] = "new implementation detail"
    result = analyze_refinement_structure(old, new)
    assert result["modified_task_ids"] == ["T1"]


def _insert_single_node(db):
    import json
    from learningci.core.service import now_iso
    now = now_iso()
    cur = db.conn.execute(
        "INSERT INTO plans(plan_code,name,version,plan_hash,source_path,imported_at) VALUES(?,?,?,?,?,?)",
        ("P", "Plan", "1", "hash", "plan.json", now),
    )
    plan_id = int(cur.lastrowid)
    cur = db.conn.execute(
        """INSERT INTO nodes(
            plan_id,node_code,stage,order_index,title,capability,priority,target_score,status,
            tasks_json,must_learn_json,out_of_scope_json,scoring_json,project_anchor_json,created_at,updated_at
        ) VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
        (
            plan_id, "NRPC-S1-01", "1", 1, "EventLoop 可读事件完整路径", "cap", "CORE", 80, "READY",
            "[]", "[]", "[]", "{}", "{}", now, now,
        ),
    )
    db.conn.commit()
    return int(cur.lastrowid)


def test_frozen_child_bundle_can_be_revised_without_erasing_unchanged_progress(tmp_path, monkeypatch):
    import json
    import learningci.core.refinement_bridge as bridge
    import learningci.core.service as service_module
    from learningci.core.bundle_loader import ensure_bundles_imported
    from learningci.core.service import LearningService
    from learningci.database import Database

    bundle_dir = tmp_path / "bundles"
    bundle_dir.mkdir()
    proposed = tmp_path / "proposed"
    proposed.mkdir()
    db = Database(tmp_path / "learningci.db")
    db.initialize()
    node_id = _insert_single_node(db)

    old = _bundle()
    old["compiler"]["status"] = "FROZEN"
    (bundle_dir / "NRPC-S1-01.json").write_text(json.dumps(old, ensure_ascii=False), encoding="utf-8")
    ensure_bundles_imported(db, bundle_dir)

    # Existing learning evidence must survive when its task definition is unchanged.
    now = "2026-01-01T00:00:00"
    db.conn.execute(
        """INSERT INTO leaf_task_progress(node_id,task_code,completed,completed_at,updated_at)
           VALUES(?,?,1,?,?)""",
        (node_id, "T1", now, now),
    )
    db.conn.execute(
        """INSERT INTO leaf_task_progress(node_id,task_code,completed,completed_at,updated_at)
           VALUES(?,?,1,?,?)""",
        (node_id, "M1", now, now),
    )
    db.conn.commit()

    candidate = copy.deepcopy(old)
    candidate["compiler"]["status"] = "REVIEWED"
    candidate["task_groups"] = [g for g in candidate["task_groups"] if g["id"] != "gate"]
    candidate["task_groups"][0]["items"].append(_task("T2", "new coding task"))
    candidate["task_groups"][1]["items"][0]["detail"] = "changed mastery check"
    candidate["task_count"] = 3
    staged = tmp_path / "candidate.json"
    staged.write_text(json.dumps(candidate, ensure_ascii=False), encoding="utf-8")

    monkeypatch.setattr(bridge, "DEFAULT_BUNDLE_DIR", bundle_dir)
    monkeypatch.setattr(service_module, "DEFAULT_BUNDLE_DIR", bundle_dir)

    service = LearningService(db)
    result = service.apply_refined_bundle(node_id, staged)
    assert result["new_state"] == "FROZEN"

    rows = {
        row["task_code"]: dict(row)
        for row in db.conn.execute("SELECT * FROM leaf_task_progress WHERE node_id=?", (node_id,)).fetchall()
    }
    assert rows["T1"]["completed"] == 1  # unchanged task preserved
    assert rows["M1"]["completed"] == 0  # changed definition reopened
    assert rows["T2"]["completed"] == 0  # new task created

    stored = service.get_node_bundle(node_id)
    assert "gate" not in [g["id"] for g in stored["task_groups"]]
    db.close()
