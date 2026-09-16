from __future__ import annotations

import json
from collections import defaultdict
from datetime import date, datetime, timedelta
from pathlib import Path
from typing import Any

from learningci.config import (
    DEFAULT_BUNDLE_DIR, REPO_ROOT, SYNC_DB_PATH,
)
from learningci.core.scoring import DEFAULT_MINIMUMS, evaluate_scores
from learningci.core.bundle_loader import ensure_bundles_imported, validate_bundle
from learningci.core.refinement_bridge import (
    backup_bundle_file, export_refinement_package as build_refinement_zip,
    install_reviewed_bundle, stage_candidate_file,
)
from learningci.database import Database


def now_iso() -> str:
    return datetime.now().isoformat(timespec="seconds")


def today_iso() -> str:
    return date.today().isoformat()


def row_to_dict(row) -> dict | None:
    return dict(row) if row is not None else None


class LearningService:
    def __init__(self, db: Database):
        self.db = db

    # ---------- Plan / nodes ----------
    def list_nodes(self) -> list[dict]:
        rows = self.db.conn.execute("SELECT * FROM nodes ORDER BY order_index").fetchall()
        return [self._decode_node(dict(r)) for r in rows]

    def get_node(self, node_id: int) -> dict:
        row = self.db.conn.execute("SELECT * FROM nodes WHERE id=?", (node_id,)).fetchone()
        if not row:
            raise KeyError(node_id)
        return self._decode_node(dict(row))

    def get_node_by_code(self, node_code: str) -> dict:
        row = self.db.conn.execute("SELECT * FROM nodes WHERE node_code=?", (node_code,)).fetchone()
        if not row:
            raise KeyError(node_code)
        return self._decode_node(dict(row))

    def get_active_node(self) -> dict | None:
        row = self.db.conn.execute(
            "SELECT * FROM nodes WHERE status != 'PASSED' AND priority != 'OPTIONAL' ORDER BY order_index LIMIT 1"
        ).fetchone()
        if not row:
            return None
        node = self._decode_node(dict(row))
        state = self.get_bundle_state(node["id"])
        # A REVIEWED package becomes immutable the first time it actually reaches the front of
        # the mainline. GENERATED means the next level has not been prepared yet, so Today must
        # stop instead of silently using a coarse draft.
        if state == "REVIEWED":
            self.freeze_node_bundle(node["id"])
            state = "FROZEN"
        node["bundle_state"] = state
        if state == "FROZEN":
            self.ensure_leaf_task_rows(node["id"])
        return node

    def _decode_node(self, node: dict) -> dict:
        for field in ("tasks_json", "must_learn_json", "out_of_scope_json", "scoring_json", "project_anchor_json"):
            node[field[:-5] if field.endswith("_json") else field] = json.loads(node[field])
        return node

    # ---------- Node execution packages ----------
    def get_node_bundle(self, node_id: int) -> dict:
        row = self.db.conn.execute(
            "SELECT bundle_json,bundle_hash,source_path,bundle_state,revision,updated_at FROM node_bundles WHERE node_id=?",
            (node_id,),
        ).fetchone()
        if not row:
            raise RuntimeError(f"node {node_id} 没有导入节点执行包")
        bundle = json.loads(row["bundle_json"])
        bundle["_bundle_hash"] = row["bundle_hash"]
        bundle["_source_path"] = row["source_path"]
        bundle["_bundle_state"] = row["bundle_state"]
        bundle["_revision"] = int(row["revision"] or 1)
        bundle["_updated_at"] = row["updated_at"]
        return bundle

    def get_bundle_state(self, node_id: int) -> str:
        row = self.db.conn.execute(
            "SELECT bundle_state FROM node_bundles WHERE node_id=?", (node_id,)
        ).fetchone()
        if not row:
            return "MISSING"
        return str(row["bundle_state"] or "GENERATED").upper()

    def get_bundle_info(self, node_id: int) -> dict:
        row = self.db.conn.execute(
            "SELECT bundle_state,revision,bundle_hash,source_path,updated_at,bundle_json FROM node_bundles WHERE node_id=?",
            (node_id,),
        ).fetchone()
        if not row:
            return {"state": "MISSING", "revision": 0, "task_count": 0, "paper_id": "-"}
        bundle = json.loads(row["bundle_json"])
        return {
            "state": str(row["bundle_state"] or "GENERATED").upper(),
            "revision": int(row["revision"] or 1),
            "task_count": int(bundle.get("task_count", 0) or 0),
            "paper_id": str(bundle.get("verification_paper", {}).get("paper_id", "-")),
            "hash": row["bundle_hash"],
            "source_path": row["source_path"],
            "updated_at": row["updated_at"],
        }

    def _node_has_runtime_data(self, node_id: int) -> bool:
        checks = [
            ("SELECT 1 FROM leaf_task_progress WHERE node_id=? AND (completed=1 OR total_seconds>0 OR first_started_at IS NOT NULL) LIMIT 1", (node_id,)),
            ("SELECT 1 FROM focus_sessions WHERE node_id=? LIMIT 1", (node_id,)),
            ("SELECT 1 FROM attempts WHERE node_id=? LIMIT 1", (node_id,)),
            ("SELECT 1 FROM score_records WHERE node_id=? LIMIT 1", (node_id,)),
        ]
        return any(self.db.conn.execute(sql, params).fetchone() for sql, params in checks)

    def freeze_node_bundle(self, node_id: int) -> None:
        info = self.get_bundle_info(node_id)
        if info["state"] == "FROZEN":
            return
        if info["state"] != "REVIEWED":
            node = self.get_node(node_id)
            raise RuntimeError(
                f"{node['node_code']} 的节点执行包仍是草稿状态。\n\n"
                "请先到“节点准备”页导出细化包，让 ChatGPT 细化并导回；审核后才能进入正式学习。"
            )
        self.db.conn.execute(
            "UPDATE node_bundles SET bundle_state='FROZEN',updated_at=? WHERE node_id=?",
            (now_iso(), node_id),
        )
        self.db.conn.commit()

    def _previous_context(self, node: dict) -> dict:
        rows = self.db.conn.execute(
            """SELECT node_code,title,status,current_score,best_score,stable_score,first_pass_at
               FROM nodes WHERE order_index < ? ORDER BY order_index DESC LIMIT 3""",
            (node["order_index"],),
        ).fetchall()
        return {
            "current_node": node["node_code"],
            "previous_nodes": [dict(r) for r in reversed(rows)],
            "note": "这里只提供已经发生的学习状态，不能用于改变当前节点路线。",
        }

    def _preparation_window_ids(self, limit: int = 3) -> set[int]:
        """只允许细化当前节点和后面两个未完成主线节点。"""
        rows = self.db.conn.execute(
            """SELECT id FROM nodes
               WHERE status != 'PASSED' AND priority != 'OPTIONAL'
               ORDER BY order_index LIMIT ?""",
            (limit,),
        ).fetchall()
        return {int(r["id"]) for r in rows}

    def _assert_in_preparation_window(self, node_id: int) -> None:
        if node_id not in self._preparation_window_ids():
            node = self.get_node(node_id)
            raise RuntimeError(
                f"{node['node_code']} 还没有进入三节点准备窗口。\n\n"
                "LearningCI 只允许细化当前节点和后面两个主线节点，避免提前优化很远的任务。"
            )

    def export_refinement_package(self, node_id: int, output_path: Path | None = None) -> Path:
        self._assert_in_preparation_window(node_id)
        node = self.get_node(node_id)
        info = self.get_bundle_info(node_id)
        if info["state"] == "FROZEN" or self._node_has_runtime_data(node_id):
            raise RuntimeError("这个节点已经冻结或已经产生学习记录，不能重新细化。")
        bundle = self.get_node_bundle(node_id)
        schema_path = REPO_ROOT / "schemas" / "节点执行包结构.json"
        return build_refinement_zip(node, bundle, self._previous_context(node), schema_path, output_path)

    def _validate_refined_data(self, node: dict, data: dict) -> str:
        validate_bundle(data, node["node_code"])
        if str(data.get("node_title", "")).strip() != node["title"]:
            raise ValueError(
                f"返回文件 Title 与冻结路线不一致：{data.get('node_title')} != {node['title']}"
            )
        paper_id = str(data.get("verification_paper", {}).get("paper_id", ""))
        if not paper_id.startswith(node["node_code"]):
            raise ValueError("固定试卷 ID 必须属于当前 Node。")
        return paper_id

    def preview_refined_bundle(self, node_id: int, source_path: Path) -> dict:
        """校验 ChatGPT 返回文件并放入待审核目录，不立即覆盖正式执行包。"""
        self._assert_in_preparation_window(node_id)
        node = self.get_node(node_id)
        info = self.get_bundle_info(node_id)
        if info["state"] == "FROZEN" or self._node_has_runtime_data(node_id):
            raise RuntimeError("这个节点已经冻结或已经产生学习记录，不能覆盖执行包。")
        old_bundle = self.get_node_bundle(node_id)
        data, staged = stage_candidate_file(Path(source_path), node["node_code"])
        paper_id = self._validate_refined_data(node, data)
        return {
            "node_code": node["node_code"],
            "old_tasks": int(old_bundle.get("task_count", 0) or 0),
            "new_tasks": int(data.get("task_count", 0) or 0),
            "old_groups": len(old_bundle.get("task_groups", [])),
            "new_groups": len(data.get("task_groups", [])),
            "old_state": info["state"],
            "new_state": "REVIEWED",
            "next_revision": int(info["revision"] or 1) + 1,
            "staged_path": str(staged),
            "paper_id": paper_id,
        }

    def apply_refined_bundle(self, node_id: int, staged_path: Path) -> dict:
        """用户确认后，把待审核执行包替换为正式执行包。"""
        self._assert_in_preparation_window(node_id)
        node = self.get_node(node_id)
        info = self.get_bundle_info(node_id)
        if info["state"] == "FROZEN" or self._node_has_runtime_data(node_id):
            raise RuntimeError("这个节点已经冻结或已经产生学习记录，不能覆盖执行包。")
        old_bundle = self.get_node_bundle(node_id)
        data = json.loads(Path(staged_path).read_text(encoding="utf-8"))
        paper_id = self._validate_refined_data(node, data)
        backup = backup_bundle_file(node["node_code"], info["revision"])
        installed = install_reviewed_bundle(node["node_code"], data)
        self.db.conn.execute("DELETE FROM leaf_task_progress WHERE node_id=?", (node_id,))
        self.db.conn.commit()
        ensure_bundles_imported(self.db, DEFAULT_BUNDLE_DIR)
        new_info = self.get_bundle_info(node_id)
        return {
            "node_code": node["node_code"],
            "old_tasks": int(old_bundle.get("task_count", 0) or 0),
            "new_tasks": int(data.get("task_count", 0) or 0),
            "old_state": info["state"],
            "new_state": new_info["state"],
            "revision": new_info["revision"],
            "staged_path": str(staged_path),
            "installed_path": str(installed),
            "backup_path": str(backup) if backup else "",
            "paper_id": paper_id,
        }

    def import_refined_bundle(self, node_id: int, source_path: Path) -> dict:
        """兼容旧调用：先校验暂存，再立即安装。"""
        preview = self.preview_refined_bundle(node_id, source_path)
        return self.apply_refined_bundle(node_id, Path(preview["staged_path"]))

    def list_preparation_nodes(self) -> list[dict]:
        nodes = self.list_nodes()
        active_code = None
        window_ids = self._preparation_window_ids()
        for n in nodes:
            if n["priority"] != "OPTIONAL" and n["status"] != "PASSED":
                active_code = n["node_code"]
                break
        out = []
        for node in nodes:
            info = self.get_bundle_info(node["id"])
            row = dict(node)
            row["bundle_state"] = info["state"]
            row["bundle_revision"] = info["revision"]
            row["task_count"] = info["task_count"]
            row["paper_id"] = info["paper_id"]
            row["in_prepare_window"] = node["id"] in window_ids
            if node["status"] == "PASSED":
                learning_state = "PASSED"
            elif node["node_code"] == active_code:
                learning_state = "CURRENT" if info["state"] in {"REVIEWED", "FROZEN"} else "PREP_REQUIRED"
            elif node["priority"] == "OPTIONAL":
                learning_state = "OPTIONAL"
            else:
                learning_state = "LOCKED"
            row["learning_state"] = learning_state
            out.append(row)
        return out

    def get_frozen_verification_paper(self, node_id: int) -> dict:
        row = self.db.conn.execute(
            "SELECT * FROM assessment_papers WHERE node_id=? AND paper_kind='VERIFICATION' ORDER BY paper_version DESC LIMIT 1",
            (node_id,),
        ).fetchone()
        if not row:
            raise RuntimeError("当前节点没有固定 Verification 试卷")
        data = json.loads(row["paper_json"])
        data["_paper_hash"] = row["paper_hash"]
        data["_paper_code"] = row["paper_code"]
        return data

    # ---------- Legacy coarse daily tasks ----------
    def ensure_day_tasks(self, node_id: int, day: str) -> None:
        node = self.get_node(node_id)
        with self.db.transaction() as conn:
            for idx, _ in enumerate(node["tasks"]):
                conn.execute(
                    "INSERT OR IGNORE INTO task_progress(day,node_id,task_index,completed) VALUES(?,?,?,0)",
                    (day, node_id, idx),
                )

    def get_task_states(self, node_id: int, day: str | None = None) -> list[dict]:
        # Kept for v0.1.x compatibility/tests. v0.2 UI uses leaf tasks.
        day = day or today_iso()
        self.ensure_day_tasks(node_id, day)
        node = self.get_node(node_id)
        rows = self.db.conn.execute(
            "SELECT task_index,completed FROM task_progress WHERE day=? AND node_id=? ORDER BY task_index",
            (day, node_id),
        ).fetchall()
        state = {int(r["task_index"]): bool(r["completed"]) for r in rows}
        return [
            {"index": idx, "text": text, "completed": state.get(idx, False)}
            for idx, text in enumerate(node["tasks"])
        ]

    def set_task_completed(self, node_id: int, task_index: int, completed: bool, day: str | None = None) -> None:
        day = day or today_iso()
        self.ensure_day_tasks(node_id, day)
        self.db.conn.execute(
            "UPDATE task_progress SET completed=?, completed_at=? WHERE day=? AND node_id=? AND task_index=?",
            (1 if completed else 0, now_iso() if completed else None, day, node_id, task_index),
        )
        self.db.conn.commit()

    # ---------- Detailed leaf tasks ----------
    def _flatten_bundle_tasks(self, node_id: int) -> list[dict]:
        bundle = self.get_node_bundle(node_id)
        output: list[dict] = []
        for group_index, group in enumerate(bundle.get("task_groups", [])):
            for item_index, item in enumerate(group.get("items", [])):
                task = dict(item)
                task["group_id"] = group.get("id")
                task["group_title"] = group.get("title", "")
                task["group_description"] = group.get("description", "")
                task["group_index"] = group_index
                task["item_index"] = item_index
                output.append(task)
        return output

    def ensure_leaf_task_rows(self, node_id: int) -> None:
        tasks = self._flatten_bundle_tasks(node_id)
        now = now_iso()
        with self.db.transaction() as conn:
            for task in tasks:
                conn.execute(
                    """INSERT OR IGNORE INTO leaf_task_progress(
                        node_id,task_code,completed,total_seconds,updated_at
                    ) VALUES(?,?,0,0,?)""",
                    (node_id, task["id"], now),
                )

    def get_leaf_task_tree(self, node_id: int) -> list[dict]:
        self.ensure_leaf_task_rows(node_id)
        bundle = self.get_node_bundle(node_id)
        rows = self.db.conn.execute(
            "SELECT * FROM leaf_task_progress WHERE node_id=?", (node_id,)
        ).fetchall()
        state = {r["task_code"]: dict(r) for r in rows}
        active = self.active_task_session()
        tree: list[dict] = []
        for group in bundle.get("task_groups", []):
            g = {
                "id": group.get("id"),
                "title": group.get("title", ""),
                "description": group.get("description", ""),
                "items": [],
            }
            for item in group.get("items", []):
                t = dict(item)
                s = state.get(item["id"], {})
                t.update({
                    "completed": bool(s.get("completed", 0)),
                    "completed_at": s.get("completed_at"),
                    "source_path": s.get("source_path", ""),
                    "function_name": s.get("function_name", ""),
                    "evidence_note": s.get("evidence_note", ""),
                    "total_seconds": int(s.get("total_seconds", 0) or 0),
                    "first_started_at": s.get("first_started_at"),
                    "in_progress": bool(active and active["node_id"] == node_id and active["task_code"] == item["id"]),
                })
                g["items"].append(t)
            tree.append(g)
        return tree

    def get_leaf_task(self, node_id: int, task_code: str) -> dict:
        for task in self._flatten_bundle_tasks(node_id):
            if task["id"] == task_code:
                row = self.db.conn.execute(
                    "SELECT * FROM leaf_task_progress WHERE node_id=? AND task_code=?", (node_id, task_code)
                ).fetchone()
                if row:
                    task.update(dict(row))
                    task["completed"] = bool(task["completed"])
                return task
        raise KeyError(task_code)

    def save_leaf_task_evidence(
        self, node_id: int, task_code: str, source_path: str = "", function_name: str = "", note: str = ""
    ) -> None:
        self.ensure_leaf_task_rows(node_id)
        self.db.conn.execute(
            """UPDATE leaf_task_progress
               SET source_path=?, function_name=?, evidence_note=?, updated_at=?
               WHERE node_id=? AND task_code=?""",
            (source_path.strip(), function_name.strip(), note.strip(), now_iso(), node_id, task_code),
        )
        self.db.conn.commit()

    def set_leaf_task_completed(self, node_id: int, task_code: str, completed: bool) -> None:
        self.ensure_leaf_task_rows(node_id)
        task = self.get_leaf_task(node_id, task_code)
        if completed and task.get("evidence_required"):
            has_evidence = bool(
                str(task.get("source_path", "")).strip()
                or str(task.get("function_name", "")).strip()
                or str(task.get("evidence_note", "")).strip()
            )
            if not has_evidence:
                raise ValueError("这个叶子任务要求留下证据。先填写源码路径、函数名或证据备注，再完成打卡。")
        self.db.conn.execute(
            """UPDATE leaf_task_progress
               SET completed=?, completed_at=?, updated_at=?
               WHERE node_id=? AND task_code=?""",
            (1 if completed else 0, now_iso() if completed else None, now_iso(), node_id, task_code),
        )
        self.db.conn.commit()
        self._update_daily_snapshot(node_id)

    def task_completion(self, node_id: int, day: str | None = None) -> tuple[int, int, int]:
        """v0.2: verification gate is based on required leaf tasks, not the old 3 coarse checkboxes."""
        try:
            tree = self.get_leaf_task_tree(node_id)
            required = [item for group in tree for item in group["items"] if item.get("required", True)]
            total = len(required)
            done = sum(1 for item in required if item.get("completed"))
            pct = 100 if total == 0 else round(done * 100 / total)
            return done, total, pct
        except RuntimeError:
            states = self.get_task_states(node_id, day)
            total = len(states)
            done = sum(1 for s in states if s["completed"])
            pct = 100 if total == 0 else round(done * 100 / total)
            return done, total, pct

    def _update_daily_snapshot(self, node_id: int) -> None:
        try:
            tree = self.get_leaf_task_tree_no_ensure(node_id)
        except Exception:
            return
        required = [i for g in tree for i in g["items"] if i.get("required", True)]
        total = len(required)
        done = sum(1 for i in required if i.get("completed"))
        pct = 100 if total == 0 else round(done * 100 / total)
        self.db.conn.execute(
            """INSERT INTO daily_progress_snapshots(day,node_id,done_required,total_required,completion_pct,updated_at)
               VALUES(?,?,?,?,?,?)
               ON CONFLICT(day,node_id) DO UPDATE SET
                 done_required=excluded.done_required,
                 total_required=excluded.total_required,
                 completion_pct=excluded.completion_pct,
                 updated_at=excluded.updated_at""",
            (today_iso(), node_id, done, total, pct, now_iso()),
        )
        self.db.conn.commit()

    def get_leaf_task_tree_no_ensure(self, node_id: int) -> list[dict]:
        bundle = self.get_node_bundle(node_id)
        rows = self.db.conn.execute("SELECT * FROM leaf_task_progress WHERE node_id=?", (node_id,)).fetchall()
        state = {r["task_code"]: dict(r) for r in rows}
        tree = []
        for group in bundle.get("task_groups", []):
            g = {"id": group.get("id"), "title": group.get("title", ""), "description": group.get("description", ""), "items": []}
            for item in group.get("items", []):
                t = dict(item)
                s = state.get(item["id"], {})
                t.update({
                    "completed": bool(s.get("completed", 0)),
                    "completed_at": s.get("completed_at"),
                    "source_path": s.get("source_path", ""),
                    "function_name": s.get("function_name", ""),
                    "evidence_note": s.get("evidence_note", ""),
                    "total_seconds": int(s.get("total_seconds", 0) or 0),
                })
                g["items"].append(t)
            tree.append(g)
        return tree

    # ---------- Focus timer ----------
    def active_focus_session(self) -> dict | None:
        row = self.db.conn.execute(
            "SELECT * FROM focus_sessions WHERE ended_at IS NULL ORDER BY id DESC LIMIT 1"
        ).fetchone()
        return row_to_dict(row)

    def start_focus(self, node_id: int) -> dict:
        active = self.active_focus_session()
        if active:
            return active
        now = now_iso()
        cur = self.db.conn.execute(
            "INSERT INTO focus_sessions(node_id,started_at,created_at) VALUES(?,?,?)",
            (node_id, now, now),
        )
        self.db.conn.commit()
        self._update_daily_snapshot(node_id)
        return row_to_dict(self.db.conn.execute("SELECT * FROM focus_sessions WHERE id=?", (cur.lastrowid,)).fetchone())

    def end_focus(self) -> int:
        # Leaf task timer is a category timer inside the overall focus session; stop it first.
        if self.active_task_session():
            self.end_task_focus()
        active = self.active_focus_session()
        if not active:
            return 0
        end = datetime.now()
        start = datetime.fromisoformat(active["started_at"])
        seconds = max(0, int((end - start).total_seconds()))
        self.db.conn.execute(
            "UPDATE focus_sessions SET ended_at=?, duration_seconds=? WHERE id=?",
            (end.isoformat(timespec="seconds"), seconds, active["id"]),
        )
        self.db.conn.commit()
        return seconds

    def active_task_session(self) -> dict | None:
        row = self.db.conn.execute(
            "SELECT * FROM task_focus_sessions WHERE ended_at IS NULL ORDER BY id DESC LIMIT 1"
        ).fetchone()
        return row_to_dict(row)

    def start_task_focus(self, node_id: int, task_code: str) -> dict:
        self.ensure_leaf_task_rows(node_id)
        active = self.active_task_session()
        if active and active["node_id"] == node_id and active["task_code"] == task_code:
            return active
        if active:
            self.end_task_focus()
        if not self.active_focus_session():
            self.start_focus(node_id)
        now = now_iso()
        self.db.conn.execute(
            """UPDATE leaf_task_progress SET first_started_at=COALESCE(first_started_at,?), updated_at=?
               WHERE node_id=? AND task_code=?""",
            (now, now, node_id, task_code),
        )
        cur = self.db.conn.execute(
            "INSERT INTO task_focus_sessions(node_id,task_code,started_at,created_at) VALUES(?,?,?,?)",
            (node_id, task_code, now, now),
        )
        self.db.conn.commit()
        return row_to_dict(self.db.conn.execute("SELECT * FROM task_focus_sessions WHERE id=?", (cur.lastrowid,)).fetchone())

    def end_task_focus(self) -> int:
        active = self.active_task_session()
        if not active:
            return 0
        end = datetime.now()
        start = datetime.fromisoformat(active["started_at"])
        seconds = max(0, int((end - start).total_seconds()))
        with self.db.transaction() as conn:
            conn.execute(
                "UPDATE task_focus_sessions SET ended_at=?,duration_seconds=? WHERE id=?",
                (end.isoformat(timespec="seconds"), seconds, active["id"]),
            )
            conn.execute(
                """UPDATE leaf_task_progress SET total_seconds=total_seconds+?, updated_at=?
                   WHERE node_id=? AND task_code=?""",
                (seconds, now_iso(), active["node_id"], active["task_code"]),
            )
        return seconds

    def focus_seconds(self, start_day: date, end_day: date | None = None, include_active: bool = True) -> int:
        end_day = end_day or date.today()
        start_dt = datetime.combine(start_day, datetime.min.time())
        end_dt = datetime.combine(end_day + timedelta(days=1), datetime.min.time())
        rows = self.db.conn.execute(
            "SELECT * FROM focus_sessions WHERE started_at >= ? AND started_at < ?",
            (start_dt.isoformat(timespec="seconds"), end_dt.isoformat(timespec="seconds")),
        ).fetchall()
        total = 0
        now = datetime.now()
        for row in rows:
            if row["duration_seconds"] is not None:
                total += int(row["duration_seconds"])
            elif include_active:
                total += max(0, int((now - datetime.fromisoformat(row["started_at"])).total_seconds()))
        return total

    def focus_summary(self) -> dict[str, int]:
        today = date.today()
        week_start = today - timedelta(days=today.weekday())
        month_start = today.replace(day=1)
        return {
            "today": self.focus_seconds(today),
            "week": self.focus_seconds(week_start),
            "month": self.focus_seconds(month_start),
        }

    # ---------- Attempts / fixed paper ----------
    def previous_tests(self, node_id: int, limit: int = 3) -> list[dict]:
        rows = self.db.conn.execute(
            "SELECT test_json FROM attempts WHERE node_id=? ORDER BY id DESC LIMIT ?", (node_id, limit)
        ).fetchall()
        out = []
        for r in reversed(rows):
            try:
                out.append(json.loads(r["test_json"]))
            except json.JSONDecodeError:
                pass
        return out

    def create_attempt(self, node_id: int, test_json: dict, review_id: int | None = None) -> int:
        row = self.db.conn.execute(
            "SELECT COALESCE(MAX(attempt_no),0)+1 AS n FROM attempts WHERE node_id=?", (node_id,)
        ).fetchone()
        attempt_no = int(row["n"])
        kind = "RETEST" if review_id else "VERIFICATION"
        cur = self.db.conn.execute(
            """INSERT INTO attempts(node_id,review_id,attempt_no,attempt_kind,test_json,created_at)
               VALUES(?,?,?,?,?,?)""",
            (node_id, review_id, attempt_no, kind, json.dumps(test_json, ensure_ascii=False), now_iso()),
        )
        self.db.conn.commit()
        return int(cur.lastrowid)

    def ensure_verification_attempt(self, node_id: int) -> int:
        row = self.db.conn.execute(
            """SELECT id,status FROM attempts
               WHERE node_id=? AND review_id IS NULL AND attempt_kind='VERIFICATION'
               ORDER BY id DESC LIMIT 1""",
            (node_id,),
        ).fetchone()
        if row and row["status"] == "OPEN":
            return int(row["id"])
        paper = self.get_frozen_verification_paper(node_id)
        clean = {k: v for k, v in paper.items() if not k.startswith("_")}
        return self.create_attempt(node_id, clean, None)

    def get_attempt(self, attempt_id: int) -> dict:
        row = self.db.conn.execute("SELECT * FROM attempts WHERE id=?", (attempt_id,)).fetchone()
        if not row:
            raise KeyError(attempt_id)
        data = dict(row)
        data["test"] = json.loads(data["test_json"])
        try:
            data["answers"] = json.loads(data["answer_text"]) if data["answer_text"] else {}
        except json.JSONDecodeError:
            data["answers"] = {}
        return data

    def save_answer(self, attempt_id: int, answer_text: str) -> None:
        self.db.conn.execute("UPDATE attempts SET answer_text=? WHERE id=?", (answer_text, attempt_id))
        self.db.conn.commit()

    def grade_attempt(self, attempt_id: int, grade: dict) -> dict:
        attempt = self.get_attempt(attempt_id)
        node = self.get_node(int(attempt["node_id"]))
        scores = grade.get("scores", {})
        scoring = node.get("scoring", {})
        minimums = scoring.get("minimums", DEFAULT_MINIMUMS)
        result = evaluate_scores(scores, node["target_score"], minimums)
        now = now_iso()
        day = today_iso()
        with self.db.transaction() as conn:
            conn.execute(
                """INSERT INTO score_records(
                    attempt_id,node_id,score_day,explanation,prediction,implementation,diagnosis,transfer,total,passed,
                    evidence_json,weaknesses_json,created_at
                ) VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?)""",
                (
                    attempt_id, node["id"], day,
                    int(scores["explanation"]), int(scores["prediction"]), int(scores["implementation"]),
                    int(scores["diagnosis"]), int(scores["transfer"]), result.total, 1 if result.passed else 0,
                    json.dumps(grade.get("evidence", {}), ensure_ascii=False),
                    json.dumps(grade.get("weaknesses", []), ensure_ascii=False), now,
                ),
            )
            score_id = int(conn.execute("SELECT last_insert_rowid() AS id").fetchone()["id"])
            conn.execute(
                "UPDATE attempts SET status=?, graded_at=? WHERE id=?",
                ("PASSED" if result.passed else "FAILED", now, attempt_id),
            )

            if attempt["review_id"]:
                conn.execute(
                    "UPDATE reviews SET status=?, completed_attempt_id=? WHERE id=?",
                    ("DONE" if result.passed else "FAILED", attempt_id, attempt["review_id"]),
                )
                if result.passed:
                    conn.execute(
                        "UPDATE reviews SET status='CANCELLED' WHERE node_id=? AND review_type='REPAIR' AND status='PENDING'",
                        (node["id"],),
                    )
                else:
                    repair_due = (date.today() + timedelta(days=1)).isoformat()
                    conn.execute(
                        "INSERT OR IGNORE INTO reviews(node_id,review_type,due_date,status,source_score_id,created_at) VALUES(?,?,?,?,?,?)",
                        (node["id"], "REPAIR", repair_due, "PENDING", score_id, now),
                    )
            else:
                if result.passed:
                    first_pass = node.get("first_pass_at") or now
                    conn.execute(
                        "UPDATE nodes SET status='PASSED', first_pass_at=?, updated_at=? WHERE id=?",
                        (first_pass, now, node["id"]),
                    )
                    self._schedule_reviews(conn, node["id"], result.total, score_id, now)
                else:
                    conn.execute("UPDATE nodes SET status='FAILED', updated_at=? WHERE id=?", (now, node["id"]))

        self._refresh_node_scores(node["id"])
        return {"total": result.total, "passed": result.passed, "failures": list(result.failures)}

    def _schedule_reviews(self, conn, node_id: int, total: int, score_id: int, now: str) -> None:
        if total <= 84:
            schedule = [(3, "3D"), (7, "7D"), (30, "30D")]
        elif total <= 89:
            schedule = [(7, "7D"), (30, "30D")]
        else:
            schedule = [(14, "14D"), (30, "30D")]
        for days, kind in schedule:
            due = (date.today() + timedelta(days=days)).isoformat()
            conn.execute(
                "INSERT OR IGNORE INTO reviews(node_id,review_type,due_date,status,source_score_id,created_at) VALUES(?,?,?,?,?,?)",
                (node_id, kind, due, "PENDING", score_id, now),
            )

    def _refresh_node_scores(self, node_id: int) -> None:
        node_row = self.db.conn.execute("SELECT first_pass_at FROM nodes WHERE id=?", (node_id,)).fetchone()
        scores = self.db.conn.execute(
            "SELECT total,created_at FROM score_records WHERE node_id=? ORDER BY created_at", (node_id,)
        ).fetchall()
        if not scores:
            return
        current = int(scores[-1]["total"])
        best = max(int(r["total"]) for r in scores)
        first_pass_at = node_row["first_pass_at"]
        if first_pass_at:
            stable_values = [int(r["total"]) for r in scores if r["created_at"] >= first_pass_at]
            stable = min(stable_values) if stable_values else current
        else:
            stable = current
        self.db.conn.execute(
            "UPDATE nodes SET current_score=?,best_score=?,stable_score=?,updated_at=? WHERE id=?",
            (current, best, stable, now_iso(), node_id),
        )
        self.db.conn.commit()

    # ---------- Reviews ----------
    def due_reviews(self, include_future: bool = False) -> list[dict]:
        sql = """SELECT r.*, n.node_code,n.title,n.stable_score
                 FROM reviews r JOIN nodes n ON n.id=r.node_id
                 WHERE r.status='PENDING'"""
        params: tuple[Any, ...] = ()
        if not include_future:
            sql += " AND r.due_date <= ?"
            params = (today_iso(),)
        sql += " ORDER BY r.due_date, n.order_index"
        return [dict(r) for r in self.db.conn.execute(sql, params).fetchall()]

    # ---------- Parking lot ----------
    def add_parking_item(self, content: str, source_node_id: int | None) -> None:
        content = content.strip()
        if not content:
            return
        self.db.conn.execute(
            "INSERT INTO parking_lot(content,source_node_id,created_at) VALUES(?,?,?)",
            (content, source_node_id, now_iso()),
        )
        self.db.conn.commit()

    def list_parking(self) -> list[dict]:
        rows = self.db.conn.execute(
            "SELECT p.*, n.node_code FROM parking_lot p LEFT JOIN nodes n ON n.id=p.source_node_id ORDER BY p.id DESC"
        ).fetchall()
        return [dict(r) for r in rows]

    # ---------- Portable SQLite snapshot ----------
    def create_sync_snapshot(self, path: Path | None = None) -> dict:
        target = Path(path or SYNC_DB_PATH)
        self.db.backup_to(target)
        return {
            "path": str(target),
            "size_bytes": target.stat().st_size,
            "integrity": "ok",
            "created_at": now_iso(),
        }

    def restore_sync_snapshot(self, path: Path | None = None) -> dict:
        source = Path(path or SYNC_DB_PATH)
        self.db.restore_from(source)
        # A snapshot may come from an older LearningCI schema. Re-run idempotent migrations
        # and re-import the current frozen plan/bundles after restore.
        self.db.initialize()
        from learningci.config import DEFAULT_BUNDLE_DIR, DEFAULT_PLAN_PATH
        from learningci.core.bundle_loader import ensure_bundles_imported, validate_bundle
        from learningci.core.plan_loader import ensure_plan_imported
        ensure_plan_imported(self.db, DEFAULT_PLAN_PATH)
        ensure_bundles_imported(self.db, DEFAULT_BUNDLE_DIR)
        return {
            "path": str(source),
            "size_bytes": source.stat().st_size,
            "integrity": self.db.integrity_check(),
            "restored_at": now_iso(),
        }

    def sync_snapshot_info(self, path: Path | None = None) -> dict:
        source = Path(path or SYNC_DB_PATH)
        return {
            "exists": source.exists(),
            "path": str(source),
            "size_bytes": source.stat().st_size if source.exists() else 0,
            "mtime": datetime.fromtimestamp(source.stat().st_mtime).isoformat(timespec="seconds") if source.exists() else None,
        }

    # ---------- History / stats ----------
    def daily_history(self, days: int = 90) -> list[dict]:
        end = date.today()
        start = end - timedelta(days=days - 1)
        output = []
        for offset in range(days):
            day = start + timedelta(days=offset)
            ds = day.isoformat()
            focus = self.focus_seconds(day, day, include_active=True)

            snap = self.db.conn.execute(
                "SELECT AVG(completion_pct) avg_pct, COUNT(*) n FROM daily_progress_snapshots WHERE day=?", (ds,)
            ).fetchone()
            if int(snap["n"] or 0):
                completion = round(float(snap["avg_pct"]))
                total_tasks = int(snap["n"])
            else:
                task_row = self.db.conn.execute(
                    "SELECT COUNT(*) total, COALESCE(SUM(completed),0) done FROM task_progress WHERE day=?", (ds,)
                ).fetchone()
                total_tasks = int(task_row["total"])
                done_tasks = int(task_row["done"])
                completion = round(done_tasks * 100 / total_tasks) if total_tasks else None

            score_row = self.db.conn.execute(
                "SELECT AVG(total) avg_score, COUNT(*) exams, SUM(passed) passed FROM score_records WHERE score_day=?", (ds,)
            ).fetchone()
            exams = int(score_row["exams"])
            avg_score = round(float(score_row["avg_score"])) if score_row["avg_score"] is not None else None
            if focus or total_tasks or exams:
                output.append({
                    "day": ds,
                    "focus_seconds": focus,
                    "completion": completion,
                    "avg_score": avg_score,
                    "exams": exams,
                    "passed": int(score_row["passed"] or 0),
                })
        return list(reversed(output))

    def aggregate_history(self, period: str, days: int = 180) -> list[dict]:
        daily = list(reversed(self.daily_history(days)))
        groups: dict[str, list[dict]] = defaultdict(list)
        for row in daily:
            d = date.fromisoformat(row["day"])
            if period == "week":
                iso = d.isocalendar()
                key = f"{iso.year}-W{iso.week:02d}"
            elif period == "month":
                key = f"{d.year}-{d.month:02d}"
            else:
                key = row["day"]
            groups[key].append(row)
        result = []
        for key, rows in sorted(groups.items(), reverse=True):
            focus = sum(r["focus_seconds"] for r in rows)
            completions = [r["completion"] for r in rows if r["completion"] is not None]
            scores = [r["avg_score"] for r in rows if r["avg_score"] is not None]
            result.append({
                "period": key,
                "focus_seconds": focus,
                "completion": round(sum(completions) / len(completions)) if completions else None,
                "avg_score": round(sum(scores) / len(scores)) if scores else None,
                "exams": sum(r["exams"] for r in rows),
                "passed": sum(r["passed"] for r in rows),
            })
        return result
