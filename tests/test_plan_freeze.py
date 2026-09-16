import json
import tempfile
import unittest
from pathlib import Path

from learningci.core.plan_loader import ensure_plan_imported
from learningci.database import Database


class PlanFreezeTests(unittest.TestCase):
    def test_changed_plan_is_rejected(self):
        with tempfile.TemporaryDirectory() as td:
            td = Path(td)
            db = Database(td / "test.db")
            db.initialize()
            source = Path(__file__).resolve().parent.parent / "plans" / "nebularpc" / "plan.json"
            plan = json.loads(source.read_text(encoding="utf-8"))
            p = td / "plan.json"
            p.write_text(json.dumps(plan, ensure_ascii=False), encoding="utf-8")
            ensure_plan_imported(db, p)
            plan["plan"]["version"] = "tampered"
            p.write_text(json.dumps(plan, ensure_ascii=False), encoding="utf-8")
            with self.assertRaises(RuntimeError):
                ensure_plan_imported(db, p)
            db.close()


if __name__ == "__main__":
    unittest.main()
