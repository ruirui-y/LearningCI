import tempfile
import unittest
from pathlib import Path

from learningci.core.bundle_loader import ensure_bundles_imported
from learningci.core.plan_loader import ensure_plan_imported
from learningci.core.service import LearningService
from learningci.database import Database

ROOT = Path(__file__).resolve().parent.parent
PLAN_PATH = ROOT / "plans" / "nebularpc" / "plan.json"
BUNDLE_DIR = ROOT / "plans" / "nebularpc" / "节点执行包"


class ServiceTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.db = Database(Path(self.tmp.name) / "test.db")
        self.db.initialize()
        ensure_plan_imported(self.db, PLAN_PATH)
        ensure_bundles_imported(self.db, BUNDLE_DIR)
        self.service = LearningService(self.db)

    def tearDown(self):
        self.db.close()
        self.tmp.cleanup()

    def test_active_node_is_first_unpassed(self):
        node = self.service.get_active_node()
        self.assertEqual(node["node_code"], "NRPC-R0-01")

    def test_leaf_tasks_are_initialized(self):
        node = self.service.get_active_node()
        tree = self.service.get_leaf_task_tree(node["id"])
        tasks = [item for group in tree for item in group["items"]]
        self.assertEqual(len(tasks), 5)
        done, total, pct = self.service.task_completion(node["id"])
        self.assertEqual((done, total, pct), (0, 5, 0))

    def test_evidence_required_before_completion(self):
        node = self.service.get_active_node()
        task = self.service.get_leaf_task_tree(node["id"])[0]["items"][0]
        self.assertTrue(task["evidence_required"])
        with self.assertRaises(ValueError):
            self.service.set_leaf_task_completed(node["id"], task["id"], True)
        self.service.save_leaf_task_evidence(node["id"], task["id"], source_path="net/EventLoop.cc", function_name="EventLoop::loop")
        self.service.set_leaf_task_completed(node["id"], task["id"], True)
        done, total, pct = self.service.task_completion(node["id"])
        self.assertEqual(done, 1)
        self.assertEqual(total, 5)
        self.assertGreater(pct, 0)


    def test_section_exam_context_uses_master_plan_and_node_boundaries(self):
        node = self.service.get_active_node()
        context = self.service.get_section_exam_context(node["id"])
        self.assertEqual(context["current_node"]["node_id"], "NRPC-R0-01")
        self.assertIn("重新手写一遍 MyMuduo", context["current_node"]["out_of_scope"])
        refs = {item["ref"] for item in context["master_plan_excerpts"]}
        self.assertIn("2.1", refs)
        self.assertIn("2.2", refs)
        self.assertIn("3", refs)
        self.assertIn("4", refs)
        text = "\n".join(item["text"] for item in context["master_plan_excerpts"])
        self.assertIn("MyMuduo", text)
        self.assertIn("AI 辅助迁移", text)
        self.assertIn("Async RPC", text)
        self.assertIn("不得因为学习者没有主动规划未来阶段而扣边界判断分", context["boundary_policy"])

    def test_section_assessment_uses_leaf_evidence_and_invalidates_on_edit(self):
        node = self.service.get_active_node()
        group = self.service.get_leaf_task_tree(node["id"])[0]
        for item in group["items"]:
            self.service.save_leaf_task_evidence(
                node["id"], item["id"],
                source_path="muduo/net/EventLoop.cc",
                function_name="EventLoop::loop",
                note=f"{item['id']} evidence",
            )
            self.service.set_leaf_task_completed(node["id"], item["id"], True)
        result = self.service.save_section_assessment(node["id"], group["id"], {
            "node_id": node["node_code"],
            "section_id": group["id"],
            "scores": {"理解准确度": 31, "源码证据": 27, "边界判断": 22, "覆盖完整度": 9},
            "evidence": ["ok"],
            "weaknesses": [],
        })
        self.assertTrue(result["passed"])
        latest = self.service.get_section_assessment(node["id"], group["id"])
        self.assertTrue(latest["passed"])
        self.service.save_leaf_task_evidence(
            node["id"], group["items"][0]["id"],
            source_path="muduo/net/EventLoop.cc",
            function_name="EventLoop::loop",
            note="changed evidence",
        )
        latest = self.service.get_section_assessment(node["id"], group["id"])
        self.assertTrue(latest["stale"])
        self.assertFalse(latest["passed"])

    def test_review_verification_uses_v04_generated_paper(self):
        node = self.service.get_active_node()
        paper = self.service.get_frozen_verification_paper(node["id"])
        self.assertEqual(paper["paper_id"], "NRPC-R0-01-V1")
        self.assertEqual(paper["version"], 1)
        self.assertEqual(len(paper["questions"]), 5)

    def test_second_review_node_has_standard_verification_paper(self):
        node = self.service.get_node_by_code("NRPC-R0-02")
        paper = self.service.get_frozen_verification_paper(node["id"])
        self.assertEqual(paper["paper_id"], "NRPC-R0-02-V1")
        self.assertEqual(sum(q["max_score"] for q in paper["questions"]), 100)

    def test_verification_evidence_context_reuses_leaf_evidence(self):
        node = self.service.get_active_node()
        group = self.service.get_leaf_task_tree(node["id"])[0]
        for item in group["items"]:
            self.service.save_leaf_task_evidence(
                node["id"], item["id"],
                source_path="muduo/net/EventLoop.cc",
                function_name="EventLoop::loop",
                note=f"{item['id']} verified evidence",
            )
            self.service.set_leaf_task_completed(node["id"], item["id"], True)
        self.service.save_section_assessment(node["id"], group["id"], {
            "node_id": node["node_code"],
            "section_id": group["id"],
            "scores": {"理解准确度": 32, "源码证据": 27, "边界判断": 24, "覆盖完整度": 10},
            "evidence": ["ok"],
            "weaknesses": [],
        })
        context = self.service.get_verification_evidence_context(node["id"])
        self.assertEqual(context["node_id"], "NRPC-R0-01")
        self.assertIn("不需要在正式测试中重新抄写", context["policy"])
        self.assertEqual(len(context["groups"]), 1)
        exported = context["groups"][0]
        self.assertEqual(exported["section_id"], group["id"])
        self.assertTrue(exported["section_assessment"]["passed"])
        self.assertEqual(len(exported["leaf_evidence"]), len(group["items"]))
        self.assertEqual(exported["leaf_evidence"][0]["source_path"], "muduo/net/EventLoop.cc")

    def test_open_old_verification_draft_is_superseded_without_score(self):
        node = self.service.get_active_node()
        old_paper = {
            "paper_id": "NRPC-R0-01-OLD",
            "version": 3,
            "visible_from_start": True,
            "frozen": True,
            "questions": [
                {"id": "q1", "dimension": "explanation", "max_score": 15, "question": "old"},
                {"id": "q2", "dimension": "prediction", "max_score": 15, "question": "old"},
                {"id": "q3", "dimension": "implementation", "max_score": 25, "question": "old"},
                {"id": "q4", "dimension": "diagnosis", "max_score": 25, "question": "old"},
                {"id": "q5", "dimension": "transfer", "max_score": 20, "question": "old"},
            ],
        }
        old_id = self.service.create_attempt(node["id"], old_paper)
        self.service.save_answer(old_id, '{"q1":"draft"}')
        new_id = self.service.ensure_verification_attempt(node["id"])
        self.assertNotEqual(old_id, new_id)
        old = self.service.get_attempt(old_id)
        self.assertEqual(old["status"], "SUPERSEDED")
        self.assertEqual(old["answers"]["q1"], "draft")
        score = self.db.conn.execute("SELECT 1 FROM score_records WHERE attempt_id=?", (old_id,)).fetchone()
        self.assertIsNone(score)
        new_attempt = self.service.get_attempt(new_id)
        self.assertEqual(new_attempt["test"]["paper_id"], "NRPC-R0-01-V1")

    def test_verification_answers_persist_for_autosave_reload(self):
        node = self.service.get_active_node()
        attempt_id = self.service.ensure_verification_attempt(node["id"])
        payload = '{"q1": "draft answer", "q2": "more evidence"}'
        self.service.save_answer(attempt_id, payload)
        attempt = self.service.get_attempt(attempt_id)
        self.assertEqual(attempt["answers"]["q1"], "draft answer")
        self.assertEqual(attempt["answers"]["q2"], "more evidence")

    def test_verification_focus_uses_normal_node_focus_session(self):
        node = self.service.get_active_node()
        session = self.service.start_focus(node["id"])
        self.assertEqual(session["node_id"], node["id"])
        self.db.conn.execute(
            "UPDATE focus_sessions SET started_at=datetime('now','-5 seconds') WHERE id=?", (session["id"],)
        )
        self.db.conn.commit()
        seconds = self.service.end_focus()
        self.assertGreaterEqual(seconds, 3)
        self.assertIsNone(self.service.active_focus_session())

    def test_fixed_verification_paper_is_reused_after_fail(self):
        node = self.service.get_active_node()
        first = self.service.ensure_verification_attempt(node["id"])
        first_attempt = self.service.get_attempt(first)
        first_paper = first_attempt["test"]
        result = self.service.grade_attempt(first, {
            "scores": {"explanation": 10, "prediction": 10, "implementation": 18, "diagnosis": 15, "transfer": 14},
            "evidence": {}, "weaknesses": ["diagnosis"],
        })
        self.assertFalse(result["passed"])
        second = self.service.ensure_verification_attempt(node["id"])
        second_attempt = self.service.get_attempt(second)
        self.assertNotEqual(first, second)
        self.assertEqual(first_paper, second_attempt["test"])

    def test_failed_grade_persists_structured_repair_issues(self):
        node = self.service.get_active_node()
        attempt = self.service.ensure_verification_attempt(node["id"])
        self.service.save_answer(attempt, '{"q2":"wrong partial write model"}')
        result = self.service.grade_attempt(attempt, {
            "scores": {"explanation": 10, "prediction": 3, "implementation": 20, "diagnosis": 18, "transfer": 14},
            "evidence": {"prediction": "partial write ownership is wrong"},
            "issues": [{
                "question_id": "q2",
                "dimension": "prediction",
                "title": "剩余 bytes 所有权错误",
                "detail": "回答把剩余 bytes 当成会立即清理。",
                "correction": "partial write 后剩余 bytes 先进入 output_buffer_，等待 EPOLLOUT 后由 HandleWrite 继续发送。",
                "related_task_ids": ["S0-01-TC-04", "S0-01-TC-06"],
                "severity": "error",
            }],
            "weaknesses": ["partial write"],
        })
        self.assertFalse(result["passed"])
        self.assertEqual(result["issues"][0]["question_id"], "q2")
        feedback = self.service.get_attempt_feedback(attempt)
        self.assertIsNotNone(feedback)
        self.assertEqual(feedback["answers"]["q2"], "wrong partial write model")
        self.assertEqual(feedback["issues"][0]["related_task_ids"], ["S0-01-TC-04", "S0-01-TC-06"])
        self.assertIn("output_buffer_", feedback["issues"][0]["correction"])

    def test_legacy_failed_grade_builds_repair_cards_from_dimension_evidence(self):
        node = self.service.get_active_node()
        attempt = self.service.ensure_verification_attempt(node["id"])
        self.service.save_answer(attempt, '{"q4":"legacy wrong diagnosis"}')
        result = self.service.grade_attempt(attempt, {
            "scores": {"explanation": 10, "prediction": 10, "implementation": 20, "diagnosis": 8, "transfer": 14},
            "evidence": {"diagnosis": "SO_ERROR 被漏掉，不能把 EPOLLOUT 直接当连接成功。"},
            "weaknesses": ["Connector completion"],
        })
        self.assertFalse(result["passed"])
        feedback = self.service.get_latest_failed_verification_feedback(node["id"])
        self.assertIsNotNone(feedback)
        self.assertTrue(feedback["issues"])
        issue = feedback["issues"][0]
        self.assertEqual(issue["question_id"], "q4")
        self.assertEqual(issue["dimension"], "diagnosis")
        self.assertIn("SO_ERROR", issue["detail"])

    def test_legacy_weaknesses_with_question_ids_become_separate_repair_cards(self):
        node = self.service.get_active_node()
        attempt = self.service.ensure_verification_attempt(node["id"])
        self.service.save_answer(attempt, '{"q2":"bad send model","q5":"bad tie model"}')
        self.service.grade_attempt(attempt, {
            "scores": {"explanation": 12, "prediction": 5, "implementation": 22, "diagnosis": 20, "transfer": 8},
            "evidence": {
                "prediction": "正确模型：partial write 后剩余 bytes 进入 output_buffer_。",
                "transfer": "正确模型：tie_.lock() 得到 shared_ptr guard 保活。",
            },
            "weaknesses": [
                "Q2 把 partial write 后剩余 bytes 的归属判断错了。",
                "Q5 对 tie/guard 的判断错误。",
            ],
        })
        feedback = self.service.get_latest_failed_verification_feedback(node["id"])
        self.assertEqual(len(feedback["issues"]), 2)
        self.assertEqual(feedback["issues"][0]["question_id"], "q2")
        self.assertEqual(feedback["issues"][1]["question_id"], "q5")
        self.assertIn("output_buffer_", feedback["issues"][0]["correction"])
        self.assertIn("shared_ptr guard", feedback["issues"][1]["correction"])

    def test_score_records_schema_has_issues_json(self):
        columns = {row[1] for row in self.db.conn.execute("PRAGMA table_info(score_records)").fetchall()}
        self.assertIn("issues_json", columns)

    def test_failed_grade_does_not_advance(self):
        node = self.service.get_active_node()
        attempt = self.service.ensure_verification_attempt(node["id"])
        result = self.service.grade_attempt(attempt, {
            "scores": {"explanation": 10, "prediction": 10, "implementation": 18, "diagnosis": 15, "transfer": 14},
            "evidence": {}, "weaknesses": ["diagnosis"],
        })
        self.assertFalse(result["passed"])
        node2 = self.service.get_active_node()
        self.assertEqual(node2["id"], node["id"])

    def test_70_point_verification_advances_even_below_old_dimension_gate(self):
        node = self.service.get_active_node()
        attempt = self.service.ensure_verification_attempt(node["id"])
        result = self.service.grade_attempt(attempt, {
            "scores": {"explanation": 11, "prediction": 11, "implementation": 22, "diagnosis": 12, "transfer": 14},
            "evidence": {},
            "issues": [{
                "question_id": "q4",
                "dimension": "diagnosis",
                "title": "诊断仍有薄弱点",
                "detail": "旧维度门槛未达到。",
                "correction": "保留为复测薄弱点，不阻塞主线。",
                "related_task_ids": [],
                "severity": "warning",
            }],
            "weaknesses": ["diagnosis"],
        })
        self.assertEqual(result["total"], 70)
        self.assertTrue(result["passed"])
        self.assertFalse(result["mastered"])
        self.assertIn("diagnosis 12 < 18", result["warnings"])
        next_node = self.service.get_active_node()
        self.assertNotEqual(next_node["id"], node["id"])

    def test_upgrade_reconciles_old_70_plus_failed_verification(self):
        node = self.service.get_active_node()
        attempt = self.service.ensure_verification_attempt(node["id"])
        now = "2026-09-18T10:00:00"
        self.db.conn.execute(
            """INSERT INTO score_records(
                attempt_id,node_id,score_day,explanation,prediction,implementation,diagnosis,transfer,total,passed,
                evidence_json,weaknesses_json,issues_json,created_at
            ) VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
            (attempt, node["id"], "2026-09-18", 11, 11, 22, 17, 16, 77, 0, "{}", "[]", "[]", now),
        )
        self.db.conn.execute(
            "UPDATE attempts SET status='FAILED',graded_at=? WHERE id=?", (now, attempt)
        )
        self.db.conn.execute(
            "UPDATE nodes SET status='FAILED',updated_at=? WHERE id=?", (now, node["id"])
        )
        self.db.conn.commit()

        migrated = LearningService(self.db)
        old_attempt = migrated.get_attempt(attempt)
        self.assertEqual(old_attempt["status"], "PASSED")
        score = self.db.conn.execute(
            "SELECT passed FROM score_records WHERE attempt_id=?", (attempt,)
        ).fetchone()
        self.assertEqual(int(score["passed"]), 1)
        migrated_node = migrated.get_node(node["id"])
        self.assertEqual(migrated_node["status"], "PASSED")
        next_node = migrated.get_active_node()
        self.assertNotEqual(next_node["id"], node["id"])

    def test_pass_advances_and_schedules_review(self):
        node = self.service.get_active_node()
        attempt = self.service.ensure_verification_attempt(node["id"])
        result = self.service.grade_attempt(attempt, {
            "scores": {"explanation": 13, "prediction": 12, "implementation": 22, "diagnosis": 20, "transfer": 16},
            "evidence": {}, "weaknesses": [],
        })
        self.assertTrue(result["passed"])
        next_node = self.service.get_active_node()
        self.assertNotEqual(next_node["id"], node["id"])
        future_reviews = self.service.due_reviews(include_future=True)
        self.assertGreaterEqual(len(future_reviews), 2)

    def test_task_timer_rolls_into_task_total(self):
        node = self.service.get_active_node()
        task = self.service.get_leaf_task_tree(node["id"])[0]["items"][0]
        session = self.service.start_task_focus(node["id"], task["id"])
        self.assertIsNotNone(session)
        # Force start time one minute back to keep test deterministic/fast.
        self.db.conn.execute(
            "UPDATE task_focus_sessions SET started_at=datetime('now','-60 seconds') WHERE id=?", (session["id"],)
        )
        self.db.conn.commit()
        seconds = self.service.end_task_focus()
        self.assertGreaterEqual(seconds, 50)
        updated = self.service.get_leaf_task(node["id"], task["id"])
        self.assertGreaterEqual(int(updated["total_seconds"]), 50)
        self.service.end_focus()


class OptionalRouteTests(unittest.TestCase):
    def test_optional_nodes_do_not_block_core_mainline(self):
        with tempfile.TemporaryDirectory() as td:
            db = Database(Path(td) / "test.db")
            db.initialize()
            ensure_plan_imported(db, PLAN_PATH)
            ensure_bundles_imported(db, BUNDLE_DIR)
            service = LearningService(db)
            final_row = db.conn.execute("SELECT order_index FROM nodes WHERE node_code='NRPC-FINAL-01'").fetchone()
            db.conn.execute("UPDATE nodes SET status='PASSED' WHERE priority!='OPTIONAL' AND order_index < ?", (final_row["order_index"],))
            db.conn.commit()
            node = service.get_active_node()
            self.assertEqual(node["node_code"], "NRPC-FINAL-01")
            db.close()


if __name__ == "__main__":
    unittest.main()
