from __future__ import annotations

import json
import hashlib
import re
from collections import defaultdict
from datetime import date, datetime, timedelta
from pathlib import Path
from typing import Any

from learningci.config import (
    DEFAULT_BUNDLE_DIR, MASTER_PLAN_PATH, REPO_ROOT, SYNC_DB_PATH,
)
from learningci.core.scoring import DEFAULT_MINIMUMS, ROUTE_PASS_SCORE, evaluate_scores
from learningci.core.bundle_loader import ensure_bundles_imported, normalize_bundle_for_learning, validate_bundle
from learningci.core.refinement_bridge import (
    analyze_refinement_structure, backup_bundle_file, build_refinement_ai_prompt,
    export_refinement_package as build_refinement_zip, install_reviewed_bundle,
    stage_candidate_file,
)
from learningci.database import Database


def now_iso() -> str:
    return datetime.now().isoformat(timespec="seconds")


def today_iso() -> str:
    return date.today().isoformat()


def row_to_dict(row) -> dict | None:
    return dict(row) if row is not None else None


# v0.3.2: 早期 S0-01 执行包中存在“再写一遍审计结论/收束文档”的重复任务。
# 用户已经在更细的叶子任务中逐项回答并留证据，因此这些历史任务不再要求手工执行。
# 这里是一次明确的方法论迁移，不改变 plan.json 主路线，也不改已经记录的学习证据。
LEGACY_REDUNDANT_TASKS: dict[str, set[str]] = {
    "NRPC-S0-01": {
        "S0-01-EL-07", "S0-01-TC-11", "S0-01-CO-06", "S0-01-CL-05", "S0-01-BF-06",
        "S0-01-AU-01", "S0-01-AU-02", "S0-01-AU-03", "S0-01-AU-04", "S0-01-AU-05", "S0-01-AU-06",
    }
}

SECTION_SCORE_MAX = {
    "understanding": 35,
    "evidence": 30,
    "boundary": 25,
    "completeness": 10,
}
SECTION_PASS_SCORE = 80

# 小节验收时，考官需要看到被冻结的架构路线，但学习者不需要在 10 分钟叶子任务里
# 自己推断“未来该复用还是重做”。这些章节只作为边界判断的全局锚点；当前节点
# 自己的 source_section 会另外自动加入。
SECTION_EXAM_GLOBAL_ROUTE_REFS = ("5.1", "5.2", "5.3", "6")

# v0.3.9: 历史审计节点正式验收去重继续保留；正式测试 FAIL 后新增结构化修正反馈。
# 学习者只证明“源码里有什么、怎么工作、证据在哪里”；是否复用/恢复/重做由 Reviewer
# 结合冻结 Master Plan 判断。旧试卷中把未来架构决策塞回学习者答案的题目在运行时被新版本取代，
# 不改 plan.json，也不直接改已经冻结的执行包文件。
HISTORY_AUDIT_NODE_CODES = {"NRPC-S0-01", "NRPC-S0-02"}


