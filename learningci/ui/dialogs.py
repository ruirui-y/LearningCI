from __future__ import annotations

import json

from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtGui import QGuiApplication
from PyQt6.QtWidgets import (
    QDialog, QDialogButtonBox, QFrame, QHBoxLayout, QLabel, QMessageBox,
    QPushButton, QScrollArea, QTextEdit, QVBoxLayout, QWidget
)

from learningci.core.prompt_builder import build_grade_prompt, build_test_prompt


DIMENSION_ZH = {
    "explanation": "解释",
    "prediction": "预测",
    "implementation": "实现",
    "diagnosis": "诊断",
    "transfer": "迁移",
}


class JsonPasteDialog(QDialog):
    def __init__(self, title: str, parent=None):
        super().__init__(parent)
        self.setWindowTitle(title)
        self.resize(780, 560)
        layout = QVBoxLayout(self)
        tip = QLabel("粘贴 AI 返回的纯 JSON。不要包含 Markdown ``` fence。")
        tip.setObjectName("Secondary")
        layout.addWidget(tip)
        self.editor = QTextEdit()
        self.editor.setPlaceholderText('{\n  "node_id": "...",\n  "questions": [...]\n}')
        layout.addWidget(self.editor, 1)
        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel)
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

    def value(self) -> dict:
        return json.loads(self.editor.toPlainText().strip())


