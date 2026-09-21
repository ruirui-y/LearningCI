import json
import tempfile
import unittest
from pathlib import Path

from learningci.database import Database
from learningci.core.service import LearningService, now_iso


class SkipPrepareWindowRegressionTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.db = Database(Path(self.tmp.name) / "test.db")
        self.db.initialize()
        now = now_iso()
        cur = self.db.conn.execute(
            "INSERT INTO plans(plan_code,name,version,plan_hash,source_path,imported_at) VALUES(?,?,?,?,?,?)",
            ("test-plan", "test", "1", "hash", "plan.json", now),
        )
        plan_id = int(cur.lastrowid)
        specs = [
            ("NRPC-S0-01", 1, "PASSED"),
            ("NRPC-S0-02", 2, "PASSED"),
            ("NRPC-S0-03", 3, "READY"),
            ("NRPC-S0-04", 4, "READY"),
            ("NRPC-S0-05", 5, "READY"),
            ("NRPC-S1-01", 6, "READY"),
            ("NRPC-S1-02", 7, "READY"),
            ("NRPC-S1-03", 8, "READY"),
            ("NRPC-S1-04", 9, "READY"),
        ]
        self.ids = {}
        for code, order_index, status in specs:
            cur = self.db.conn.execute(
                """INSERT INTO nodes(
                    plan_id,node_code,stage,order_index,title,capability,priority,target_score,status,
                    tasks_json,must_learn_json,out_of_scope_json,scoring_json,project_anchor_json,
                    created_at,updated_at
                ) VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
                (
                    plan_id, code, code.split("-")[1][1:], order_index, code, "capability", "CORE", 80, status,
                    "[]", "[]", "[]", "{}", "[]", now, now,
                ),
            )
            node_id = int(cur.lastrowid)
            self.ids[code] = node_id
            bundle = {
                "schema_version": 1,
                "node_id": code,
                "node_title": code,
                "compiler": {"status": "GENERATED"},
                "task_groups": [],
                "task_count": 0,
                "verification_paper": {"paper_id": f"{code}-V1", "version": 1, "questions": []},
            }
            self.db.conn.execute(
                """INSERT INTO node_bundles(
                    node_id,bundle_hash,bundle_json,source_path,imported_at,bundle_state,revision,updated_at
                ) VALUES(?,?,?,?,?,?,?,?)""",
                (node_id, f"hash-{code}", json.dumps(bundle, ensure_ascii=False), f"{code}.json", now, "GENERATED", 1, now),
            )
        self.db.conn.commit()
        self.service = LearningService(self.db)

    def tearDown(self):
        self.db.close()
        self.tmp.cleanup()

    def _window_codes(self):
        ids = self.service._preparation_window_ids()
        return {
            self.service.get_node(node_id)["node_code"]
            for node_id in ids
        }

    def test_skipped_nodes_are_not_active_or_in_prepare_window(self):
        self.assertEqual(self.service.get_active_node()["node_code"], "NRPC-S0-03")

        self.service.skip_node(self.ids["NRPC-S0-03"])
        self.assertEqual(self.service.get_active_node()["node_code"], "NRPC-S0-04")

        self.service.skip_node(self.ids["NRPC-S0-04"])
        self.assertEqual(self.service.get_active_node()["node_code"], "NRPC-S0-05")

        self.service.skip_node(self.ids["NRPC-S0-05"])
        self.assertEqual(self.service.get_active_node()["node_code"], "NRPC-S1-01")
        self.assertEqual(
            self._window_codes(),
            {"NRPC-S1-01", "NRPC-S1-02", "NRPC-S1-03"},
        )

        rows = {row["node_code"]: row for row in self.service.list_preparation_nodes()}
        self.assertTrue(rows["NRPC-S1-01"]["in_prepare_window"])
        self.assertEqual(rows["NRPC-S1-01"]["learning_state"], "PREP_REQUIRED")
        self.assertFalse(rows["NRPC-S0-03"]["in_prepare_window"])
        self.assertEqual(rows["NRPC-S0-03"]["learning_state"], "SKIPPED")

    def test_cannot_skip_future_node(self):
        with self.assertRaises(RuntimeError):
            self.service.skip_node(self.ids["NRPC-S1-01"])


class NodePreparePageSourceRegressionTest(unittest.TestCase):
    def test_prepare_button_uses_window_even_after_skips(self):
        path = Path(__file__).resolve().parents[1] / "learningci" / "ui" / "node_prepare_page.py"
        text = path.read_text(encoding="utf-8")
        self.assertIn('allowed = bool(row.get("in_prepare_window"))', text)
        self.assertNotIn('and not frozen', text)
        self.assertIn('"CURRENT", "PREP_REQUIRED"', text)


if __name__ == "__main__":
    unittest.main()
