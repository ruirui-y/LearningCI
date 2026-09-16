import tempfile
import unittest
from pathlib import Path

from learningci.core.plan_loader import ensure_plan_imported
from learningci.core.service import LearningService, today_iso
from learningci.database import Database


class ServiceTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.db = Database(Path(self.tmp.name) / "test.db")
        self.db.initialize()
        plan_path = Path(__file__).resolve().parent.parent / "plans" / "nebularpc" / "plan.json"
        ensure_plan_imported(self.db, plan_path)
        self.service = LearningService(self.db)

    def tearDown(self):
        self.db.close()
        self.tmp.cleanup()

    def test_active_node_is_first_unpassed(self):
        node = self.service.get_active_node()
        self.assertEqual(node["node_code"], "NRPC-S0-01")

    def test_daily_tasks_are_initialized(self):
        node = self.service.get_active_node()
        states = self.service.get_task_states(node["id"], today_iso())
        self.assertEqual(len(states), 3)
        self.service.set_task_completed(node["id"], 0, True)
        done, total, pct = self.service.task_completion(node["id"])
        self.assertEqual((done, total, pct), (1, 3, 33))

    def test_failed_grade_does_not_advance(self):
        node = self.service.get_active_node()
        attempt = self.service.create_attempt(node["id"], {"questions": [{"id":"q1"}]})
        result = self.service.grade_attempt(attempt, {
            "scores": {"explanation": 12, "prediction": 12, "implementation": 20, "diagnosis": 15, "transfer": 18},
            "evidence": {}, "weaknesses": ["diagnosis"],
        })
        self.assertFalse(result["passed"])
        node2 = self.service.get_active_node()
        self.assertEqual(node2["id"], node["id"])

    def test_pass_advances_and_schedules_review(self):
        node = self.service.get_active_node()
        attempt = self.service.create_attempt(node["id"], {"questions": [{"id":"q1"}]})
        result = self.service.grade_attempt(attempt, {
            "scores": {"explanation": 13, "prediction": 12, "implementation": 22, "diagnosis": 20, "transfer": 16},
            "evidence": {}, "weaknesses": [],
        })
        self.assertTrue(result["passed"])
        next_node = self.service.get_active_node()
        self.assertNotEqual(next_node["id"], node["id"])
        future_reviews = self.service.due_reviews(include_future=True)
        self.assertGreaterEqual(len(future_reviews), 2)


if __name__ == "__main__":
    unittest.main()


class OptionalRouteTests(unittest.TestCase):
    def test_optional_nodes_do_not_block_core_mainline(self):
        with tempfile.TemporaryDirectory() as td:
            db = Database(Path(td) / "test.db")
            db.initialize()
            plan_path = Path(__file__).resolve().parent.parent / "plans" / "nebularpc" / "plan.json"
            ensure_plan_imported(db, plan_path)
            service = LearningService(db)
            # Mark every CORE node before Stage 15 as passed. Stage 13/14 OPTIONAL nodes remain READY.
            db.conn.execute("UPDATE nodes SET status='PASSED' WHERE priority!='OPTIONAL' AND CAST(stage AS INTEGER) < 15")
            db.conn.commit()
            node = service.get_active_node()
            self.assertEqual(node["node_code"], "NRPC-S15-01")
            db.close()
