import unittest

from learningci.core.refinement_bridge import build_refinement_ai_prompt, _request_text


class RefinementFileDeliveryPromptTest(unittest.TestCase):
    def setUp(self):
        self.node = {
            "node_code": "NRPC-S1-01",
            "title": "EventLoop 可读事件完整路径",
            "stage": 1,
            "priority": "CORE",
            "target_score": 80,
            "capability": "capability",
        }
        self.bundle = {
            "compiler": {"status": "GENERATED"},
            "task_count": 1,
            "task_groups": [{"id": "g1", "title": "group", "items": [{"id": "t1"}]}],
            "verification_paper": {"paper_id": "NRPC-S1-01-V1", "version": 1},
        }

    def test_clipboard_prompt_requires_downloadable_json_file(self):
        prompt = build_refinement_ai_prompt(self.node, self.bundle)
        self.assertIn("NRPC-S1-01-refined.json", prompt)
        self.assertIn("可下载的 JSON 文件", prompt)
        self.assertIn("正文只返回该 JSON 文件的下载链接", prompt)
        self.assertNotIn("只返回 **一个合法 JSON 对象**", prompt)

    def test_zip_instruction_requires_file_delivery(self):
        text = _request_text(self.node, self.bundle)
        self.assertIn("NRPC-S1-01-refined.json", text)
        self.assertIn("聊天正文不要粘贴 JSON", text)
        self.assertIn("只返回文件下载链接", text)


if __name__ == "__main__":
    unittest.main()
