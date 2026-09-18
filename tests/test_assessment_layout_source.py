from pathlib import Path
import unittest


class AssessmentLayoutSourceTests(unittest.TestCase):
    def test_assessment_uses_one_outer_scroll_page(self):
        source = (Path(__file__).parents[1] / "learningci" / "ui" / "dialogs.py").read_text(encoding="utf-8")
        self.assertIn("self.page_scroll = QScrollArea()", source)
        self.assertIn("self.page_scroll.setWidget(self.page_host)", source)
        self.assertIn("root.addWidget(self.question_host)", source)
        self.assertIn("repair_layout.addWidget(self.repair_host)", source)
        self.assertNotIn("self.question_scroll = QScrollArea()", source)
        self.assertNotIn("self.repair_scroll = QScrollArea()", source)
        self.assertNotIn("self.repair_scroll.setMaximumHeight", source)

    def test_retry_returns_page_to_top_and_feedback_can_be_revealed(self):
        source = (Path(__file__).parents[1] / "learningci" / "ui" / "dialogs.py").read_text(encoding="utf-8")
        self.assertIn("self.page_scroll.verticalScrollBar().setValue(0)", source)
        self.assertIn("self.page_scroll.ensureWidgetVisible(self.repair_panel", source)
        self.assertIn("self._render_repair_feedback(feedback, reveal=True)", source)


if __name__ == "__main__":
    unittest.main()
