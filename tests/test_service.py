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
        self.assertEqual(node["node_code"], "NRPC-S0-01")

    def test_leaf_tasks_are_initialized(self):
        node = self.service.get_active_node()
        tree = self.service.get_leaf_task_tree(node["id"])
        tasks = [item for group in tree for item in group["items"]]
        self.assertEqual(len(tasks), 30)
        done, total, pct = self.service.task_completion(node["id"])
        self.assertEqual((done, total, pct), (0, 30, 0))

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
        self.assertEqual(total, 30)
        self.assertGreater(pct, 0)


    def test_section_exam_context_uses_master_plan_and_node_boundaries(self):
        node = self.service.get_active_node()
        context = self.service.get_section_exam_context(node["id"])
        self.assertEqual(context["current_node"]["node_id"], "NRPC-S0-01")
        self.assertIn("重新实现 Reactor", context["current_node"]["out_of_scope"])
        refs = {item["ref"] for item in context["master_plan_excerpts"]}
        self.assertIn("4.1", refs)
        self.assertIn("5.1", refs)
        self.assertIn("5.2", refs)
        self.assertIn("5.3", refs)
        text = "\n".join(item["text"] for item in context["master_plan_excerpts"])
        self.assertIn("MyMuduo 已经证明的能力", text)
        self.assertIn("不复制整个 MyMuduo", text)
        self.assertIn("Recovery Zone", text)
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

    def test_s0_01_verification_no_longer_requires_manual_audit_document(self):
        node = self.service.get_active_node()
        paper = self.service.get_frozen_verification_paper(node["id"])
        impl = next(q for q in paper["questions"] if q["dimension"] == "implementation")
        self.assertIn("不额外撰写审计总结文档", impl["question"])
        self.assertNotIn("完成 NebulaRPC/docs/history/MYMUDUO_AUDIT.md", impl["question"])

    def test_fixed_verification_paper_is_reused_after_fail(self):
        node = self.service.get_active_node()
        first = self.service.ensure_verification_attempt(node["id"])
        first_attempt = self.service.get_attempt(first)
        first_paper = first_attempt["test"]
        result = self.service.grade_attempt(first, {
            "scores": {"explanation": 12, "prediction": 12, "implementation": 20, "diagnosis": 15, "transfer": 18},
            "evidence": {}, "weaknesses": ["diagnosis"],
        })
        self.assertFalse(result["passed"])
        second = self.service.ensure_verification_attempt(node["id"])
        second_attempt = self.service.get_attempt(second)
        self.assertNotEqual(first, second)
        self.assertEqual(first_paper, second_attempt["test"])

    def test_failed_grade_does_not_advance(self):
        node = self.service.get_active_node()
        attempt = self.service.ensure_verification_attempt(node["id"])
        result = self.service.grade_attempt(attempt, {
            "scores": {"explanation": 12, "prediction": 12, "implementation": 20, "diagnosis": 15, "transfer": 18},
            "evidence": {}, "weaknesses": ["diagnosis"],
        })
        self.assertFalse(result["passed"])
        node2 = self.service.get_active_node()
        self.assertEqual(node2["id"], node["id"])

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
            db.conn.execute("UPDATE nodes SET status='PASSED' WHERE priority!='OPTIONAL' AND CAST(stage AS INTEGER) < 15")
            db.conn.commit()
            node = service.get_active_node()
            self.assertEqual(node["node_code"], "NRPC-S15-01")
            db.close()


if __name__ == "__main__":
    unittest.main()
