import copy
import unittest

from learningci.core.bundle_loader import normalize_bundle_task_groups, validate_bundle
from learningci.core.refinement_bridge import analyze_refinement_structure


def _paper():
    dims = [("explanation", 15), ("prediction", 15), ("implementation", 25), ("diagnosis", 25), ("transfer", 20)]
    return {
        "paper_id": "NRPC-TEST-V1",
        "version": 1,
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
        "evidence_fields": ["note"],
        "done_when": ["done"],
    }


def _bundle(group_ids, tasks_per_group=4, alias=None):
    groups = []
    count = 0
    field = alias or "items"
    for group_id in group_ids:
        items = []
        for i in range(tasks_per_group):
            count += 1
            items.append(_item(f"{group_id}-{i + 1}"))
        groups.append({"id": group_id, "title": group_id, field: items})
    return {
        "schema_version": 1,
        "node_id": "NRPC-TEST",
        "node_title": "test",
        "task_groups": groups,
        "task_count": count,
        "verification_paper": _paper(),
    }


class RefinementStructureTests(unittest.TestCase):
    def test_alias_is_normalized_to_items(self):
        data = _bundle(["a", "b"], 2, alias="leaf_tasks")
        validate_bundle(data, "NRPC-TEST")
        normalize_bundle_task_groups(data)
        self.assertIn("items", data["task_groups"][0])
        self.assertNotIn("leaf_tasks", data["task_groups"][0])
        validate_bundle(data, "NRPC-TEST")

    def test_merging_existing_groups_is_rejected(self):
        old = _bundle(["protobuf", "pending", "receiver", "server", "timeout"], 4)
        new = _bundle(["protobuf"], 25)
        result = analyze_refinement_structure(old, new)
        self.assertTrue(result["errors"])
        self.assertIn("pending", result["missing_group_ids"])

    def test_existing_groups_can_be_kept_and_refined(self):
        old = _bundle(["protobuf", "pending", "receiver", "server", "timeout"], 3)
        new = _bundle(["protobuf", "pending", "receiver", "server", "timeout"], 5)
        result = analyze_refinement_structure(old, new)
        self.assertEqual(result["errors"], [])
        self.assertEqual(result["new_tasks"], 25)
        self.assertEqual(result["warnings"], [])

    def test_group_split_is_allowed_with_warning(self):
        old = _bundle(["protobuf", "pending", "receiver", "server", "timeout"], 4)
        new = _bundle(["protobuf", "pending", "receiver", "server", "timeout", "failure_paths"], 4)
        result = analyze_refinement_structure(old, new)
        self.assertEqual(result["errors"], [])
        self.assertTrue(any("增加" in warning for warning in result["warnings"]))

    def test_task_count_outside_20_30_only_warns(self):
        old = _bundle(["a", "b", "c", "d", "e"], 4)
        new = _bundle(["a", "b", "c", "d", "e"], 7)
        result = analyze_refinement_structure(old, new)
        self.assertEqual(result["errors"], [])
        self.assertEqual(result["new_tasks"], 35)
        self.assertTrue(any("20~30" in warning for warning in result["warnings"]))

    def test_existing_verification_paper_is_immutable(self):
        old = _bundle(["a", "b", "c", "d", "e"], 4)
        new = copy.deepcopy(old)
        new["verification_paper"]["questions"][0]["question"] = "changed"
        result = analyze_refinement_structure(old, new)
        self.assertTrue(any("verification_paper" in error for error in result["errors"]))

    def test_stable_bundle_policy_is_immutable(self):
        old = _bundle(["a", "b", "c", "d", "e"], 4)
        old["task_policy"] = {"single_active_leaf_task": True}
        old["retest_policy"] = {"new_paper_required_for_retest": True}
        new = copy.deepcopy(old)
        new.pop("retest_policy")
        result = analyze_refinement_structure(old, new)
        self.assertTrue(any("retest_policy" in error for error in result["errors"]))


if __name__ == "__main__":
    unittest.main()