def _history_audit_paper_override(node_code: str) -> dict | None:
    if node_code == "NRPC-S0-01":
        return {
            "paper_id": "NRPC-S0-01-V1.3",
            "version": 4,
            "visible_from_start": True,
            "frozen": True,
            "supersedes": ["NRPC-S0-01-V1", "NRPC-S0-01-V1.1", "NRPC-S0-01-V1.2"],
            "revision_reason": (
                "历史审计正式验收去重：叶子阶段负责采集源码证据，正式测试只考脱离材料后的机制解释、预测、"
                "诊断和迁移；implementation 由 LearningCI 自动附带既有工程证据供 Reviewer 复核。"
            ),
            "questions": [
                {
                    "id": "q1",
                    "dimension": "explanation",
                    "max_score": 15,
                    "question": (
                        "用自己的话说明四组已经审计过的对象怎样协作："
                        "① EventLoop / Poller / Channel；② Connector / TcpClient / TcpConnection；"
                        "③ Send / output_buffer / EPOLLOUT / HandleWrite；④ Channel tie/guard / TcpConnection 生命周期。"
                        "重点写对象职责、关键状态变化和因果关系。不要重新抄源码路径、行号或代码；"
                        "如果机制漏掉关键一步，Reviewer 直接针对该机制批注。"
                    ),
                },
                {
                    "id": "q2",
                    "dimension": "prediction",
                    "max_score": 15,
                    "question": (
                        "假设 TcpConnection 已建立：业务线程连续提交多个 Send，其中一次首次非阻塞 write 只写出部分数据，"
                        "且 output_buffer 尚未清空时对端关闭连接。禁止运行程序，预测跨线程发送怎样进入 owner loop、"
                        "剩余 bytes 去哪里、什么条件让发送继续、EPOLLOUT 何时停止关注，以及 close 到来后连接清理如何推进。"
                        "只写预测和原因，不要求重新抄源码路径。"
                    ),
                },
                {
                    "id": "q3",
                    "dimension": "implementation",
                    "max_score": 25,
                    "requires_answer": False,
                    "question": (
                        "系统自动复核项：LearningCI 会把本节点已经保存并通过小节验收的叶子任务工程证据自动附到评分提示词中，"
                        "Reviewer 直接检查这些路径、函数、调用链和证据备注能否支撑真实实现结论。学习者无需再次作答或重新整理证据。"
                    ),
                },
                {
                    "id": "q4",
                    "dimension": "diagnosis",
                    "max_score": 25,
                    "question": (
                        "具体故障诊断：假设有人修改 Connector 的连接完成处理逻辑，只要收到 EPOLLOUT 就直接当作连接成功并把 fd "
                        "交给 TcpClient，不再检查 SO_ERROR。此时目标端口拒绝连接。根据你已经审计过的机制说明：程序会在哪一步做出错误判断、"
                        "上层可能看到什么错误现象、根因是什么、原实现为什么能够避免这个误判。只做因果诊断，不要求重新贴源码路径或写审计报告。"
                    ),
                },
                {
                    "id": "q5",
                    "dimension": "transfer",
                    "max_score": 20,
                    "question": (
                        "假设有人对这套网络代码做以下修改：① foreign thread 直接执行 SendInLoop；"
                        "② partial write 后丢弃剩余 bytes；③ output_buffer 清空后仍持续关注 EPOLLOUT；"
                        "④ Channel 回调期间去掉 tie/guard 保活。任选三项，判断会破坏什么行为以及为什么。"
                        "不要求重新抄源码路径，只考你能否把已经掌握的机制迁移到这个变化场景。"
                    ),
                },
            ],
        }

    if node_code == "NRPC-S0-02":
        return {
            "paper_id": "NRPC-S0-02-V1.2",
            "version": 3,
            "visible_from_start": True,
            "frozen": True,
            "supersedes": ["NRPC-S0-02-V1", "NRPC-S0-02-V1.1"],
            "revision_reason": (
                "历史审计正式验收去重：旧 RPC 的源码证据只在叶子阶段采集一次，正式测试不再要求重复整理；"
                "implementation 由 LearningCI 自动附带已有证据。"
            ),
            "questions": [
                {
                    "id": "q1",
                    "dimension": "explanation",
                    "max_score": 15,
                    "question": (
                        "用自己的话解释旧 RPC 从调用发起到响应完成时，RequestId/seq_id、PendingCall、promise/future、"
                        "ReceiverThread、RpcHeader/Protobuf 分别承担什么职责，以及它们怎样串起来。"
                        "重点写机制和因果关系，不要求重新抄源码路径、行号或代码，也不要求设计新的 Async RPC。"
                    ),
                },
                {
                    "id": "q2",
                    "dimension": "prediction",
                    "max_score": 15,
                    "question": (
                        "两个 RPC 请求几乎同时发出，服务端响应顺序与请求顺序相反，其中一个调用在响应到达前发生 wait_for 超时。"
                        "禁止运行程序，预测 seq_id、PendingCall、ReceiverThread、promise/future 会怎样变化，迟到响应到来时会经过什么查找/完成逻辑。"
                        "只写预测和原因，不要求重新抄源码路径。"
                    ),
                },
                {
                    "id": "q3",
                    "dimension": "implementation",
                    "max_score": 25,
                    "requires_answer": False,
                    "question": (
                        "系统自动复核项：LearningCI 自动附带本节点已经保存并通过小节验收的旧 RPC 工程证据，Reviewer 直接检查其真实性和闭环程度。"
                        "学习者无需再次整理源码路径、函数和调用链。"
                    ),
                },
                {
                    "id": "q4",
                    "dimension": "diagnosis",
                    "max_score": 25,
                    "question": (
                        "具体故障诊断：假设某个调用已经 wait_for 超时并结束等待，随后该请求的响应才被 ReceiverThread 收到。"
                        "根据你审计过的旧实现说明迟到响应会尝试经过哪些状态/查找关系、哪里可能失效或被忽略、根因是什么，"
                        "以及当前旧实现实际如何处理。不要重新写审计报告，也不要设计新的 Async RPC。"
                    ),
                },
                {
                    "id": "q5",
                    "dimension": "transfer",
                    "max_score": 20,
                    "question": (
                        "假设对旧 RPC 做以下变化：① 两个并发请求的响应乱序返回；② 两个请求错误复用了同一个 RequestId；"
                        "③ ReceiverThread 暂停消费响应；④ PendingCall 在响应到来前被移除。任选三项，判断首先会破坏哪个状态或查找关系以及为什么。"
                        "只考当前同步 RPC 模型内的机制迁移，不进入后续阶段设计。"
                    ),
                },
            ],
        }
    return None

def _parse_source_section_refs(source_section: str) -> list[str]:
    refs: list[str] = []
    for ref in re.findall(r"§\s*(\d+(?:\.\d+)*)", str(source_section or "")):
        if ref not in refs:
            refs.append(ref)
    return refs


def _extract_markdown_numbered_section(markdown: str, ref: str) -> dict | None:
    """Extract one numbered Markdown section such as §4.1 or §7.

    The section ends at the next heading with the same or a higher hierarchy level.
    This keeps the prompt grounded in the frozen Master Plan without dumping the whole file.
    """
    lines = markdown.splitlines()
    pattern = re.compile(
        rf"^(?P<hashes>#{{1,6}})\s+{re.escape(str(ref))}(?=\s|[.：:、])(?P<title>.*)$"
    )
    start = None
    level = None
    title = ""
    for idx, line in enumerate(lines):
        match = pattern.match(line.strip())
        if match:
            start = idx
            level = len(match.group("hashes"))
            title = line.lstrip("#").strip()
            break
    if start is None or level is None:
        return None

    end = len(lines)
    heading = re.compile(r"^(?P<hashes>#{1,6})\s+")
    for idx in range(start + 1, len(lines)):
        match = heading.match(lines[idx].strip())
        if match and len(match.group("hashes")) <= level:
            end = idx
            break

    text = "\n".join(lines[start:end]).strip()
    return {"ref": str(ref), "title": title, "text": text}


