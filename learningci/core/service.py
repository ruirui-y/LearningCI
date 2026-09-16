from __future__ import annotations

import json
from collections import defaultdict
from datetime import date, datetime, timedelta
from typing import Any

from learningci.core.scoring import DEFAULT_MINIMUMS, evaluate_scores
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
        rows = self.db.conn.execute(
            "SELECT * FROM nodes ORDER BY order_index"
        ).fetchall()
        return [self._decode_node(dict(r)) for r in rows]

    def get_node(self, node_id: int) -> dict:
        row = self.db.conn.execute("SELECT * FROM nodes WHERE id=?", (node_id,)).fetchone()
        if not row:
            raise KeyError(node_id)
        return self._decode_node(dict(row))

    def get_active_node(self) -> dict | None:
        row = self.db.conn.execute(
            "SELECT * FROM nodes WHERE status != 'PASSED' AND priority != 'OPTIONAL' ORDER BY order_index LIMIT 1"
        ).fetchone()
        if not row:
            return None
        node = self._decode_node(dict(row))
        self.ensure_day_tasks(node["id"], today_iso())
        return node

    def _decode_node(self, node: dict) -> dict:
        for field in ("tasks_json", "must_learn_json", "out_of_scope_json", "scoring_json", "project_anchor_json"):
            node[field[:-5] if field.endswith("_json") else field] = json.loads(node[field])
        return node

    # ---------- Daily tasks ----------
    def ensure_day_tasks(self, node_id: int, day: str) -> None:
        node = self.get_node(node_id)
        with self.db.transaction() as conn:
            for idx, _ in enumerate(node["tasks"]):
                conn.execute(
                    "INSERT OR IGNORE INTO task_progress(day,node_id,task_index,completed) VALUES(?,?,?,0)",
                    (day, node_id, idx),
                )

    def get_task_states(self, node_id: int, day: str | None = None) -> list[dict]:
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

    def task_completion(self, node_id: int, day: str | None = None) -> tuple[int, int, int]:
        states = self.get_task_states(node_id, day)
        total = len(states)
        done = sum(1 for s in states if s["completed"])
        pct = 100 if total == 0 else round(done * 100 / total)
        return done, total, pct

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
        return row_to_dict(self.db.conn.execute("SELECT * FROM focus_sessions WHERE id=?", (cur.lastrowid,)).fetchone())

    def end_focus(self) -> int:
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

    # ---------- Attempts / AI bridge ----------
    def previous_tests(self, node_id: int, limit: int = 3) -> list[dict]:
        rows = self.db.conn.execute(
            "SELECT test_json FROM attempts WHERE node_id=? ORDER BY id DESC LIMIT ?",
            (node_id, limit),
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
            "SELECT COALESCE(MAX(attempt_no),0)+1 AS n FROM attempts WHERE node_id=?",
            (node_id,),
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

    def get_attempt(self, attempt_id: int) -> dict:
        row = self.db.conn.execute("SELECT * FROM attempts WHERE id=?", (attempt_id,)).fetchone()
        if not row:
            raise KeyError(attempt_id)
        data = dict(row)
        data["test"] = json.loads(data["test_json"])
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
                    # If a review failed earlier today and the user immediately passed a new paper,
                    # cancel any pending repair generated by that earlier failed attempt.
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
            "SELECT total,created_at FROM score_records WHERE node_id=? ORDER BY created_at",
            (node_id,),
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

    # ---------- History / stats ----------
    def daily_history(self, days: int = 90) -> list[dict]:
        end = date.today()
        start = end - timedelta(days=days - 1)
        output = []
        for offset in range(days):
            day = start + timedelta(days=offset)
            ds = day.isoformat()
            focus = self.focus_seconds(day, day, include_active=True)
            task_row = self.db.conn.execute(
                "SELECT COUNT(*) total, COALESCE(SUM(completed),0) done FROM task_progress WHERE day=?",
                (ds,),
            ).fetchone()
            total_tasks = int(task_row["total"])
            done_tasks = int(task_row["done"])
            completion = round(done_tasks * 100 / total_tasks) if total_tasks else None
            score_row = self.db.conn.execute(
                "SELECT AVG(total) avg_score, COUNT(*) exams, SUM(passed) passed FROM score_records WHERE score_day=?",
                (ds,),
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
