from __future__ import annotations

import json
from datetime import datetime

from PyQt6.QtCore import Qt, QTimer, pyqtSignal
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
    task_jump_requested = pyqtSignal(str)

    def __init__(self, service, node: dict, review: dict | None = None, parent=None):
        super().__init__(parent)
        self.service = service
        self.node = node
        self.review = review
        self.attempt_id: int | None = None
        self.test_json: dict | None = None
        self.answer_editors: dict[str, QTextEdit] = {}
        self._loading_answers = False
        self._owns_focus_session = False
        self.exam_timer = QTimer(self)
        self.exam_timer.setInterval(1000)
        self.exam_timer.timeout.connect(self._tick_exam_focus)
        self.answer_autosave_timer = QTimer(self)
        self.answer_autosave_timer.setSingleShot(True)
        self.answer_autosave_timer.setInterval(450)
        self.answer_autosave_timer.timeout.connect(self._autosave_answers)
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
        # v0.3.10: the whole assessment is one vertically scrollable page.
        # Do not give the question list / repair panel their own competing fixed
        # heights; otherwise a long repair panel squeezes the answer area until
        # the current question is almost invisible.
        shell = QVBoxLayout(self)
        shell.setContentsMargins(0, 0, 0, 0)
        shell.setSpacing(0)

        self.page_scroll = QScrollArea()
        self.page_scroll.setWidgetResizable(True)
        self.page_scroll.setObjectName("AssessmentScroll")
        self.page_scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.page_host = QWidget()
        root = QVBoxLayout(self.page_host)
        root.setContentsMargins(18, 16, 18, 18)
        root.setSpacing(10)
        self.page_scroll.setWidget(self.page_host)
        shell.addWidget(self.page_scroll, 1)

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
        self.paper_label.setWordWrap(True)
        self.paper_bar.addWidget(self.paper_label, 1)
        self.exam_timer_label = QLabel("00:00")
        self.exam_timer_label.setObjectName("FocusTimer")
        self.start_exam_btn = QPushButton("开始学习")
        self.start_exam_btn.setObjectName("SuccessButton")
        self.stop_exam_btn = QPushButton("结束学习")
        self.stop_exam_btn.setObjectName("DangerButton")
        self.paper_bar.addWidget(self.exam_timer_label)
        self.paper_bar.addWidget(self.start_exam_btn)
        self.paper_bar.addWidget(self.stop_exam_btn)
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
            "除系统自动复核项外，每道题都有独立回答框。历史审计节点的 implementation 直接复核已保存工程证据，不要求重复抄材料；只有复测才换场景。"
        )
        note.setObjectName("Muted")
        note.setWordWrap(True)
        root.addWidget(note)

        # Questions now participate in the same page scroll instead of living in
        # a nested QScrollArea. This keeps every question and answer editor at its
        # natural height even when feedback below becomes very long.
        self.question_host = QWidget()
        self.question_layout = QVBoxLayout(self.question_host)
        self.question_layout.setContentsMargins(0, 0, 4, 0)
        self.question_layout.setSpacing(10)
        root.addWidget(self.question_host)

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

        self.autosave_label = QLabel("自动保存：等待试卷")
        self.autosave_label.setObjectName("Muted")
        root.addWidget(self.autosave_label)

        self.result_label = QLabel("等待试卷")
        self.result_label.setObjectName("ResultBanner")
        self.result_label.setProperty("status", "info")
        self.result_label.setWordWrap(True)
        root.addWidget(self.result_label)

        self.repair_panel = QFrame()
        self.repair_panel.setObjectName("QuestionCard")
        repair_layout = QVBoxLayout(self.repair_panel)
        repair_layout.setContentsMargins(12, 10, 12, 12)
        repair_layout.setSpacing(8)
        repair_header = QHBoxLayout()
        self.repair_title = QLabel("修正面板")
        self.repair_title.setObjectName("QuestionHeader")
        self.repair_summary = QLabel("")
        self.repair_summary.setObjectName("Secondary")
        repair_header.addWidget(self.repair_title)
        repair_header.addStretch(1)
        repair_header.addWidget(self.repair_summary)
        repair_layout.addLayout(repair_header)

        repair_tip = QLabel("只修正本次正式测试暴露的问题，不需要把整个节点重新学一遍。")
        repair_tip.setObjectName("Muted")
        repair_tip.setWordWrap(True)
        repair_layout.addWidget(repair_tip)

        # Repair cards also use the outer page scroll. There is deliberately no
        # 180~380 px nested scroll viewport anymore.
        self.repair_host = QWidget()
        self.repair_issue_layout = QVBoxLayout(self.repair_host)
        self.repair_issue_layout.setContentsMargins(8, 8, 8, 8)
        self.repair_issue_layout.setSpacing(8)
        self.repair_issue_layout.addStretch(1)
        repair_layout.addWidget(self.repair_host)
        self.repair_panel.setVisible(False)
        root.addWidget(self.repair_panel)
        root.addStretch(1)

        self.start_exam_btn.clicked.connect(self._start_exam_focus)
        self.stop_exam_btn.clicked.connect(self._stop_exam_focus)
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
        self.autosave_label.setText("自动保存：等待复测试卷")

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
        auto_review = any(q.get("requires_answer", True) is False for q in self.test_json.get("questions", []))
        suffix = " · implementation 由系统自动复核已有证据" if auto_review else ""
        self.result_label.setText(f"第 {attempt['attempt_no']} 次作答 · 请闭卷作答{suffix}")
        self.result_label.setProperty("status", "info")
        self._repolish(self.result_label)
        self.autosave_label.setText("自动保存：已载入 SQLite")
        feedback = self.service.get_latest_failed_verification_feedback(self.node["id"])
        if feedback and int(feedback.get("attempt_id", -1)) != int(self.attempt_id or -1):
            self._render_repair_feedback(feedback)

    def _refresh_state(self) -> None:
        has_attempt = self.attempt_id is not None and self.test_json is not None
        self.copy_grade_btn.setEnabled(has_attempt)
        self.paste_grade_btn.setEnabled(has_attempt)
        self.save_answer_btn.setEnabled(has_attempt)
        active = self.service.active_focus_session()
        active_here = bool(active and int(active.get("node_id", -1)) == int(self.node["id"]))
        self.start_exam_btn.setEnabled(not active_here)
        self.stop_exam_btn.setEnabled(active_here)
        if active_here:
            self.exam_timer.start()
            self._tick_exam_focus()
        else:
            self.exam_timer.stop()
            self.exam_timer_label.setText("00:00")

    def _clear_repair_feedback(self) -> None:
        while self.repair_issue_layout.count() > 1:
            item = self.repair_issue_layout.takeAt(0)
            widget = item.widget()
            if widget is not None:
                widget.deleteLater()
        self.repair_panel.setVisible(False)
        self.repair_summary.setText("")

    @staticmethod
    def _answer_preview(text: str, limit: int = 650) -> str:
        text = str(text or "").strip()
        if len(text) <= limit:
            return text
        return text[:limit].rstrip() + "…"

    def _render_repair_feedback(self, feedback: dict | None, *, reveal: bool = False) -> None:
        self._clear_repair_feedback()
        if not feedback or feedback.get("passed"):
            return
        issues = feedback.get("issues", [])
        if not isinstance(issues, list) or not issues:
            return

        answers = feedback.get("answers", {}) if isinstance(feedback.get("answers", {}), dict) else {}
        self.repair_title.setText(f"修正面板 · 第 {feedback.get('attempt_no', '?')} 次正式测试")
        self.repair_summary.setText(f"{feedback.get('total', 0)} / 100 · 需要修正 {len(issues)} 项")

        for index, issue in enumerate(issues, start=1):
            if not isinstance(issue, dict):
                continue
            card = QFrame()
            card.setObjectName("SectionIssueCard")
            severity = str(issue.get("severity", "warning") or "warning").lower()
            if severity not in {"error", "warning", "info"}:
                severity = "warning"
            card.setProperty("severity", severity)
            layout = QVBoxLayout(card)
            layout.setContentsMargins(10, 9, 10, 10)
            layout.setSpacing(6)

            header = QHBoxLayout()
            number = QLabel(str(index))
            number.setObjectName("IssueIndex")
            header.addWidget(number, 0, Qt.AlignmentFlag.AlignTop)

            qid = str(issue.get("question_id", "") or "")
            if qid:
                qbadge = QLabel(qid.upper())
                qbadge.setObjectName("IssueTaskBadge")
                header.addWidget(qbadge, 0, Qt.AlignmentFlag.AlignTop)

            dimension = str(issue.get("dimension", "") or "")
            if dimension:
                dbadge = QLabel(DIMENSION_ZH.get(dimension, dimension))
                dbadge.setObjectName("IssueDimensionBadge")
                header.addWidget(dbadge, 0, Qt.AlignmentFlag.AlignTop)

            title = QLabel(str(issue.get("title", "需要修正") or "需要修正"))
            title.setObjectName("IssueTitle")
            title.setWordWrap(True)
            header.addWidget(title, 1)
            layout.addLayout(header)

            answer = self._answer_preview(answers.get(qid, "")) if qid else ""
            if answer:
                answer_label = QLabel(f"你的回答：\n{answer}")
                answer_label.setObjectName("IssueDetail")
                answer_label.setWordWrap(True)
                answer_label.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
                layout.addWidget(answer_label)

            detail = str(issue.get("detail", "") or "").strip()
            if detail:
                detail_label = QLabel(f"Reviewer 批注：\n{detail}")
                detail_label.setObjectName("IssueDetail")
                detail_label.setWordWrap(True)
                detail_label.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
                layout.addWidget(detail_label)

            correction = str(issue.get("correction", "") or "").strip()
            if correction:
                correction_label = QLabel(f"正确机制 / 修正方向：\n{correction}")
                correction_label.setObjectName("TaskCriteria")
                correction_label.setWordWrap(True)
                correction_label.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
                layout.addWidget(correction_label)

            task_ids = issue.get("related_task_ids", [])
            if isinstance(task_ids, str):
                task_ids = [task_ids]
            if isinstance(task_ids, list) and task_ids:
                task_row = QHBoxLayout()
                task_row.addWidget(QLabel("回看证据："))
                for task_id in [str(x).strip() for x in task_ids if str(x).strip()]:
                    jump = QPushButton(task_id)
                    jump.setObjectName("IssueJumpButton")
                    jump.setToolTip("关闭正式测试窗口并定位到这个叶子任务")
                    jump.clicked.connect(lambda _checked=False, tid=task_id: self._jump_to_repair_task(tid))
                    task_row.addWidget(jump)
                task_row.addStretch(1)
                layout.addLayout(task_row)

            self.repair_issue_layout.insertWidget(self.repair_issue_layout.count() - 1, card)

        self.repair_panel.setVisible(True)
        if reveal:
            QTimer.singleShot(0, lambda: self.page_scroll.ensureWidgetVisible(self.repair_panel, 0, 24))

    def _jump_to_repair_task(self, task_id: str) -> None:
        self._force_save_answers()
        self.task_jump_requested.emit(task_id)
        self.reject()

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
        is_history_audit = (
            str(self.node.get("node_code", "")) in {"NRPC-S0-01", "NRPC-S0-02"}
            or "历史能力审计" in str(self.node.get("title", ""))
        )
        if is_history_audit:
            implementation = next(q for q in questions if q.get("dimension") == "implementation")
            if implementation.get("requires_answer", True) is not False:
                raise ValueError("历史审计节点的 implementation 必须是系统自动复核项（requires_answer=false）")
            for question in questions:
                if question.get("dimension") != "implementation" and question.get("requires_answer", True) is False:
                    raise ValueError("历史审计节点只有 implementation 可以设置为无需学习者作答")
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
            self.autosave_label.setText("自动保存：已载入 SQLite")
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
        self._loading_answers = True
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

            qid = str(q.get("id"))
            if q.get("requires_answer", True) is False:
                system_note = QLabel(
                    "系统自动复核 · 无需作答。复制评分提示词时，LearningCI 会自动附带本节点已经保存的叶子任务工程证据与小节验收结果。"
                )
                system_note.setObjectName("Secondary")
                system_note.setWordWrap(True)
                card_layout.addWidget(system_note)
                self.question_layout.addWidget(card)
                continue

            answer = QTextEdit()
            answer.setObjectName("AnswerEditor")
            answer.setMinimumHeight(130)
            placeholder = placeholders.get(q.get("dimension"), "在这里回答。")
            is_history_audit = (
                str(self.node.get("node_code", "")) in {"NRPC-S0-01", "NRPC-S0-02"}
                or "历史能力审计" in str(self.node.get("title", ""))
            )
            if is_history_audit and q.get("dimension") == "diagnosis":
                placeholder = "直接分析这个具体故障：错误判断发生在哪里、为什么、原机制如何避免。无需重复抄源码路径。"
            answer.setPlaceholderText(placeholder)
            answer.setPlainText(str(answers.get(qid, "")))
            answer.textChanged.connect(self._schedule_answer_autosave)
            card_layout.addWidget(answer)

            self.answer_editors[qid] = answer
            self.question_layout.addWidget(card)
        self.question_layout.addStretch(1)
        self.page_scroll.verticalScrollBar().setValue(0)
        self._loading_answers = False

    def _collect_answers(self) -> dict[str, str]:
        return {qid: editor.toPlainText().strip() for qid, editor in self.answer_editors.items()}

    def _schedule_answer_autosave(self) -> None:
        if self._loading_answers or self.attempt_id is None:
            return
        self.autosave_label.setText("自动保存：等待写入…")
        self.answer_autosave_timer.start()

    def _autosave_answers(self) -> None:
        if self.attempt_id is None:
            return
        answers = self._collect_answers()
        self.service.save_answer(self.attempt_id, json.dumps(answers, ensure_ascii=False, indent=2))
        self.autosave_label.setText(f"自动保存：已保存 {datetime.now().strftime('%H:%M:%S')}")

    def _force_save_answers(self) -> None:
        if self.answer_autosave_timer.isActive():
            self.answer_autosave_timer.stop()
        if self.attempt_id is None:
            return
        self._autosave_answers()

    def _save_answer(self) -> None:
        if self.attempt_id is None:
            return
        self._force_save_answers()
        QMessageBox.information(self, "已保存", "每道题的回答已经按 question id 保存到 SQLite。")

    def _start_exam_focus(self) -> None:
        active = self.service.active_focus_session()
        if active:
            if int(active.get("node_id", -1)) != int(self.node["id"]):
                QMessageBox.warning(self, "已有学习计时", "当前存在其他节点的学习计时，请先结束后再开始正式测试计时。")
                return
            self._owns_focus_session = True
        else:
            self.service.start_focus(self.node["id"])
            self._owns_focus_session = True
        self.exam_timer.start()
        self._tick_exam_focus()
        self._refresh_state()

    def _stop_exam_focus(self) -> None:
        active = self.service.active_focus_session()
        if active and int(active.get("node_id", -1)) == int(self.node["id"]):
            self.service.end_focus()
        self._owns_focus_session = False
        self.exam_timer.stop()
        self.exam_timer_label.setText("00:00")
        self._refresh_state()

    def _tick_exam_focus(self) -> None:
        active = self.service.active_focus_session()
        if not active or int(active.get("node_id", -1)) != int(self.node["id"]):
            self.exam_timer.stop()
            self.exam_timer_label.setText("00:00")
            self.start_exam_btn.setEnabled(True)
            self.stop_exam_btn.setEnabled(False)
            return
        elapsed = max(0, int((datetime.now() - datetime.fromisoformat(active["started_at"])).total_seconds()))
        minutes, seconds = divmod(elapsed, 60)
        hours, minutes = divmod(minutes, 60)
        self.exam_timer_label.setText(f"{hours:02d}:{minutes:02d}:{seconds:02d}" if hours else f"{minutes:02d}:{seconds:02d}")

    def _copy_grade_prompt(self) -> None:
        if self.attempt_id is None or self.test_json is None:
            return
        answers = self._collect_answers()
        empty = [qid for qid, text in answers.items() if not text]
        if empty:
            QMessageBox.warning(self, "存在未回答题目", f"以下题目仍为空：{', '.join(empty)}")
            return
        self._force_save_answers()
        has_system_review = any(
            q.get("requires_answer", True) is False for q in self.test_json.get("questions", [])
        )
        system_evidence = (
            self.service.get_verification_evidence_context(self.node["id"]) if has_system_review else None
        )
        prompt = build_grade_prompt(self.node, self.test_json, answers, system_evidence=system_evidence)
        QGuiApplication.clipboard().setText(prompt)
        QMessageBox.information(
            self, "已复制",
            "评分提示词已复制。AI 只给五维分数与证据；是否通过仍由 LearningCI 本地规则计算。",
        )

    def _paste_grade(self) -> None:
        if self.attempt_id is None:
            return
        self._force_save_answers()
        dlg = JsonPasteDialog("粘贴 AI 评分", self)
        if dlg.exec() != QDialog.DialogCode.Accepted:
            return
        try:
            grade = dlg.value()
            result = self.service.grade_attempt(self.attempt_id, grade)
            if result["passed"]:
                if result.get("mastered"):
                    self.result_label.setText(
                        f"稳定掌握  {result['total']} / 100  ·  下一节点已解锁"
                    )
                else:
                    self.result_label.setText(
                        f"通过（带薄弱点）  {result['total']} / 100  ·  下一节点已解锁\n"
                        f"70 分用于主线推进；{result.get('mastery_score', 80)} 分及维度门槛用于稳定掌握。薄弱点留到复测继续验证。"
                    )
                self.result_label.setProperty("status", "pass")
                self.retry_btn.setVisible(False)
                self._clear_repair_feedback()
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
                        f"未通过  {result['total']} / 100  |  {reasons}\n"
                        "总分达到 70 后即可推进下一节点；当前只修正真正暴露的关键机制，同一张冻结试卷继续作答。"
                    )
                    self.retry_btn.setVisible(True)
                    self.retry_btn.setEnabled(True)
                self.result_label.setProperty("status", "fail")
                feedback = self.service.get_attempt_feedback(self.attempt_id)
                self._render_repair_feedback(feedback, reveal=True)
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
        self._force_save_answers()
        self.attempt_id = self.service.ensure_verification_attempt(self.node["id"])
        attempt = self.service.get_attempt(self.attempt_id)
        self.test_json = attempt["test"]
        self._render_questions(self.test_json, attempt.get("answers", {}))
        self.result_label.setText(f"第 {attempt['attempt_no']} 次作答 · 同一冻结试卷重新作答")
        self.result_label.setProperty("status", "info")
        self._repolish(self.result_label)
        self.retry_btn.setVisible(False)
        self._refresh_state()

    def done(self, result: int) -> None:
        # 正式测试/复测回答和主页面叶子任务一样，关闭窗口前必须强制落盘。
        self._force_save_answers()
        # AssessmentDialog 是从“无活动学习计时”状态进入的；如果计时由本窗口启动，
        # 关闭窗口时自动结束，避免后台留下永不结束的 focus_session。
        if self._owns_focus_session:
            active = self.service.active_focus_session()
            if active and int(active.get("node_id", -1)) == int(self.node["id"]):
                self.service.end_focus()
            self._owns_focus_session = False
        self.exam_timer.stop()
        super().done(result)

    @staticmethod
    def _repolish(widget: QWidget) -> None:
        widget.style().unpolish(widget)
        widget.style().polish(widget)