class LearningService:
    def __init__(self, db: Database):
        self.db = db
        # v0.3.11: older builds used 80 + per-dimension hard gates for mainline
        # progression. Reconcile existing 70+ initial verification scores once so
        # upgrading the app immediately unlocks the next node without forcing the
        # learner to paste the same grade again.
        self._reconcile_relaxed_verification_gate()

    def _is_root_plan_node(self, node_id: int) -> bool:
        """Only root plan records are immutable; child execution bundles can be updated."""
        # Current node table stores executable child nodes; root plan protection is handled by plan layer.
        return False

    def _reconcile_relaxed_verification_gate(self) -> None:
        rows = self.db.conn.execute(
            """SELECT s.id AS score_id,s.node_id,s.attempt_id,s.total,s.created_at
               FROM score_records s
               JOIN attempts a ON a.id=s.attempt_id
               WHERE a.review_id IS NULL
                 AND a.attempt_kind='VERIFICATION'
                 AND s.passed=0
                 AND s.total>=?
               ORDER BY s.node_id,s.created_at,s.id""",
            (ROUTE_PASS_SCORE,),
        ).fetchall()
        if not rows:
            return

        touched: set[int] = set()
        now = now_iso()
        with self.db.transaction() as conn:
            for row in rows:
                node_id = int(row["node_id"])
                touched.add(node_id)
                conn.execute("UPDATE score_records SET passed=1 WHERE id=?", (int(row["score_id"]),))
                conn.execute(
                    "UPDATE attempts SET status='PASSED', graded_at=COALESCE(graded_at,?) WHERE id=?",
                    (now, int(row["attempt_id"])),
                )

            for node_id in touched:
                first = conn.execute(
                    """SELECT s.id,s.total,s.created_at
                       FROM score_records s
                       JOIN attempts a ON a.id=s.attempt_id
                       WHERE s.node_id=? AND a.review_id IS NULL
                         AND a.attempt_kind='VERIFICATION' AND s.passed=1
                       ORDER BY s.created_at,s.id LIMIT 1""",
                    (node_id,),
                ).fetchone()
                latest = conn.execute(
                    """SELECT s.id,s.total,s.created_at
                       FROM score_records s
                       JOIN attempts a ON a.id=s.attempt_id
                       WHERE s.node_id=? AND a.review_id IS NULL
                         AND a.attempt_kind='VERIFICATION' AND s.passed=1
                       ORDER BY s.created_at DESC,s.id DESC LIMIT 1""",
                    (node_id,),
                ).fetchone()
                if not first or not latest:
                    continue
                node_row = conn.execute(
                    "SELECT status,first_pass_at FROM nodes WHERE id=?", (node_id,)
                ).fetchone()
                first_pass_at = node_row["first_pass_at"] or first["created_at"]
                conn.execute(
                    "UPDATE nodes SET status='PASSED',first_pass_at=?,updated_at=? WHERE id=?",
                    (first_pass_at, now, node_id),
                )
                # If this node was trapped by the old hard gate, it never received
                # delayed reviews. Schedule them now from the qualifying score.
                pending = conn.execute(
                    "SELECT 1 FROM reviews WHERE node_id=? LIMIT 1", (node_id,)
                ).fetchone()
                if not pending:
                    self._schedule_reviews(conn, node_id, int(latest["total"]), int(latest["id"]), now)

        for node_id in touched:
            self._refresh_node_scores(node_id)

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
            "SELECT * FROM nodes WHERE status NOT IN ('PASSED','SKIPPED') AND priority != 'OPTIONAL' ORDER BY order_index LIMIT 1"
        ).fetchone()
        if not row:
            return None
        node = self._decode_node(dict(row))
        state = self.get_bundle_state(node["id"])
        # REVIEWED becomes FROZEN when it reaches the front of the mainline. FROZEN now means
        # "entered execution" only; the child execution package may still be revised from Node
        # Prepare while plan.json and the fixed verification paper remain protected.
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
        normalize_bundle_for_learning(bundle)
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
        """Mark a reviewed child package as entered execution; this does not make it immutable."""
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
               WHERE status NOT IN ('PASSED','SKIPPED') AND priority != 'OPTIONAL'
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
        bundle = self.get_node_bundle(node_id)
        schema_path = REPO_ROOT / "schemas" / "节点执行包结构.json"
        return build_refinement_zip(node, bundle, self._previous_context(node), schema_path, output_path)

    def get_refinement_ai_prompt(self, node_id: int) -> str:
        """Build the exact prompt that should accompany the exported refinement ZIP."""
        self._assert_in_preparation_window(node_id)
        node = self.get_node(node_id)
        info = self.get_bundle_info(node_id)
        bundle = self.get_node_bundle(node_id)
        return build_refinement_ai_prompt(node, bundle)

    def _validate_refined_data(self, node: dict, data: dict) -> str:
        normalize_bundle_for_learning(data)
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
        old_bundle = self.get_node_bundle(node_id)
        data, staged = stage_candidate_file(Path(source_path), node["node_code"])
        paper_id = self._validate_refined_data(node, data)
        structure = analyze_refinement_structure(old_bundle, data)
        if structure["errors"]:
            try:
                Path(staged).unlink()
            except OSError:
                pass
            raise ValueError(
                "节点细化结果破坏了任务组结构：\n\n- " + "\n- ".join(structure["errors"]) +
                "\n\n请重新生成细化结果。既有任务组是小节验收边界，只允许保留或进一步拆分。"
            )
        return {
            "node_code": node["node_code"],
            "old_tasks": structure["old_tasks"],
            "new_tasks": structure["new_tasks"],
            "old_groups": structure["old_groups"],
            "new_groups": structure["new_groups"],
            "structure_warnings": structure["warnings"],
            "recommended_task_range": structure["recommended_task_range"],
            "old_state": info["state"],
            "new_state": "FROZEN" if info["state"] == "FROZEN" else "REVIEWED",
            "next_revision": int(info["revision"] or 1) + 1,
            "added_task_ids": structure.get("added_task_ids", []),
            "removed_task_ids": structure.get("removed_task_ids", []),
            "modified_task_ids": structure.get("modified_task_ids", []),
            "staged_path": str(staged),
            "paper_id": paper_id,
        }

    def apply_refined_bundle(self, node_id: int, staged_path: Path) -> dict:
        """Replace a child execution package while preserving compatible learning evidence."""
        self._assert_in_preparation_window(node_id)
        node = self.get_node(node_id)
        info = self.get_bundle_info(node_id)
        old_bundle = self.get_node_bundle(node_id)
        data = json.loads(Path(staged_path).read_text(encoding="utf-8"))
        paper_id = self._validate_refined_data(node, data)
        structure = analyze_refinement_structure(old_bundle, data)
        if structure["errors"]:
            raise ValueError(
                "节点细化结果破坏了任务组结构：\n\n- " + "\n- ".join(structure["errors"])
            )
        backup = backup_bundle_file(node["node_code"], info["revision"])
        installed = install_reviewed_bundle(node["node_code"], data)
        ensure_bundles_imported(self.db, DEFAULT_BUNDLE_DIR)

        # Child execution packages are mutable. Preserve evidence for unchanged task ids,
        # add rows for new tasks, and only reopen tasks whose definition actually changed.
        modified_task_ids = structure.get("modified_task_ids", [])
        if modified_task_ids:
            now = now_iso()
            with self.db.transaction() as conn:
                for task_code in modified_task_ids:
                    conn.execute(
                        """UPDATE leaf_task_progress
                           SET completed=0, completed_at=NULL, updated_at=?
                           WHERE node_id=? AND task_code=?""",
                        (now, node_id, task_code),
                    )
        self.ensure_leaf_task_rows(node_id)

        # FROZEN now means "already entered execution", not "immutable child plan".
        # Keep that runtime state after an in-place revision so Today can continue immediately.
        if info["state"] == "FROZEN":
            self.db.conn.execute(
                "UPDATE node_bundles SET bundle_state='FROZEN',updated_at=? WHERE node_id=?",
                (now_iso(), node_id),
            )
            self.db.conn.commit()
        new_info = self.get_bundle_info(node_id)
        return {
            "node_code": node["node_code"],
            "old_tasks": structure["old_tasks"],
            "new_tasks": structure["new_tasks"],
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


    def skip_node(self, node_id: int, reason: str = "用户确认跳过 Recovery 节点") -> None:
        """仅允许跳过当前主线节点；SKIPPED 与 PASSED 一样参与路线推进。"""
        active = self.db.conn.execute(
            """SELECT id,node_code FROM nodes
               WHERE status NOT IN ('PASSED','SKIPPED') AND priority != 'OPTIONAL'
               ORDER BY order_index LIMIT 1"""
        ).fetchone()
        if not active:
            raise RuntimeError("当前没有可跳过的主线节点。")
        if int(active["id"]) != int(node_id):
            node = self.get_node(node_id)
            raise RuntimeError(
                f"只能跳过当前主线节点。当前节点是 {active['node_code']}，不能直接跳过 {node['node_code']}。"
            )
        with self.db.transaction() as conn:
            conn.execute(
                "UPDATE nodes SET status='SKIPPED', updated_at=? WHERE id=?",
                (now_iso(), node_id),
            )

    def list_preparation_nodes(self) -> list[dict]:
        nodes = self.list_nodes()
        active_code = None
        window_ids = self._preparation_window_ids()
        for n in nodes:
            if n["priority"] != "OPTIONAL" and n["status"] not in {"PASSED", "SKIPPED"}:
                active_code = n["node_code"]
                break
        out = []
        for node in nodes:
            info = self.get_bundle_info(node["id"])
            row = dict(node)
            row["bundle_state"] = info["state"]
            row["bundle_revision"] = info["revision"]
            try:
                effective_tree = self.get_leaf_task_tree_no_ensure_without_assessment(node["id"])
                row["task_count"] = sum(len(g.get("items", [])) for g in effective_tree)
            except Exception:
                row["task_count"] = info["task_count"]
            try:
                row["paper_id"] = self.get_frozen_verification_paper(node["id"]).get("_paper_code", info["paper_id"])
            except Exception:
                row["paper_id"] = info["paper_id"]
            row["in_prepare_window"] = node["id"] in window_ids
            if node["status"] == "PASSED":
                learning_state = "PASSED"
            elif node["status"] == "SKIPPED":
                learning_state = "SKIPPED"
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
        node = self.get_node(node_id)

        # 方法论兼容层：冻结执行包保持原样，但历史审计节点的旧正式试卷若把未来架构
        # 决策责任压给学习者，则在运行时使用已批准的新版本试卷。这样不会触碰已冻结
        # 路线/执行包，也能让已有 SQLite 在升级后立即使用正确职责边界。
        override = _history_audit_paper_override(node["node_code"])
        if override is not None:
            data = override

        data["_paper_hash"] = row["paper_hash"]
        data["_paper_code"] = data.get("paper_id", row["paper_code"])
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
        node = self.get_node(node_id)
        hidden = LEGACY_REDUNDANT_TASKS.get(node["node_code"], set())
        output: list[dict] = []
        for group_index, group in enumerate(bundle.get("task_groups", [])):
            for item_index, item in enumerate(group.get("items", [])):
                task = dict(item)
                task["group_id"] = group.get("id")
                task["group_title"] = group.get("title", "")
                task["group_description"] = group.get("description", "")
                task["group_index"] = group_index
                task["item_index"] = item_index
                task["policy_hidden"] = task.get("id") in hidden
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
        node = self.get_node(node_id)
        hidden = LEGACY_REDUNDANT_TASKS.get(node["node_code"], set())
        rows = self.db.conn.execute(
            "SELECT * FROM leaf_task_progress WHERE node_id=?", (node_id,)
        ).fetchall()
        state = {r["task_code"]: dict(r) for r in rows}
        active = self.active_task_session()
        tree: list[dict] = []
        for group in bundle.get("task_groups", []):
            visible_items = [item for item in group.get("items", []) if item.get("id") not in hidden]
            if not visible_items:
                continue
            g = {
                "id": group.get("id"),
                "title": group.get("title", ""),
                "description": group.get("description", ""),
                "assessment_required": bool(group.get("assessment_required", True)),
                "items": [],
            }
            for item in visible_items:
                t = dict(item)
                srow = state.get(item["id"], {})
                t.update({
                    "completed": bool(srow.get("completed", 0)),
                    "completed_at": srow.get("completed_at"),
                    "source_path": srow.get("source_path", ""),
                    "function_name": srow.get("function_name", ""),
                    "evidence_note": srow.get("evidence_note", ""),
                    "total_seconds": int(srow.get("total_seconds", 0) or 0),
                    "first_started_at": srow.get("first_started_at"),
                    "in_progress": bool(active and active["node_id"] == node_id and active["task_code"] == item["id"]),
                })
                g["items"].append(t)
            g["assessment"] = self.get_section_assessment(node_id, str(g["id"]), tree_override=g)
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
        node = self.get_node(node_id)
        hidden = LEGACY_REDUNDANT_TASKS.get(node["node_code"], set())
        rows = self.db.conn.execute("SELECT * FROM leaf_task_progress WHERE node_id=?", (node_id,)).fetchall()
        state = {r["task_code"]: dict(r) for r in rows}
        tree = []
        for group in bundle.get("task_groups", []):
            visible_items = [item for item in group.get("items", []) if item.get("id") not in hidden]
            if not visible_items:
                continue
            g = {
                "id": group.get("id"),
                "title": group.get("title", ""),
                "description": group.get("description", ""),
                "assessment_required": bool(group.get("assessment_required", True)),
                "items": [],
            }
            for item in visible_items:
                t = dict(item)
                srow = state.get(item["id"], {})
                t.update({
                    "completed": bool(srow.get("completed", 0)),
                    "completed_at": srow.get("completed_at"),
                    "source_path": srow.get("source_path", ""),
                    "function_name": srow.get("function_name", ""),
                    "evidence_note": srow.get("evidence_note", ""),
                    "total_seconds": int(srow.get("total_seconds", 0) or 0),
                })
                g["items"].append(t)
            g["assessment"] = self.get_section_assessment(node_id, str(g["id"]), tree_override=g)
            tree.append(g)
        return tree

    # ---------- Section mastery checks ----------
    @staticmethod
    def _section_evidence_hash(group: dict) -> str:
        payload = {
            "group_id": group.get("id"),
            "items": [
                {
                    "id": item.get("id"),
                    "completed": bool(item.get("completed")),
                    "source_path": str(item.get("source_path", "") or "").strip(),
                    "function_name": str(item.get("function_name", "") or "").strip(),
                    "evidence_note": str(item.get("evidence_note", "") or "").strip(),
                }
                for item in group.get("items", [])
            ],
        }
        raw = json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")
        return hashlib.sha256(raw).hexdigest()

    def get_section_group(self, node_id: int, group_id: str) -> dict:
        for group in self.get_leaf_task_tree_no_ensure_without_assessment(node_id):
            if str(group.get("id")) == str(group_id):
                return group
        raise KeyError(group_id)

    def get_section_exam_context(self, node_id: int) -> dict:
        """Return frozen route context for an AI section examiner.

        The learner only supplies current leaf-task facts/evidence. Reuse/rebuild decisions are
        made by the examiner from this frozen context, so the learner is not forced to plan future
        NebulaRPC stages while working on a short task.
        """
        node = self.get_node(node_id)
        bundle = self.get_node_bundle(node_id)
        source_section = str(bundle.get("source_section", "") or "")

        plan_row = self.db.conn.execute(
            "SELECT name,version FROM plans WHERE id=?", (node["plan_id"],)
        ).fetchone()
        plan_info = dict(plan_row) if plan_row else {}

        refs = _parse_source_section_refs(source_section)
        for ref in SECTION_EXAM_GLOBAL_ROUTE_REFS:
            if ref not in refs:
                refs.append(ref)

        excerpts: list[dict] = []
        if MASTER_PLAN_PATH.exists():
            master_plan = MASTER_PLAN_PATH.read_text(encoding="utf-8")
            for ref in refs:
                section = _extract_markdown_numbered_section(master_plan, ref)
                if section:
                    excerpts.append(section)

        nearby_rows = self.db.conn.execute(
            """SELECT node_code,stage,order_index,title,capability,priority,status
               FROM nodes
               WHERE plan_id=? AND order_index BETWEEN ? AND ?
               ORDER BY order_index""",
            (node["plan_id"], max(1, int(node["order_index"]) - 1), int(node["order_index"]) + 3),
        ).fetchall()
        nearby = [dict(row) for row in nearby_rows]

        return {
            "plan": {
                "name": plan_info.get("name", "NebulaRPC"),
                "version": plan_info.get("version", ""),
                "master_plan": str(MASTER_PLAN_PATH),
            },
            "current_node": {
                "node_id": node["node_code"],
                "stage": node["stage"],
                "title": node["title"],
                "capability": node["capability"],
                "must_learn": node.get("must_learn", []),
                "out_of_scope": node.get("out_of_scope", []),
                "source_section": source_section,
            },
            "nearby_mainline": nearby,
            "master_plan_excerpts": excerpts,
            "boundary_policy": (
                "学习者只负责证明当前叶子任务中的技术事实与工程证据。"
                "哪些能力在 NebulaRPC 中复用、最小恢复、重新验证或重做，由考官依据冻结路线判断；"
                "不得因为学习者没有主动规划未来阶段而扣边界判断分。"
            ),
        }

    def get_leaf_task_tree_no_ensure_without_assessment(self, node_id: int) -> list[dict]:
        bundle = self.get_node_bundle(node_id)
        node = self.get_node(node_id)
        hidden = LEGACY_REDUNDANT_TASKS.get(node["node_code"], set())
        rows = self.db.conn.execute("SELECT * FROM leaf_task_progress WHERE node_id=?", (node_id,)).fetchall()
        state = {r["task_code"]: dict(r) for r in rows}
        tree: list[dict] = []
        for group in bundle.get("task_groups", []):
            visible_items = [item for item in group.get("items", []) if item.get("id") not in hidden]
            if not visible_items:
                continue
            g = {
                "id": group.get("id"),
                "title": group.get("title", ""),
                "description": group.get("description", ""),
                "assessment_required": bool(group.get("assessment_required", True)),
                "items": [],
            }
            for item in visible_items:
                t = dict(item)
                srow = state.get(item["id"], {})
                t.update({
                    "completed": bool(srow.get("completed", 0)),
                    "completed_at": srow.get("completed_at"),
                    "source_path": srow.get("source_path", ""),
                    "function_name": srow.get("function_name", ""),
                    "evidence_note": srow.get("evidence_note", ""),
                    "total_seconds": int(srow.get("total_seconds", 0) or 0),
                })
                g["items"].append(t)
            tree.append(g)
        return tree

    def get_section_assessment(self, node_id: int, group_id: str, tree_override: dict | None = None) -> dict | None:
        row = self.db.conn.execute(
            "SELECT * FROM section_assessments WHERE node_id=? AND group_id=? ORDER BY attempt_no DESC LIMIT 1",
            (node_id, group_id),
        ).fetchone()
        if not row:
            return None
        result = dict(row)
        group = tree_override or next(
            (g for g in self.get_leaf_task_tree_no_ensure_without_assessment(node_id) if str(g.get("id")) == str(group_id)),
            None,
        )
        current_hash = self._section_evidence_hash(group) if group else ""
        result["stale"] = bool(current_hash and current_hash != result.get("evidence_hash"))
        result["passed"] = bool(result.get("passed")) and not result["stale"]
        result["grade"] = json.loads(result.get("grade_json") or "{}")
        return result

    def save_section_assessment(self, node_id: int, group_id: str, grade: dict) -> dict:
        group = self.get_section_group(node_id, group_id)
        required = [item for item in group.get("items", []) if item.get("required", True)]
        incomplete = [item.get("title", item.get("id")) for item in required if not item.get("completed")]
        if incomplete:
            raise ValueError("这个小节还有未完成叶子任务，不能进行小节验收：" + "、".join(map(str, incomplete[:5])))

        raw_scores = grade.get("scores", {})
        aliases = {
            "understanding": ["understanding", "理解准确度"],
            "evidence": ["evidence", "源码证据"],
            "boundary": ["boundary", "边界判断"],
            "completeness": ["completeness", "覆盖完整度"],
        }
        scores: dict[str, int] = {}
        for key, names in aliases.items():
            value = None
            for name in names:
                if name in raw_scores:
                    value = raw_scores[name]
                    break
            if value is None:
                raise ValueError(f"小节评分缺少：{names[-1]}")
            ivalue = int(value)
            if ivalue < 0 or ivalue > SECTION_SCORE_MAX[key]:
                raise ValueError(f"{names[-1]} 必须在 0~{SECTION_SCORE_MAX[key]} 之间")
            scores[key] = ivalue
        total = sum(scores.values())
        passed = total >= SECTION_PASS_SCORE
        expected_node = str(grade.get("node_id", "")).strip()
        expected_group = str(grade.get("section_id", grade.get("group_id", ""))).strip()
        node = self.get_node(node_id)
        if expected_node and expected_node != node["node_code"]:
            raise ValueError("小节评分 node_id 与当前节点不一致")
        if expected_group and expected_group != str(group_id):
            raise ValueError("小节评分 section_id 与当前小节不一致")
        attempt = self.db.conn.execute(
            "SELECT COALESCE(MAX(attempt_no),0)+1 n FROM section_assessments WHERE node_id=? AND group_id=?",
            (node_id, group_id),
        ).fetchone()["n"]
        evidence_hash = self._section_evidence_hash(group)
        now = now_iso()
        self.db.conn.execute(
            """INSERT INTO section_assessments(
                node_id,group_id,attempt_no,understanding,evidence,boundary,completeness,total,passed,evidence_hash,grade_json,created_at
            ) VALUES(?,?,?,?,?,?,?,?,?,?,?,?)""",
            (
                node_id, group_id, int(attempt), scores["understanding"], scores["evidence"], scores["boundary"],
                scores["completeness"], total, 1 if passed else 0, evidence_hash,
                json.dumps(grade, ensure_ascii=False), now,
            ),
        )
        self.db.conn.commit()
        return {"total": total, "passed": passed, "attempt_no": int(attempt), "stale": False}

    def section_completion(self, node_id: int) -> tuple[int, int]:
        groups = [g for g in self.get_leaf_task_tree(node_id) if g.get("assessment_required", True)]
        total = len(groups)
        passed = 0
        for group in groups:
            a = group.get("assessment")
            if a and bool(a.get("passed")) and not bool(a.get("stale")):
                passed += 1
        return passed, total

    def all_sections_passed(self, node_id: int) -> bool:
        passed, total = self.section_completion(node_id)
        return total == 0 or passed == total

    def get_verification_evidence_context(self, node_id: int) -> dict:
        """Return already-saved engineering evidence for formal history-audit grading.

        Leaf tasks are the evidence-collection phase. Formal Verification must not force the
        learner to re-copy paths/functions/call chains. The Reviewer receives this context
        automatically and uses it mainly for the implementation dimension and for checking
        mechanism answers against previously verified source evidence.
        """
        node = self.get_node(node_id)
        groups: list[dict] = []
        for group in self.get_leaf_task_tree(node_id):
            items: list[dict] = []
            for item in group.get("items", []):
                if not item.get("completed"):
                    continue
                source_path = str(item.get("source_path", "") or "").strip()
                function_name = str(item.get("function_name", "") or "").strip()
                evidence_note = str(item.get("evidence_note", "") or "").strip()
                if not (source_path or function_name or evidence_note):
                    continue
                items.append({
                    "task_id": item.get("id"),
                    "title": item.get("title", ""),
                    "source_path": source_path,
                    "function_name": function_name,
                    "evidence_note": evidence_note,
                })

            if not items:
                continue

            assessment = group.get("assessment") or {}
            grade = assessment.get("grade") or {}
            groups.append({
                "section_id": group.get("id"),
                "section_title": group.get("title", ""),
                "section_assessment": {
                    "passed": bool(assessment.get("passed")),
                    "stale": bool(assessment.get("stale")),
                    "total": assessment.get("total"),
                    "scores": grade.get("scores", {}),
                },
                "leaf_evidence": items,
            })

        return {
            "node_id": node["node_code"],
            "source": "LearningCI 已保存叶子任务证据与小节验收结果",
            "policy": (
                "这些证据由系统自动附带。学习者不需要在正式测试中重新抄写。"
                "implementation 直接依据这些工程证据评分；其他维度可用这些证据核对技术回答，但不得因未重复写路径而扣分。"
            ),
            "groups": groups,
        }

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
        # 先解析当前生效试卷。方法论修订可能在不改冻结 bundle 的前提下 supersede 旧试卷。
        paper = self.get_frozen_verification_paper(node_id)
        clean = {k: v for k, v in paper.items() if not k.startswith("_")}

        row = self.db.conn.execute(
            """SELECT id,status,test_json FROM attempts
               WHERE node_id=? AND review_id IS NULL AND attempt_kind='VERIFICATION'
               ORDER BY id DESC LIMIT 1""",
            (node_id,),
        ).fetchone()
        if row and row["status"] == "OPEN":
            try:
                open_test = json.loads(row["test_json"])
            except json.JSONDecodeError:
                open_test = None
            if open_test == clean:
                return int(row["id"])

            # 旧试卷尚未评分时只作废草稿，不生成 FAIL/score_record。历史回答仍保留在 SQLite
            # 里供追溯，但不会继续作为当前正式测试打开。
            self.db.conn.execute(
                "UPDATE attempts SET status='SUPERSEDED' WHERE id=?", (int(row["id"]),)
            )
            self.db.conn.commit()

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

    @staticmethod
    def _question_id_by_dimension(test_json: dict) -> dict[str, str]:
        out: dict[str, str] = {}
        for question in test_json.get("questions", []):
            dimension = str(question.get("dimension", "") or "")
            qid = str(question.get("id", "") or "")
            if dimension and qid:
                out[dimension] = qid
        return out

    def _normalize_verification_issues(self, grade: dict, attempt: dict, node: dict) -> list[dict]:
        """Normalize Reviewer correction items and provide a useful legacy fallback.

        v0.3.9 Reviewer prompts return structured ``issues``. Existing v0.3.8 scores only
        contain dimension evidence/weaknesses, so when reopening an already-failed attempt
        we synthesize one card per failed dimension instead of forcing the learner to guess.
        """
        raw_issues = grade.get("issues", [])
        if isinstance(raw_issues, dict):
            raw_issues = [raw_issues]
        if not isinstance(raw_issues, list):
            raw_issues = []

        q_by_dimension = self._question_id_by_dimension(attempt.get("test", {}))
        normalized: list[dict] = []
        allowed_dimensions = {"explanation", "prediction", "implementation", "diagnosis", "transfer"}
        allowed_severity = {"error", "warning", "info"}

        for raw in raw_issues:
            if not isinstance(raw, dict):
                continue
            dimension = str(raw.get("dimension", "") or "").strip()
            if dimension not in allowed_dimensions:
                continue
            question_id = str(raw.get("question_id", "") or q_by_dimension.get(dimension, "")).strip()
            task_ids = raw.get("related_task_ids", [])
            if isinstance(task_ids, str):
                task_ids = [task_ids]
            if not isinstance(task_ids, list):
                task_ids = []
            task_ids = [str(x).strip() for x in task_ids if str(x).strip()]
            severity = str(raw.get("severity", "warning") or "warning").strip().lower()
            if severity not in allowed_severity:
                severity = "warning"
            normalized.append({
                "question_id": question_id,
                "dimension": dimension,
                "title": str(raw.get("title", "需要修正") or "需要修正").strip(),
                "detail": str(raw.get("detail", "") or "").strip(),
                "correction": str(raw.get("correction", "") or "").strip(),
                "related_task_ids": task_ids,
                "severity": severity,
            })

        if normalized:
            return normalized

        # Legacy v0.3.8 fallback. Prefer the old ``weaknesses`` list when it already
        # contains Q1/Q2/... markers because those are usually one-problem-per-line and
        # therefore make a better repair panel than one large paragraph per dimension.
        scores = grade.get("scores", {}) if isinstance(grade.get("scores", {}), dict) else {}
        evidence = grade.get("evidence", {}) if isinstance(grade.get("evidence", {}), dict) else {}
        scoring = node.get("scoring", {})
        minimums = scoring.get("minimums", DEFAULT_MINIMUMS)
        dimension_by_q = {qid: dim for dim, qid in q_by_dimension.items()}

        weaknesses = grade.get("weaknesses", [])
        if isinstance(weaknesses, str):
            weaknesses = [weaknesses]
        mapped_legacy: list[dict] = []
        if isinstance(weaknesses, list):
            for index, item in enumerate(weaknesses, start=1):
                text = str(item or "").strip()
                if not text:
                    continue
                match = re.search(r"\b[qQ]([1-5])\b", text)
                qid = f"q{match.group(1)}" if match else ""
                dimension = dimension_by_q.get(qid, "")
                if not dimension:
                    for candidate in ("explanation", "prediction", "implementation", "diagnosis", "transfer"):
                        if candidate.lower() in text.lower():
                            dimension = candidate
                            qid = q_by_dimension.get(candidate, "")
                            break
                if not dimension:
                    continue
                try:
                    score = int(scores.get(dimension, 0))
                except (TypeError, ValueError):
                    score = 0
                minimum = int(minimums.get(dimension, 0))
                correction = str(evidence.get(dimension, "") or "").strip()
                if not correction:
                    correction = "按该条 Reviewer 批注修正对应技术机制；不需要重新整理已有源码材料。"
                title_text = re.sub(r"^[qQ][1-5]\s*", "", text).strip(" ：:-")
                if len(title_text) > 34:
                    title_text = title_text[:34].rstrip() + "…"
                mapped_legacy.append({
                    "question_id": qid,
                    "dimension": dimension,
                    "title": title_text or f"历史评分薄弱点 {index}",
                    "detail": text,
                    "correction": correction,
                    "related_task_ids": [],
                    "severity": "error" if score < minimum else "warning",
                })
        if mapped_legacy:
            return mapped_legacy

        # If the old weaknesses are not mappable, synthesize one card per failed
        # dimension from the detailed Reviewer evidence already stored in SQLite.
        for dimension, minimum in minimums.items():
            try:
                score = int(scores.get(dimension, 0))
            except (TypeError, ValueError):
                score = 0
            if score >= int(minimum):
                continue
            detail = str(evidence.get(dimension, "") or "").strip()
            if not detail:
                detail = f"{dimension} 当前 {score} 分，低于门槛 {minimum} 分。"
            normalized.append({
                "question_id": q_by_dimension.get(dimension, ""),
                "dimension": dimension,
                "title": f"{dimension} 未达到当前门槛",
                "detail": detail,
                "correction": "按 Reviewer 批注修正其中的错误机制；不需要重新整理已经保存的源码材料。",
                "related_task_ids": [],
                "severity": "error",
            })

        if normalized:
            return normalized

        if isinstance(weaknesses, list):
            for index, item in enumerate(weaknesses, start=1):
                text = str(item or "").strip()
                if not text:
                    continue
                normalized.append({
                    "question_id": "",
                    "dimension": "",
                    "title": f"历史评分薄弱点 {index}",
                    "detail": text,
                    "correction": "按此批注修正后重新作答同一冻结试卷。",
                    "related_task_ids": [],
                    "severity": "warning",
                })
        return normalized

    def get_attempt_feedback(self, attempt_id: int) -> dict | None:
        row = self.db.conn.execute(
            """SELECT s.*, a.test_json, a.answer_text, a.attempt_no, a.status AS attempt_status
               FROM score_records s JOIN attempts a ON a.id=s.attempt_id
               WHERE s.attempt_id=?""",
            (attempt_id,),
        ).fetchone()
        if not row:
            return None
        data = dict(row)
        try:
            test_json = json.loads(data.get("test_json") or "{}")
        except json.JSONDecodeError:
            test_json = {}
        try:
            answers = json.loads(data.get("answer_text") or "{}")
        except json.JSONDecodeError:
            answers = {}
        try:
            evidence = json.loads(data.get("evidence_json") or "{}")
        except json.JSONDecodeError:
            evidence = {}
        try:
            weaknesses = json.loads(data.get("weaknesses_json") or "[]")
        except json.JSONDecodeError:
            weaknesses = []
        try:
            issues = json.loads(data.get("issues_json") or "[]")
        except json.JSONDecodeError:
            issues = []
        return {
            "attempt_id": int(data["attempt_id"]),
            "attempt_no": int(data["attempt_no"]),
            "status": str(data.get("attempt_status") or ""),
            "passed": bool(data.get("passed")),
            "total": int(data.get("total", 0)),
            "scores": {
                "explanation": int(data.get("explanation", 0)),
                "prediction": int(data.get("prediction", 0)),
                "implementation": int(data.get("implementation", 0)),
                "diagnosis": int(data.get("diagnosis", 0)),
                "transfer": int(data.get("transfer", 0)),
            },
            "test": test_json,
            "answers": answers if isinstance(answers, dict) else {},
            "evidence": evidence if isinstance(evidence, dict) else {},
            "weaknesses": weaknesses if isinstance(weaknesses, list) else [],
            "issues": issues if isinstance(issues, list) else [],
        }

    def get_latest_failed_verification_feedback(self, node_id: int) -> dict | None:
        row = self.db.conn.execute(
            """SELECT a.id
               FROM attempts a JOIN score_records s ON s.attempt_id=a.id
               WHERE a.node_id=? AND a.review_id IS NULL AND a.attempt_kind='VERIFICATION' AND s.passed=0
               ORDER BY a.id DESC LIMIT 1""",
            (node_id,),
        ).fetchone()
        if not row:
            return None
        feedback = self.get_attempt_feedback(int(row["id"]))
        if feedback and not feedback.get("issues"):
            node = self.get_node(node_id)
            legacy_grade = {
                "scores": feedback.get("scores", {}),
                "evidence": feedback.get("evidence", {}),
                "weaknesses": feedback.get("weaknesses", []),
            }
            attempt = {"test": feedback.get("test", {})}
            feedback["issues"] = self._normalize_verification_issues(legacy_grade, attempt, node)
        return feedback

    def grade_attempt(self, attempt_id: int, grade: dict) -> dict:
        attempt = self.get_attempt(attempt_id)
        node = self.get_node(int(attempt["node_id"]))
        scores = grade.get("scores", {})
        scoring = node.get("scoring", {})
        minimums = scoring.get("minimums", DEFAULT_MINIMUMS)
        # v0.3.11: 70 points advances the route. The frozen plan's target_score
        # (normally 80) is retained as the mastery target, while old dimension
        # minimums become advisory warnings instead of hard blockers.
        mastery_score = max(ROUTE_PASS_SCORE, int(node.get("target_score") or 80))
        result = evaluate_scores(
            scores,
            pass_score=ROUTE_PASS_SCORE,
            minimums=minimums,
            mastery_score=mastery_score,
        )
        issues = self._normalize_verification_issues(grade, attempt, node)
        now = now_iso()
        day = today_iso()
        with self.db.transaction() as conn:
            conn.execute(
                """INSERT INTO score_records(
                    attempt_id,node_id,score_day,explanation,prediction,implementation,diagnosis,transfer,total,passed,
                    evidence_json,weaknesses_json,issues_json,created_at
                ) VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
                (
                    attempt_id, node["id"], day,
                    int(scores["explanation"]), int(scores["prediction"]), int(scores["implementation"]),
                    int(scores["diagnosis"]), int(scores["transfer"]), result.total, 1 if result.passed else 0,
                    json.dumps(grade.get("evidence", {}), ensure_ascii=False),
                    json.dumps(grade.get("weaknesses", []), ensure_ascii=False),
                    json.dumps(issues, ensure_ascii=False), now,
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
        return {
            "total": result.total,
            "passed": result.passed,
            "mastered": result.mastered,
            "tier": result.tier,
            "pass_score": ROUTE_PASS_SCORE,
            "mastery_score": mastery_score,
            "failures": list(result.failures),
            "warnings": list(result.warnings),
            "issues": issues,
        }

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
        from learningci.core.bundle_loader import ensure_bundles_imported, normalize_bundle_for_learning, validate_bundle
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
