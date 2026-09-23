import json
import tempfile
import unittest
import zipfile
from pathlib import Path
from unittest.mock import patch

from learningci.core.bundle_loader import ensure_bundles_imported
from learningci.core.plan_loader import ensure_plan_imported
from learningci.core.service import LearningService
from learningci.database import Database

ROOT = Path(__file__).resolve().parent.parent
PLAN_PATH = ROOT / "plans" / "nebularpc" / "plan.json"
BUNDLE_DIR = ROOT / "plans" / "nebularpc" / "节点执行包"


class RefinementBridgeTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.tmp_path = Path(self.tmp.name)
        self.db = Database(self.tmp_path / "test.db")
        self.db.initialize()
        ensure_plan_imported(self.db, PLAN_PATH)
        ensure_bundles_imported(self.db, BUNDLE_DIR)
        self.service = LearningService(self.db)

    def tearDown(self):
        self.db.close()
        self.tmp.cleanup()

    def test_only_three_node_window_can_be_refined(self):
        rows = {x["node_code"]: x for x in self.service.list_preparation_nodes()}
        self.assertTrue(rows["NRPC-R0-01"]["in_prepare_window"])
        self.assertTrue(rows["NRPC-R0-02"]["in_prepare_window"])
        self.assertTrue(rows["NRPC-B0-01"]["in_prepare_window"])
        self.assertFalse(rows["NRPC-N1-01"]["in_prepare_window"])
        with self.assertRaises(RuntimeError):
            self.service.export_refinement_package(
                rows["NRPC-N1-01"]["id"], self.tmp_path / "far.zip"
            )

    def test_export_package_uses_chinese_file_names(self):
        node = self.service.get_node_by_code("NRPC-R0-02")
        target = self.tmp_path / "R0-02节点细化包.zip"
        result = self.service.export_refinement_package(node["id"], target)
        self.assertEqual(result, target)
        with zipfile.ZipFile(result) as zf:
            names = set(zf.namelist())
        expected = {
            "01-节点细化要求.md",
            "02-当前节点定义_禁止修改.json",
            "03-当前节点执行包.json",
            "04-返回文件结构约束.json",
            "05-NebulaRPC总计划.md",
            "06-前置节点学习结果.json",
            "07-项目背景与求职证据.md",
            "08-返回文件说明.txt",
        }
        self.assertTrue(expected.issubset(names))

    def test_chatgpt_result_is_staged_before_install(self):
        node = self.service.get_node_by_code("NRPC-R0-02")
        source = BUNDLE_DIR / "NRPC-R0-02.json"
        data = json.loads(source.read_text(encoding="utf-8"))
        data["compiler"]["status"] = "REVIEWED"
        candidate = self.tmp_path / "NRPC-R0-02_已细化.json"
        candidate.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
        staged_dir = self.tmp_path / "待审核"
        with patch("learningci.core.refinement_bridge.REFINE_PROPOSED_DIR", staged_dir):
            preview = self.service.preview_refined_bundle(node["id"], candidate)
        self.assertEqual(preview["new_state"], "REVIEWED")
        self.assertTrue(Path(preview["staged_path"]).exists())
        self.assertEqual(self.service.get_bundle_state(node["id"]), "REVIEWED")


if __name__ == "__main__":
    unittest.main()
