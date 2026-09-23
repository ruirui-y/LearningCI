import json
import tempfile
import unittest
import zipfile
from pathlib import Path

from learningci.core.refinement_bridge import (
    build_refinement_ai_prompt,
    export_refinement_package,
)


def _paper():
    dims = [
        ("explanation", 15),
        ("prediction", 15),
        ("implementation", 25),
        ("diagnosis", 25),
        ("transfer", 20),
    ]
    return {
        "paper_id": "NRPC-TEST-V1.2",
        "version": 2,
        "questions": [
            {"id": f"q{i}", "dimension": dim, "max_score": score, "question": f"{dim}?"}
            for i, (dim, score) in enumerate(dims, 1)
        ],
    }


def _item(code):
    return {
        "id": code,
        "title": code,
        "detail": "detail",
        "purpose": "purpose",
        "estimated_minutes": 10,
        "required": True,
        "evidence_required": True,
        "evidence_fields": ["source_path", "function_name", "evidence_note"],
        "done_when": ["done"],
    }


def _bundle():
    groups = []
    count = 0
    for group_id in ["g1", "g2", "g3", "must", "gate"]:
        items = []
        for index in range(4):
            count += 1
            items.append(_item(f"{group_id}-{index + 1}"))
        groups.append({"id": group_id, "title": group_id, "items": items})
    return {
        "schema_version": 1,
        "node_id": "NRPC-TEST",
        "node_title": "测试节点",
        "compiler": {"status": "GENERATED"},
        "task_groups": groups,
        "task_count": count,
        "verification_paper": _paper(),
    }


def _node():
    return {
        "node_code": "NRPC-TEST",
        "title": "测试节点",
        "stage": 0,
        "priority": "MAIN",
        "target_score": 80,
        "capability": "测试能力",
        "order_index": 1,
        "tasks": [],
        "must_learn": ["A", "B"],
        "out_of_scope": ["C"],
        "scoring": {},
        "project_anchor": [],
    }


class RefinementExportProtocolTests(unittest.TestCase):
    def test_clipboard_prompt_contains_machine_contract(self):
        prompt = build_refinement_ai_prompt(_node(), _bundle())
        self.assertIn("task_groups[].items[]", prompt)
        self.assertIn("禁止合并、删除或改名", prompt)
        self.assertIn("5~12", prompt)
        self.assertIn("NRPC-TEST-V1.2", prompt)
        self.assertIn("version=2", prompt)
        self.assertIn("必须且只能包含一个合法 JSON 对象", prompt)

    def test_export_zip_contains_same_clipboard_prompt_and_self_check(self):
        node = _node()
        bundle = _bundle()
        expected_prompt = build_refinement_ai_prompt(node, bundle)
        previous_context = {"previous_nodes": []}
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            schema = root / "schema.json"
            schema.write_text(json.dumps({"type": "object"}, ensure_ascii=False), encoding="utf-8")
            output = root / "package.zip"
            export_refinement_package(node, bundle, previous_context, schema, output)
            with zipfile.ZipFile(output, "r") as zf:
                names = set(zf.namelist())
                self.assertIn("00-复制给AI的提示词.txt", names)
                self.assertIn("01-节点细化要求.md", names)
                self.assertIn("04-返回文件结构约束.json", names)
                self.assertIn("09-生成前自检清单.md", names)
                prompt = zf.read("00-复制给AI的提示词.txt").decode("utf-8")
                self.assertEqual(prompt, expected_prompt)
                checklist = zf.read("09-生成前自检清单.md").decode("utf-8")
                self.assertIn("verification_paper", checklist)
                self.assertIn("task_count", checklist)


if __name__ == "__main__":
    unittest.main()
