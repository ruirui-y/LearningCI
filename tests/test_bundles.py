import json
import tempfile
import unittest
from pathlib import Path

from learningci.core.bundle_loader import ensure_bundles_imported, load_bundle_file
from learningci.core.plan_loader import ensure_plan_imported
from learningci.core.service import LearningService
from learningci.database import Database

ROOT = Path(__file__).resolve().parent.parent


class BundleTests(unittest.TestCase):
    def test_all_nodes_have_valid_bundles(self):
        plan = json.loads((ROOT / "plans" / "nebularpc" / "plan.json").read_text(encoding="utf-8"))
        bundle_dir = ROOT / "plans" / "nebularpc" / "节点执行包"
        for node in plan["nodes"]:
            bundle, _ = load_bundle_file(bundle_dir / f"{node['id']}.json")
            self.assertEqual(bundle["node_id"], node["id"])
            self.assertEqual(sum(q["max_score"] for q in bundle["verification_paper"]["questions"]), 100)

    def test_s001_is_detailed(self):
        bundle, _ = load_bundle_file(ROOT / "plans" / "nebularpc" / "节点执行包" / "NRPC-S0-01.json")
        self.assertEqual(bundle["compiler"]["status"], "REVIEWED")
        self.assertGreaterEqual(bundle["task_count"], 35)
        self.assertTrue(bundle["verification_paper"]["visible_from_start"])

    def test_bundle_change_is_rejected_after_import(self):
        with tempfile.TemporaryDirectory() as td:
            td = Path(td)
            db = Database(td / "test.db")
            db.initialize()
            ensure_plan_imported(db, ROOT / "plans" / "nebularpc" / "plan.json")
            source_dir = ROOT / "plans" / "nebularpc" / "节点执行包"
            local_dir = td / "节点执行包"
            local_dir.mkdir()
            for src in source_dir.glob("NRPC-*.json"):
                (local_dir / src.name).write_bytes(src.read_bytes())
            ensure_bundles_imported(db, local_dir)
            # S0-01 is REVIEWED; reaching the front of the mainline freezes it.
            LearningService(db).get_active_node()
            target = local_dir / "NRPC-S0-01.json"
            data = json.loads(target.read_text(encoding="utf-8"))
            data["task_groups"][0]["title"] += " tampered"
            target.write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")
            with self.assertRaises(RuntimeError):
                ensure_bundles_imported(db, local_dir)
            db.close()


if __name__ == "__main__":
    unittest.main()
