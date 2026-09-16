import unittest

from learningci.core.section_feedback import normalize_section_issues
from learningci.core.prompt_builder import build_section_grade_prompt


class SectionFeedbackTests(unittest.TestCase):
    def test_legacy_weakness_extracts_task_and_dimension(self):
        grade = {
            "weaknesses": [
                "S0-01-EL-02 的证据备注为空。任务要求写出 EventLoop 到 EPollPoller 调用链。"
            ]
        }
        issues = normalize_section_issues(grade, ["S0-01-EL-01", "S0-01-EL-02"])
        self.assertEqual(issues[0]["task_id"], "S0-01-EL-02")
        self.assertEqual(issues[0]["dimension"], "源码证据")
        self.assertIn("证据备注为空", issues[0]["title"])

    def test_structured_issue_is_preserved(self):
        grade = {
            "issues": [
                {
                    "task_id": "S0-01-EL-03",
                    "dimension": "理解准确度",
                    "title": "epoll_event.data 理解不准确",
                    "detail": "data 是联合体，不能描述成同时独立返回 fd 和 void*。",
                    "severity": "error",
                }
            ]
        }
        issues = normalize_section_issues(grade, ["S0-01-EL-03"])
        self.assertEqual(issues[0]["task_id"], "S0-01-EL-03")
        self.assertEqual(issues[0]["dimension"], "理解准确度")
        self.assertEqual(issues[0]["severity"], "error")

    def test_unknown_task_is_not_linked(self):
        grade = {
            "issues": [
                {
                    "task_id": "OTHER-01",
                    "dimension": "源码证据",
                    "title": "缺少证据",
                    "detail": "没有绑定真实函数位置。",
                }
            ]
        }
        issues = normalize_section_issues(grade, ["S0-01-EL-01"])
        self.assertEqual(issues[0]["task_id"], "")

    def test_no_issues_returns_empty(self):
        self.assertEqual(normalize_section_issues({"weaknesses": []}, ["A"]), [])

    def test_section_prompt_requests_structured_issues(self):
        node = {
            "node_code": "NRPC-S0-01",
            "title": "测试节点",
            "capability": "测试能力",
        }
        group = {
            "id": "eventloop",
            "title": "EventLoop",
            "description": "",
            "items": [],
        }
        prompt = build_section_grade_prompt(node, group)
        self.assertIn('"issues"', prompt)
        self.assertIn('"task_id"', prompt)
        self.assertIn('"dimension"', prompt)
        self.assertIn('"detail"', prompt)


if __name__ == "__main__":
    unittest.main()
