import unittest

from learningci.core.prompt_builder import build_grade_prompt, build_test_prompt


class PromptBuilderTests(unittest.TestCase):
    def _history_node(self):
        return {
            "node_code": "NRPC-S0-01",
            "title": "MyMuduo 历史能力审计",
            "capability": "基于真实源码说明历史能力",
            "target_score": 80,
            "tasks": [],
            "must_learn": ["Reactor"],
            "out_of_scope": ["协程"],
            "project_anchor": {},
        }

    def test_history_audit_test_prompt_avoids_duplicate_evidence_work(self):
        prompt = build_test_prompt(self._history_node())
        self.assertIn("历史审计节点专用职责边界", prompt)
        self.assertIn("正式测试不得要求学习者把这些材料再抄一遍", prompt)
        self.assertIn("requires_answer", prompt)
        self.assertIn("系统自动复核已有工程证据", prompt)
        self.assertIn("diagnosis 必须给一个具体故障", prompt)
        self.assertIn("不得要求学习者判断未来 Stage", prompt)

    def test_history_audit_grade_prompt_injects_system_evidence(self):
        test_json = {
            "paper_id": "NRPC-S0-01-V1.3",
            "questions": [
                {"id": "q3", "dimension": "implementation", "max_score": 25, "requires_answer": False, "question": "system"}
            ],
        }
        system_evidence = {
            "node_id": "NRPC-S0-01",
            "groups": [{
                "section_id": "eventloop",
                "leaf_evidence": [{
                    "task_id": "S0-01-EL-01",
                    "source_path": "src/net/EventLoop.cpp",
                    "function_name": "EventLoop::Loop",
                    "evidence_note": "poll_->Poll",
                }],
            }],
        }
        prompt = build_grade_prompt(
            self._history_node(), test_json, {"q1": "answer"}, system_evidence=system_evidence
        )
        self.assertIn("LearningCI 自动附带的既有工程证据", prompt)
        self.assertIn("src/net/EventLoop.cpp", prompt)
        self.assertIn("implementation 的 25 分只依据", prompt)
        self.assertIn("不得因未重复写源码路径而扣分", prompt)
        self.assertIn("直接指出具体机制错误", prompt)
        self.assertIn('"issues"', prompt)
        self.assertIn('"correction"', prompt)
        self.assertIn('"related_task_ids"', prompt)
        self.assertIn("正确机制是什么", prompt)


if __name__ == "__main__":
    unittest.main()