class AssessmentDialog(QDialog):
    graded = pyqtSignal()

    def __init__(self, service, node: dict, review: dict | None = None, parent=None):
        super().__init__(parent)
        self.service = service
        self.node = node
        self.review = review
        self.attempt_id: int | None = None
        self.test_json: dict | None = None
        self.answer_editors: dict[str, QTextEdit] = {}
        self.setWindowTitle("LearningCI - 复测" if review else "LearningCI - 正式测试")
        self.resize(1080, 880)
        self.setMinimumSize(920, 700)
        self._build_ui()
        if self.review:
            self._set_review_empty_state()
        else:
            self._load_frozen_verification()
        self._refresh_state()

    def _build_ui(self) -> None:
        root = QVBoxLayout(self)
        root.setContentsMargins(18, 16, 18, 16)
        root.setSpacing(10)

        title = QLabel(f"{self.node['node_code']}  {self.node['title']}")
        title.setObjectName("PageTitle")
        root.addWidget(title)
        sub = QLabel(
            "复测试卷必须换场景、换数据、换代码。" if self.review
            else "正式测试：试卷已在节点开始前冻结；未通过只重做同一张试卷，不改学习路线。"
        )
        sub.setObjectName("Secondary")
        sub.setWordWrap(True)
        root.addWidget(sub)

        self.paper_bar = QHBoxLayout()
        self.paper_label = QLabel("")
        self.paper_label.setObjectName("ProjectPath")
        self.paper_bar.addWidget(self.paper_label)
        self.paper_bar.addStretch(1)
        root.addLayout(self.paper_bar)

        self.review_test_bar = QHBoxLayout()
        self.copy_test_btn = QPushButton("复制复测出题提示词")
        self.copy_test_btn.setObjectName("PrimaryButton")
        self.paste_test_btn = QPushButton("粘贴复测试卷 JSON")
        self.paste_test_btn.setObjectName("SecondaryButton")
        self.review_test_bar.addWidget(self.copy_test_btn)
        self.review_test_bar.addWidget(self.paste_test_btn)
        self.review_test_bar.addStretch(1)
        root.addLayout(self.review_test_bar)

        note = QLabel(
            "每一道题都有独立回答框。主线首次正式测试使用固定试卷；只有 3日/7日/14日/30日复测才要求重新出不同场景的试卷。"
        )
        note.setObjectName("Muted")
        note.setWordWrap(True)
        root.addWidget(note)

        self.question_scroll = QScrollArea()
        self.question_scroll.setWidgetResizable(True)
        self.question_scroll.setObjectName("AssessmentScroll")
        self.question_host = QWidget()
        self.question_layout = QVBoxLayout(self.question_host)
        self.question_layout.setContentsMargins(0, 0, 4, 0)
        self.question_layout.setSpacing(10)
        self.question_scroll.setWidget(self.question_host)
        root.addWidget(self.question_scroll, 1)

        bottom = QHBoxLayout()
        self.save_answer_btn = QPushButton("保存全部回答")
        self.save_answer_btn.setObjectName("SecondaryButton")
        self.copy_grade_btn = QPushButton("复制评分提示词")
        self.copy_grade_btn.setObjectName("PrimaryButton")
        self.paste_grade_btn = QPushButton("粘贴评分 JSON")
        self.paste_grade_btn.setObjectName("SecondaryButton")
        self.retry_btn = QPushButton("重新作答同一冻结试卷")
        self.retry_btn.setObjectName("DangerButton")
        self.retry_btn.setVisible(False)
        bottom.addWidget(self.save_answer_btn)
        bottom.addWidget(self.copy_grade_btn)
        bottom.addWidget(self.paste_grade_btn)
        bottom.addWidget(self.retry_btn)
        bottom.addStretch(1)
        root.addLayout(bottom)

        self.result_label = QLabel("等待试卷")
        self.result_label.setObjectName("ResultBanner")
        self.result_label.setProperty("status", "info")
        self.result_label.setWordWrap(True)
        root.addWidget(self.result_label)

        self.copy_test_btn.clicked.connect(self._copy_test_prompt)
        self.paste_test_btn.clicked.connect(self._paste_test)
        self.save_answer_btn.clicked.connect(self._save_answer)
        self.copy_grade_btn.clicked.connect(self._copy_grade_prompt)
        self.paste_grade_btn.clicked.connect(self._paste_grade)
        self.retry_btn.clicked.connect(self._retry_same_paper)

    def _set_review_empty_state(self) -> None:
        self.review_test_bar.setEnabled(True)
        self.paper_label.setText(f"复测类型：{self.review.get('review_type')} · 到期日：{self.review.get('due_date')}")
        self._clear_questions()
        empty = QLabel("复测必须使用一张新试卷。先复制复测出题提示词，再粘贴 AI 返回的 JSON。")
        empty.setObjectName("Secondary")
        empty.setWordWrap(True)
        self.question_layout.addWidget(empty)
        self.question_layout.addStretch(1)
        self.result_label.setText("等待新的复测试卷")

    def _load_frozen_verification(self) -> None:
        self.copy_test_btn.setVisible(False)
        self.paste_test_btn.setVisible(False)
        paper = self.service.get_frozen_verification_paper(self.node["id"])
        self.test_json = {k: v for k, v in paper.items() if not k.startswith("_")}
        self.attempt_id = self.service.ensure_verification_attempt(self.node["id"])
        attempt = self.service.get_attempt(self.attempt_id)
        self.test_json = attempt["test"]
        self.paper_label.setText(
            f"固定试卷 {paper.get('_paper_code', paper.get('paper_id', 'V1'))} · 从节点开始即固定 · 未通过后继续使用同一试卷"
        )
        self._render_questions(self.test_json, attempt.get("answers", {}))
        self.result_label.setText(f"第 {attempt['attempt_no']} 次作答 · 请闭卷作答")
        self.result_label.setProperty("status", "info")
        self._repolish(self.result_label)

    def _refresh_state(self) -> None:
        has_attempt = self.attempt_id is not None and self.test_json is not None
        self.copy_grade_btn.setEnabled(has_attempt)
        self.paste_grade_btn.setEnabled(has_attempt)
        self.save_answer_btn.setEnabled(has_attempt)

    def _copy_test_prompt(self) -> None:
        if not self.review:
            return
        previous = self.service.previous_tests(self.node["id"])
        text = build_test_prompt(self.node, previous, is_retest=True)
        QGuiApplication.clipboard().setText(text)
        QMessageBox.information(self, "已复制", "复测出题提示词已复制。复测题必须换场景，AI 只返回 JSON。")

    def _validate_test(self, data: dict) -> None:
        questions = data.get("questions")
        if not isinstance(questions, list) or len(questions) != 5:
            raise ValueError("questions 必须严格包含 5 道题")
        expected = {
            "explanation": 15,
            "prediction": 15,
            "implementation": 25,
            "diagnosis": 25,
            "transfer": 20,
        }
        seen = set()
        question_ids = set()
        total = 0
        for question in questions:
            qid = str(question.get("id", "")).strip()
            if not qid:
                raise ValueError("每道题必须包含非空 id")
            if qid in question_ids:
                raise ValueError(f"重复 question id: {qid}")
            question_ids.add(qid)
            dimension = question.get("dimension")
            if dimension not in expected:
                raise ValueError(f"非法评分维度: {dimension}")
            if dimension in seen:
                raise ValueError(f"重复评分维度: {dimension}")
            seen.add(dimension)
            max_score = int(question.get("max_score", -1))
            if max_score != expected[dimension]:
                raise ValueError(f"{dimension} 的 max_score 必须为 {expected[dimension]}")
            total += max_score
            if not str(question.get("question", "")).strip():
                raise ValueError(f"{dimension} 题目为空")
        if seen != set(expected) or total != 100:
            raise ValueError("五个评分维度必须全部出现，且总分必须严格等于 100")
        node_id = data.get("node_id")
        if node_id and node_id != self.node["node_code"]:
            raise ValueError("试卷 node_id 与当前冻结节点不一致")

    def _paste_test(self) -> None:
        if not self.review:
            return
        dlg = JsonPasteDialog("粘贴复测试卷", self)
        if dlg.exec() != QDialog.DialogCode.Accepted:
            return
        try:
            data = dlg.value()
            self._validate_test(data)
            self.test_json = data
            self.attempt_id = self.service.create_attempt(self.node["id"], data, self.review["id"])
            self._render_questions(data)
            self.result_label.setText("复测试卷已导入 · 请逐题作答")
            self.result_label.setProperty("status", "info")
            self._repolish(self.result_label)
            self._refresh_state()
        except Exception as exc:
            QMessageBox.critical(self, "试卷 JSON 无效", str(exc))

    def _clear_questions(self) -> None:
        while self.question_layout.count():
            item = self.question_layout.takeAt(0)
            widget = item.widget()
            if widget is not None:
                widget.deleteLater()
        self.answer_editors.clear()

    def _render_questions(self, data: dict, answers: dict[str, str] | None = None) -> None:
        self._clear_questions()
        answers = answers or {}
        placeholders = {
            "explanation": "闭卷解释。不要只写定义；写清为什么、边界与因果关系。",
            "prediction": "先写预测，再写依据。不要先运行后补答案。",
            "implementation": "回答 + 可验证工程证据：代码位置、commit、测试命令、日志、抓包或实验结果。",
            "diagnosis": "按 观察 → 假设 → 证据 → 根因 → 验证 的顺序作答，并附真实证据。",
            "transfer": "处理题目给出的新场景，说明如何迁移当前能力与取舍。",
        }
        for index, q in enumerate(data.get("questions", []), start=1):
            card = QFrame()
            card.setObjectName("QuestionCard")
            card_layout = QVBoxLayout(card)
            card_layout.setContentsMargins(14, 12, 14, 14)
            card_layout.setSpacing(8)

            header = QLabel(f"Q{index}  ·  {DIMENSION_ZH.get(q.get('dimension'), q.get('dimension', '?'))}  ·  {q.get('max_score', '?')} 分")
            header.setObjectName("QuestionHeader")
            header.setProperty("dimension", q.get("dimension", ""))
            card_layout.addWidget(header)

            question = QLabel(str(q.get("question", "")))
            question.setObjectName("QuestionText")
            question.setWordWrap(True)
            question.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
            card_layout.addWidget(question)

            answer = QTextEdit()
            answer.setObjectName("AnswerEditor")
            answer.setMinimumHeight(130)
            answer.setPlaceholderText(placeholders.get(q.get("dimension"), "在这里回答。"))
            qid = str(q.get("id"))
            answer.setPlainText(str(answers.get(qid, "")))
            card_layout.addWidget(answer)

            self.answer_editors[qid] = answer
            self.question_layout.addWidget(card)
        self.question_layout.addStretch(1)
        self.question_scroll.verticalScrollBar().setValue(0)

    def _collect_answers(self) -> dict[str, str]:
        return {qid: editor.toPlainText().strip() for qid, editor in self.answer_editors.items()}

    def _save_answer(self) -> None:
        if self.attempt_id is None:
            return
        answers = self._collect_answers()
        self.service.save_answer(self.attempt_id, json.dumps(answers, ensure_ascii=False, indent=2))
        QMessageBox.information(self, "已保存", "每道题的回答已经按 question id 保存到 SQLite。")

    def _copy_grade_prompt(self) -> None:
        if self.attempt_id is None or self.test_json is None:
            return
        answers = self._collect_answers()
        empty = [qid for qid, text in answers.items() if not text]
        if empty:
            QMessageBox.warning(self, "存在未回答题目", f"以下题目仍为空：{', '.join(empty)}")
            return
        self.service.save_answer(self.attempt_id, json.dumps(answers, ensure_ascii=False, indent=2))
        prompt = build_grade_prompt(self.node, self.test_json, answers)
        QGuiApplication.clipboard().setText(prompt)
        QMessageBox.information(
            self, "已复制",
            "评分提示词已复制。AI 只给五维分数与证据；是否通过仍由 LearningCI 本地规则计算。",
        )

    def _paste_grade(self) -> None:
        if self.attempt_id is None:
            return
        dlg = JsonPasteDialog("粘贴 AI 评分", self)
        if dlg.exec() != QDialog.DialogCode.Accepted:
            return
        try:
            grade = dlg.value()
            result = self.service.grade_attempt(self.attempt_id, grade)
            if result["passed"]:
                self.result_label.setText(f"通过  {result['total']} / 100")
                self.result_label.setProperty("status", "pass")
                self.retry_btn.setVisible(False)
            else:
                reasons = "；".join(result["failures"])
                if self.review:
                    self.result_label.setText(
                        f"未通过  {result['total']} / 100  |  {reasons}\n复测未通过：进入补强队列；再次复测时必须使用新的变化题。"
                    )
                    self.copy_test_btn.setEnabled(True)
                    self.paste_test_btn.setEnabled(True)
                else:
                    self.result_label.setText(
                        f"未通过  {result['total']} / 100  |  {reasons}\n当前节点不推进。下一次作答继续使用同一张冻结试卷，不换题。"
                    )
                    self.retry_btn.setVisible(True)
                    self.retry_btn.setEnabled(True)
                self.result_label.setProperty("status", "fail")
            self._repolish(self.result_label)
            self.graded.emit()
            self.copy_grade_btn.setEnabled(False)
            self.paste_grade_btn.setEnabled(False)
            self.save_answer_btn.setEnabled(False)
        except Exception as exc:
            QMessageBox.critical(self, "评分 JSON 无效", str(exc))

    def _retry_same_paper(self) -> None:
        if self.review:
            return
        self.attempt_id = self.service.ensure_verification_attempt(self.node["id"])
        attempt = self.service.get_attempt(self.attempt_id)
        self.test_json = attempt["test"]
        self._render_questions(self.test_json, attempt.get("answers", {}))
        self.result_label.setText(f"第 {attempt['attempt_no']} 次作答 · 同一冻结试卷重新作答")
        self.result_label.setProperty("status", "info")
        self._repolish(self.result_label)
        self.retry_btn.setVisible(False)
        self._refresh_state()

    @staticmethod
    def _repolish(widget: QWidget) -> None:
        widget.style().unpolish(widget)
        widget.style().polish(widget)
