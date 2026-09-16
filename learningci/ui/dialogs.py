from __future__ import annotations

import json

from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtGui import QGuiApplication
from PyQt6.QtWidgets import (
    QDialog, QDialogButtonBox, QFrame, QHBoxLayout, QLabel, QMessageBox,
    QPushButton, QScrollArea, QTextEdit, QVBoxLayout, QWidget
)

from learningci.core.prompt_builder import build_grade_prompt, build_test_prompt


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
        self.setWindowTitle("LearningCI - 复测" if review else "LearningCI - Verification")
        self.resize(1040, 860)
        self.setMinimumSize(900, 680)
        self._build_ui()
        self._refresh_state()

    def _build_ui(self) -> None:
        root = QVBoxLayout(self)
        root.setContentsMargins(18, 16, 18, 16)
        root.setSpacing(10)

        title = QLabel(f"{self.node['node_code']}  {self.node['title']}")
        title.setObjectName("PageTitle")
        root.addWidget(title)
        sub = QLabel("复测试卷必须换场景、换数据、换代码。" if self.review else "正式 Verification：AI 只出题与评分，本地规则决定 PASS / FAIL。")
        sub.setObjectName("Secondary")
        root.addWidget(sub)

        bar = QHBoxLayout()
        self.copy_test_btn = QPushButton("复制出题 Prompt")
        self.copy_test_btn.setObjectName("PrimaryButton")
        self.paste_test_btn = QPushButton("粘贴试卷 JSON")
        self.paste_test_btn.setObjectName("SecondaryButton")
        bar.addWidget(self.copy_test_btn)
        bar.addWidget(self.paste_test_btn)
        bar.addStretch(1)
        root.addLayout(bar)

        note = QLabel("粘贴试卷后，每一道题会自动生成独立回答框；问题会固定显示在回答框上方，不需要来回翻看。")
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
        empty = QLabel("尚未导入试卷。先复制出题 Prompt，在聊天式 AI 中生成 JSON，再粘贴回来。")
        empty.setObjectName("Secondary")
        empty.setWordWrap(True)
        self.question_layout.addWidget(empty)
        self.question_layout.addStretch(1)
        self.question_scroll.setWidget(self.question_host)
        root.addWidget(self.question_scroll, 1)

        bottom = QHBoxLayout()
        self.save_answer_btn = QPushButton("保存全部回答")
        self.save_answer_btn.setObjectName("SecondaryButton")
        self.copy_grade_btn = QPushButton("复制评分 Prompt")
        self.copy_grade_btn.setObjectName("PrimaryButton")
        self.paste_grade_btn = QPushButton("粘贴评分 JSON")
        self.paste_grade_btn.setObjectName("SecondaryButton")
        bottom.addWidget(self.save_answer_btn)
        bottom.addWidget(self.copy_grade_btn)
        bottom.addWidget(self.paste_grade_btn)
        bottom.addStretch(1)
        root.addLayout(bottom)

        self.result_label = QLabel("等待试卷")
        self.result_label.setObjectName("ResultBanner")
        self.result_label.setProperty("status", "info")
        root.addWidget(self.result_label)

        self.copy_test_btn.clicked.connect(self._copy_test_prompt)
        self.paste_test_btn.clicked.connect(self._paste_test)
        self.save_answer_btn.clicked.connect(self._save_answer)
        self.copy_grade_btn.clicked.connect(self._copy_grade_prompt)
        self.paste_grade_btn.clicked.connect(self._paste_grade)

    def _refresh_state(self) -> None:
        has_attempt = self.attempt_id is not None and self.test_json is not None
        self.copy_grade_btn.setEnabled(has_attempt)
        self.paste_grade_btn.setEnabled(has_attempt)
        self.save_answer_btn.setEnabled(has_attempt)

    def _copy_test_prompt(self) -> None:
        previous = self.service.previous_tests(self.node["id"])
        text = build_test_prompt(self.node, previous, is_retest=bool(self.review))
        QGuiApplication.clipboard().setText(text)
        QMessageBox.information(self, "已复制", "出题 Prompt 已复制。把它粘贴到聊天式 AI，AI 只返回 JSON。")

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
        if seen != set(expected):
            raise ValueError("五个评分维度必须全部出现")
        if total != 100:
            raise ValueError("试卷总分必须严格等于 100")
        node_id = data.get("node_id")
        if node_id and node_id != self.node["node_code"]:
            raise ValueError("试卷 node_id 与当前冻结节点不一致")

    def _paste_test(self) -> None:
        dlg = JsonPasteDialog("粘贴正式试卷", self)
        if dlg.exec() != QDialog.DialogCode.Accepted:
            return
        try:
            data = dlg.value()
            self._validate_test(data)
            self.test_json = data
            self.attempt_id = self.service.create_attempt(
                self.node["id"], data, self.review["id"] if self.review else None
            )
            self._render_questions(data)
            self.result_label.setText("试卷已导入 · 请逐题作答")
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

    def _render_questions(self, data: dict) -> None:
        self._clear_questions()
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

            header = QLabel(
                f"Q{index}  ·  {q.get('dimension', '?').upper()}  ·  {q.get('max_score', '?')} 分"
            )
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
            answer.setMinimumHeight(120)
            answer.setPlaceholderText(placeholders.get(q.get("dimension"), "在这里回答。"))
            card_layout.addWidget(answer)

            qid = str(q.get("id"))
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
        answer_json = json.dumps(answers, ensure_ascii=False, indent=2)
        self.service.save_answer(self.attempt_id, answer_json)
        prompt = build_grade_prompt(self.node, self.test_json, answers)
        QGuiApplication.clipboard().setText(prompt)
        QMessageBox.information(self, "已复制", "评分 Prompt 已复制。AI 只给五维分数与证据；PASS / FAIL 仍由 LearningCI 本地规则计算。")

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
                self.result_label.setText(f"PASS  {result['total']} / 100")
                self.result_label.setProperty("status", "pass")
            else:
                reasons = "；".join(result["failures"])
                self.result_label.setText(f"FAIL  {result['total']} / 100  |  {reasons}\n当前节点不推进，请生成一套不同试卷重新验证。")
                self.result_label.setProperty("status", "fail")
            self._repolish(self.result_label)
            self.graded.emit()

            # Failed attempts may immediately generate a new paper, including review attempts.
            self.copy_test_btn.setEnabled(not result["passed"])
            self.paste_test_btn.setEnabled(not result["passed"])
            self.copy_grade_btn.setEnabled(False)
            self.paste_grade_btn.setEnabled(False)
            self.save_answer_btn.setEnabled(False)
        except Exception as exc:
            QMessageBox.critical(self, "评分 JSON 无效", str(exc))

    @staticmethod
    def _repolish(widget: QWidget) -> None:
        widget.style().unpolish(widget)
        widget.style().polish(widget)
