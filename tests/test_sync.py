import tempfile
import unittest
from pathlib import Path

from learningci.core.bundle_loader import ensure_bundles_imported
from learningci.core.plan_loader import ensure_plan_imported
from learningci.core.service import LearningService
from learningci.database import Database

ROOT = Path(__file__).resolve().parent.parent


class SyncTests(unittest.TestCase):
    def test_snapshot_roundtrip(self):
        with tempfile.TemporaryDirectory() as td:
            td = Path(td)
            db = Database(td / "local.db")
            db.initialize()
            ensure_plan_imported(db, ROOT / "plans" / "nebularpc" / "plan.json")
            ensure_bundles_imported(db, ROOT / "plans" / "nebularpc" / "节点执行包")
            service = LearningService(db)
            node = service.get_active_node()
            service.add_parking_item("before snapshot", node["id"])
            snap = td / "sync.db"
            service.create_sync_snapshot(snap)
            service.add_parking_item("local only", node["id"])
            self.assertEqual(len(service.list_parking()), 2)
            service.restore_sync_snapshot(snap)
            self.assertEqual(len(service.list_parking()), 1)
            self.assertEqual(service.list_parking()[0]["content"], "before snapshot")
            db.close()


if __name__ == "__main__":
    unittest.main()
