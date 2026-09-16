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

    def test_section_prompt_includes_frozen_route_context(self):
        node = {
            "node_code": "NRPC-S0-01",
            "title": "MyMuduo 历史能力审计",
            "capability": "确认历史能力边界",
            "stage": "0",
        }
        group = {"id": "eventloop", "title": "EventLoop", "description": "", "items": []}
        route_context = {
            "plan": {"name": "NebulaRPC", "version": "test"},
            "current_node": {
                "stage": "0",
                "must_learn": ["Reactor 已有能力边界"],
                "out_of_scope": ["重新实现 Reactor"],
                "source_section": "§4.1 / §7",
            },
            "nearby_mainline": [
                {
                    "node_code": "NRPC-S0-01", "stage": "0", "title": "MyMuduo 历史能力审计",
                    "capability": "确认历史能力边界",
                }
            ],
            "master_plan_excerpts": [
                {"ref": "4.1", "title": "4.1 MyMuduo 已经证明的能力", "text": "NebulaRPC 不再把手写完整 muduo 当成主要学习目标。"}
            ],
        }
        prompt = build_section_grade_prompt(node, group, route_context)
        self.assertIn("冻结路线上下文", prompt)
        self.assertIn("重新实现 Reactor", prompt)
        self.assertIn("MyMuduo 已经证明的能力", prompt)
        self.assertIn("不得因为学习者没有主动规划", prompt)
        self.assertIn("边界判断由考官结合冻结路线上下文完成", prompt)


if __name__ == "__main__":
    unittest.main()
