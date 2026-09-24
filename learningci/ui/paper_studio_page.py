"""试卷工作台页面。

链路：导入试卷 -> 限时闭卷作答 -> 导出给 AI 评分 -> 导入评分 -> 只看分数与错题。

和「今日学习」里的正式验收是两条独立链路：正式验收绑定节点、五维评分与主线推进；
这里只服务“我是否真的掌握了某一段内容”这种自发验证，因此试卷可以随便出、随便删。
"""

from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path

from PyQt6.QtCore import Qt, QTimer
from PyQt6.QtGui import QGuiApplication
from PyQt6.QtWidgets import (
    QDialog, QDialogButtonBox, QFileDialog, QFrame, QHBoxLayout, QLabel,
    QListWidget, QListWidgetItem, QMessageBox, QPushButton, QScrollArea,
    QTextEdit, QVBoxLayout, QWidget,
)

from learningci.config import STUDIO_EXPORT_DIR, STUDIO_IMPORT_DIR
from learningci.core.paper_studio import (
    ATTEMPT_GRADED, ATTEMPT_OPEN, ATTEMPT_SUBMITTED, DIMENSION_ZH,
    PLACEHOLDER_BY_DIMENSION, PaperStudioError, answers_are_blank, format_duration,
)
from learningci.ui.dialogs import JsonPasteDialog


class TextViewDialog(QDialog):
    """只读文本查看器。用于展示标准答案这类长文本。"""

    def __init__(self, title: str, text: str, parent=None):
        super().__init__(parent)
        self.setWindowTitle(title)
        self.resize(820, 620)
        layout = QVBoxLayout(self)
        editor = QTextEdit()
        editor.setReadOnly(True)
        editor.setPlainText(text)
        layout.addWidget(editor, 1)
        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Close)
        buttons.rejected.connect(self.reject)
        buttons.accepted.connect(self.accept)
        layout.addWidget(buttons)


def loads_lenient(text: str) -> dict:
    """解析用户粘贴的 JSON。AI 经常无视“不要 fence”的要求，这里主动剥掉代码块。"""
    payload = text.strip()
    if payload.startswith("```"):
        lines = payload.splitlines()
        if lines and lines[0].startswith("```"):
            lines = lines[1:]
        if lines and lines[-1].strip().startswith("```"):
            lines = lines[:-1]
        payload = "\n".join(lines).strip()
    data = json.loads(payload)
    if not isinstance(data, dict):
        raise ValueError("JSON 顶层必须是对象")
    return data


def repolish(widget: QWidget) -> None:
    widget.style().unpolish(widget)
    widget.style().polish(widget)


class PaperStudioPage(QWidget):
    def __init__(self, service, parent=None):
        super().__init__(parent)
        self.service = service
        self.paper_id: int | None = None
        self.attempt_id: int | None = None
        self.answer_editors: dict[str, QTextEdit] = {}
        self._loading_answers = False

        self.autosave_timer = QTimer(self)
        self.autosave_timer.setSingleShot(True)
        self.autosave_timer.setInterval(450)
        self.autosave_timer.timeout.connect(self._autosave_answers)

        self.clock = QTimer(self)
        self.clock.setInterval(1000)
        self.clock.timeout.connect(self._tick)

        self._build_ui()
        self.refresh()

    # ------------------------------------------------------------------ UI

    def _build_ui(self) -> None:
        root = QVBoxLayout(self)
        root.setContentsMargins(24, 20, 24, 24)
        root.setSpacing(12)

        title = QLabel("试卷工作台")
        title.setObjectName("PageTitle")
        sub = QLabel(
            "自己出题、限时闭卷作答、交 AI 评分，然后只看两件事：得了几分，错在哪里。"
            "「开始作答」会接着上一次写过的答案写，并把那一次的批注挂到各题下面；"
            "「重新作答」才是空白、不带批注。"
            "这张试卷完全独立于节点的正式验收。"
        )
        sub.setObjectName("PageSub")
        sub.setWordWrap(True)
        root.addWidget(title)
        root.addWidget(sub)
        root.addSpacing(4)

        body = QHBoxLayout()
        body.setSpacing(14)
        body.addWidget(self._build_left_panel())
        body.addWidget(self._build_right_panel(), 1)
        root.addLayout(body, 1)

    def _build_left_panel(self) -> QWidget:
        panel = QFrame()
        panel.setObjectName("Card")
        panel.setFixedWidth(300)
        layout = QVBoxLayout(panel)
        layout.setContentsMargins(14, 14, 14, 14)
        layout.setSpacing(8)

        head = QLabel("我的试卷")
        head.setObjectName("SectionTitle")
        layout.addWidget(head)

        self.paper_list = QListWidget()
        self.paper_list.setObjectName("StudioPaperList")
        self.paper_list.currentItemChanged.connect(lambda *_: self._on_paper_selected())
        layout.addWidget(self.paper_list, 1)

        import_file = QPushButton("导入试卷文件")
        import_file.setObjectName("PrimaryButton")
        import_file.clicked.connect(self._import_paper_file)
        layout.addWidget(import_file)

        paste = QPushButton("粘贴试卷 JSON")
        paste.setObjectName("SecondaryButton")
        paste.clicked.connect(self._paste_paper)
        layout.addWidget(paste)

        self.delete_btn = QPushButton("删除选中试卷")
        self.delete_btn.setObjectName("DangerButton")
        self.delete_btn.clicked.connect(self._delete_paper)
        layout.addWidget(self.delete_btn)

        hint = QLabel("试卷是普通 JSON 文件。节点执行包里的冻结试卷不会出现在这里，也不会被改动。")
        hint.setObjectName("Muted")
        hint.setWordWrap(True)
        layout.addWidget(hint)
        return panel

    def _build_right_panel(self) -> QWidget:
        self.scroll = QScrollArea()
        self.scroll.setObjectName("AssessmentScroll")
        self.scroll.setWidgetResizable(True)
        container = QWidget()
        self.scroll.setWidget(container)

        layout = QVBoxLayout(container)
        layout.setContentsMargins(0, 0, 8, 0)
        layout.setSpacing(12)

        layout.addWidget(self._build_info_card())

        self.question_host = QWidget()
        self.question_layout = QVBoxLayout(self.question_host)
        self.question_layout.setContentsMargins(0, 0, 0, 0)
        self.question_layout.setSpacing(12)
        layout.addWidget(self.question_host)

        layout.addWidget(self._build_action_card())
        layout.addWidget(self._build_grade_card())
        layout.addStretch(1)
        return self.scroll

    def _build_info_card(self) -> QWidget:
        card = QFrame()
        card.setObjectName("Card")
        layout = QVBoxLayout(card)
        layout.setContentsMargins(16, 14, 16, 16)
        layout.setSpacing(8)

        self.paper_title = QLabel("未选择试卷")
        self.paper_title.setObjectName("SectionTitle")
        self.paper_title.setWordWrap(True)
        layout.addWidget(self.paper_title)

        self.paper_meta = QLabel("左侧导入或选择一张试卷开始。")
        self.paper_meta.setObjectName("Secondary")
        self.paper_meta.setWordWrap(True)
        layout.addWidget(self.paper_meta)

        timer_row = QHBoxLayout()
        self.timer_label = QLabel("00:00")
        self.timer_label.setObjectName("FocusTimer")
        timer_row.addWidget(self.timer_label)
        self.timer_note = QLabel("计时从开始作答算，交卷即停。")
        self.timer_note.setObjectName("Muted")
        self.timer_note.setWordWrap(True)
        timer_row.addWidget(self.timer_note, 1)
        layout.addLayout(timer_row)

        self.status_label = QLabel("")
        self.status_label.setObjectName("Secondary")
        self.status_label.setWordWrap(True)
        layout.addWidget(self.status_label)

        buttons = QHBoxLayout()
        self.start_btn = QPushButton("开始作答")
        self.start_btn.setObjectName("PrimaryButton")
        self.start_btn.setToolTip("以上一次写过的答案为基础继续写；没有任何历史时才是空白。")
        self.start_btn.clicked.connect(lambda: self._start_attempt(inherit=True))

        self.submit_btn = QPushButton("交卷")
        self.submit_btn.setObjectName("SuccessButton")
        self.submit_btn.setToolTip("停止计时并解锁标准答案。")
        self.submit_btn.clicked.connect(self._submit_attempt)

        self.cancel_btn = QPushButton("取消作答")
        self.cancel_btn.setObjectName("DangerButton")
        self.cancel_btn.setToolTip("中止这次作答：一个字没写就直接作废；写了东西会先问你要不要交卷。")
        self.cancel_btn.clicked.connect(self._cancel_attempt)

        self.retry_btn = QPushButton("重新作答")
        self.retry_btn.setObjectName("SecondaryButton")
        self.retry_btn.setToolTip("从空白开始，不带上一次写过的答案。")
        self.retry_btn.clicked.connect(lambda: self._start_attempt(inherit=False))

        for button in (self.start_btn, self.submit_btn, self.cancel_btn, self.retry_btn):
            buttons.addWidget(button)
        buttons.addStretch(1)
        layout.addLayout(buttons)
        return card

    def _build_action_card(self) -> QWidget:
        card = QFrame()
        card.setObjectName("Card")
        layout = QVBoxLayout(card)
        layout.setContentsMargins(16, 14, 16, 16)
        layout.setSpacing(8)

        head = QLabel("评分与报告")
        head.setObjectName("SectionTitle")
        layout.addWidget(head)

        buttons = QHBoxLayout()
        self.export_review_btn = QPushButton("导出给 AI 评分")
        self.export_review_btn.setObjectName("PrimaryButton")
        self.export_review_btn.clicked.connect(self._export_review_request)

        self.import_grade_btn = QPushButton("导入评分")
        self.import_grade_btn.setObjectName("PrimaryButton")
        self.import_grade_btn.clicked.connect(self._import_grade)

        self.answer_key_btn = QPushButton("查看标准答案")
        self.answer_key_btn.setObjectName("SecondaryButton")
        self.answer_key_btn.clicked.connect(self._show_answer_key)

        self.export_report_btn = QPushButton("导出精简报告")
        self.export_report_btn.setObjectName("SecondaryButton")
        self.export_report_btn.clicked.connect(self._export_report)

        for button in (self.export_review_btn, self.import_grade_btn, self.answer_key_btn, self.export_report_btn):
            buttons.addWidget(button)
        buttons.addStretch(1)
        layout.addLayout(buttons)

        self.action_hint = QLabel("")
        self.action_hint.setObjectName("Muted")
        self.action_hint.setWordWrap(True)
        layout.addWidget(self.action_hint)
        return card

    def _build_grade_card(self) -> QWidget:
        card = QFrame()
        card.setObjectName("Card")
        card.setVisible(False)
        self.grade_card = card
        layout = QVBoxLayout(card)
        layout.setContentsMargins(16, 14, 16, 16)
        layout.setSpacing(8)

        head = QLabel("本次评分")
        head.setObjectName("SectionTitle")
        layout.addWidget(head)

        self.grade_banner = QLabel("")
        self.grade_banner.setObjectName("ResultBanner")
        self.grade_banner.setWordWrap(True)
        layout.addWidget(self.grade_banner)

        self.grade_summary = QLabel("")
        self.grade_summary.setObjectName("Secondary")
        self.grade_summary.setWordWrap(True)
        layout.addWidget(self.grade_summary)

        self.score_line = QLabel("")
        self.score_line.setObjectName("Muted")
        self.score_line.setWordWrap(True)
        layout.addWidget(self.score_line)

        self.issue_host = QWidget()
        self.issue_layout = QVBoxLayout(self.issue_host)
        self.issue_layout.setContentsMargins(0, 0, 0, 0)
        self.issue_layout.setSpacing(8)
        layout.addWidget(self.issue_host)
        return card

    # ------------------------------------------------------------- 试卷选择

    def refresh(self) -> None:
        papers = self.service.studio.list_papers()
        keep = self.paper_id
        self.paper_list.blockSignals(True)
        self.paper_list.clear()
        for paper in papers:
            payload = paper.get("paper", {})
            count = len(payload.get("questions", [])) if isinstance(payload, dict) else 0
            item = QListWidgetItem(f"{paper['title']}\n{paper['paper_code']} · {count} 题 · {float(payload.get('max_score', 0)):g} 分")
            item.setData(Qt.ItemDataRole.UserRole, int(paper["id"]))
            self.paper_list.addItem(item)
        self.paper_list.blockSignals(False)

        if not papers:
            self.paper_id = None
            self.attempt_id = None
            self.paper_title.setText("未选择试卷")
            self.paper_meta.setText("左侧导入或选择一张试卷开始。")
            self._clear_questions()
            self.grade_card.setVisible(False)
            self._sync_buttons()
            return

        target_row = 0
        if keep is not None:
            for row in range(self.paper_list.count()):
                if int(self.paper_list.item(row).data(Qt.ItemDataRole.UserRole)) == int(keep):
                    target_row = row
                    break
        self.paper_list.setCurrentRow(target_row)
        self._on_paper_selected()

    def _on_paper_selected(self) -> None:
        item = self.paper_list.currentItem()
        if item is None:
            return
        self.paper_id = int(item.data(Qt.ItemDataRole.UserRole))
        self._discard_blank_attempts()
        self._load_paper()

    def _discard_blank_attempts(self) -> None:
        """选中试卷时清掉空白作答。

        空白记录本身没有信息量，却会把“最近一次”这个位置占住，让下一次继承
        找不到真正的底稿。代价是那一次的计时跟着归零 —— 但它本来就没落笔。
        """
        if self.paper_id is None:
            return
        removed = self.service.studio.discard_blank_attempts(self.paper_id)
        if removed and self.attempt_id in removed:
            self.attempt_id = None

    def _load_paper(self) -> None:
        if self.paper_id is None:
            return
        paper_row = self.service.studio.get_paper(self.paper_id)
        if paper_row is None:
            return
        payload = paper_row.get("paper", {})
        payload = payload if isinstance(payload, dict) else {}
        questions = [q for q in payload.get("questions", []) if isinstance(q, dict)]

        self.paper_title.setText(str(paper_row["title"]))
        attempt_count = int(paper_row.get("attempt_count", 0))
        limit = int(payload.get("time_limit_minutes", 0) or 0)
        head = (
            f"{paper_row['paper_code']} · {len(questions)} 题"
            f" · 总分 {float(payload.get('max_score', 0)):g}"
        )
        head += f" · 限时 {limit} 分钟" if limit else " · 不限时"
        lines = [head]
        if payload.get("description"):
            lines.append(str(payload["description"]))
        lines.append(f"历史作答 {attempt_count} 次")
        self.paper_meta.setText("\n".join(lines))

        open_attempt = self.service.studio.open_attempt(self.paper_id)
        latest = self.service.studio.latest_attempt(self.paper_id)

        if open_attempt is not None:
            self.attempt_id = int(open_attempt["id"])
            answers = open_attempt.get("answers", {})
            readonly = False
        elif latest is not None:
            # 已交卷时默认回看最近一次，方便导入评分与看报告。
            # 回看态必须只读：那条记录是评分与报告的底稿，再被改写就对不上分。
            self.attempt_id = int(latest["id"])
            answers = latest.get("answers", {})
            readonly = True
        else:
            self.attempt_id = None
            answers = {}
            readonly = False

        self._render_questions(
            questions,
            answers if isinstance(answers, dict) else {},
            readonly=readonly,
            prior=self._prior_annotations(open_attempt),
        )
        self._render_grade()
        self._sync_buttons()
        self._tick()

    def _prior_annotations(self, open_attempt: dict | None) -> dict[str, object] | None:
        """作答进行中才显示历史批注。

        来源由服务层按「这条作答的底稿是哪一条」给出，所以只有「开始作答」（继承上一次）
        才有批注；「重新作答」是空白起手，没有来源，整卷不挂批注。
        """
        if open_attempt is None or self.attempt_id is None:
            return None
        prior = self.service.studio.inherited_annotations(self.attempt_id)
        if prior is None:
            return None
        grouped = prior.get("by_question")
        if not isinstance(grouped, dict) or not grouped:
            return None
        return prior

    def _import_paper_file(self) -> None:
        path, _ = QFileDialog.getOpenFileName(
            self, "导入试卷", str(STUDIO_IMPORT_DIR), "JSON 文件 (*.json);;所有文件 (*)"
        )
        if not path:
            return
        try:
            raw = json.loads(Path(path).read_text(encoding="utf-8"))
            paper = self.service.studio.import_paper(raw, source_path=path)
        except (OSError, json.JSONDecodeError) as exc:
            QMessageBox.critical(self, "试卷文件读取失败", str(exc))
            return
        except PaperStudioError as exc:
            QMessageBox.critical(self, "试卷格式不正确", str(exc))
            return

        self.paper_id = int(paper["id"])
        self.refresh()
        QMessageBox.information(self, "试卷已导入", f"{paper['title']}\n{paper['paper_code']}")

    def _paste_paper(self) -> None:
        dialog = JsonPasteDialog("粘贴试卷", self)
        if dialog.exec() != QDialog.DialogCode.Accepted:
            return
        try:
            paper = self.service.studio.import_paper(loads_lenient(dialog.editor.toPlainText()))
        except (json.JSONDecodeError, ValueError) as exc:
            QMessageBox.critical(self, "试卷 JSON 无效", str(exc))
            return
        except PaperStudioError as exc:
            QMessageBox.critical(self, "试卷格式不正确", str(exc))
            return
        self.paper_id = int(paper["id"])
        self.refresh()

    def _delete_paper(self) -> None:
        if self.paper_id is None:
            QMessageBox.information(self, "没有选中试卷", "先在左侧选择一张试卷。")
            return
        paper = self.service.studio.get_paper(self.paper_id)
        if paper is None:
            return
        reply = QMessageBox.question(
            self,
            "删除试卷",
            f"删除《{paper['title']}》会连带删除它的 {int(paper.get('attempt_count', 0))} 次作答和评分记录。\n\n继续？",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.Cancel,
            QMessageBox.StandardButton.Cancel,
        )
        if reply != QMessageBox.StandardButton.Yes:
            return
        self.service.studio.delete_paper(self.paper_id)
        self.paper_id = None
        self.attempt_id = None
        self.refresh()

    # ------------------------------------------------------------- 作答

    def _clear_questions(self) -> None:
        while self.question_layout.count():
            item = self.question_layout.takeAt(0)
            widget = item.widget()
            if widget is not None:
                widget.deleteLater()
        self.answer_editors.clear()

    def _render_questions(
        self,
        questions: list[dict],
        answers: dict[str, str],
        *,
        readonly: bool = False,
        prior: dict[str, object] | None = None,
    ) -> None:
        """渲染题目与作答框。

        `prior` 非空表示这次是「开始作答」—— 答案继承自上一次，于是把那一次留下的批注
        按题挂回各自题目下方，边写边能看见上次错在哪。重新作答时这里是 None，整卷干净。
        """
        self._loading_answers = True
        self._clear_questions()

        grouped = prior.get("by_question") if prior else None
        grouped = grouped if isinstance(grouped, dict) else {}
        if grouped:
            self.question_layout.addWidget(self._build_prior_banner(prior))

        for index, question in enumerate(questions, start=1):
            card = QFrame()
            card.setObjectName("QuestionCard")
            layout = QVBoxLayout(card)
            layout.setContentsMargins(14, 12, 14, 14)
            layout.setSpacing(8)

            dimension = str(question.get("dimension") or "")
            header_text = (
                f"Q{index} · {DIMENSION_ZH.get(dimension, dimension or '未分类')}"
                f" · {float(question.get('max_score', 0)):g} 分"
            )
            if question.get("title"):
                header_text += f" · {question['title']}"
            header = QLabel(header_text)
            header.setObjectName("QuestionHeader")
            layout.addWidget(header)

            body = QLabel(str(question.get("question", "")))
            body.setObjectName("QuestionText")
            body.setWordWrap(True)
            body.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
            layout.addWidget(body)

            qid = str(question.get("id"))
            editor = QTextEdit()
            editor.setObjectName("AnswerEditor")
            editor.setMinimumHeight(120)
            editor.setReadOnly(readonly)
            editor.setPlaceholderText(
                "这是已交卷的作答，只能查看；要接着改请点「开始作答」。"
                if readonly
                else PLACEHOLDER_BY_DIMENSION.get(dimension, "在这里作答。写完再交卷，交卷后计时停止。")
            )
            editor.setPlainText(str(answers.get(qid, "")))
            if not readonly:
                editor.textChanged.connect(self._schedule_autosave)
            layout.addWidget(editor)

            for issue_index, issue in enumerate(grouped.get(qid) or [], start=1):
                if isinstance(issue, dict):
                    layout.addWidget(self._build_issue_card(issue_index, issue))

            self.answer_editors[qid] = editor
            self.question_layout.addWidget(card)

        self.question_layout.addStretch(1)
        self._loading_answers = False

    def _build_prior_banner(self, prior: dict[str, object]) -> QWidget:
        parts = [
            f"以下批注来自第 {int(prior['attempt_no'])} 次作答"
            f"（{float(prior['score']):g} / {float(prior['max_score']):g}"
            f"，{float(prior['percent']):g}%），挂在各自题目下方。"
        ]
        seed_no = prior.get("seed_attempt_no")
        if prior.get("stale") and seed_no is not None:
            parts.append(
                f"第 {int(seed_no)} 次作答还没评分，所以先挂着上一次的批注；"
                f"给第 {int(seed_no)} 次导入评分后，这里会换成它自己那一份。"
            )
        parts.append("「重新作答」不会带这些批注；交卷并导入新评分后会换成新的一份。")
        label = QLabel("".join(parts))
        label.setObjectName("Muted")
        label.setWordWrap(True)
        return label

    def _collect_answers(self) -> dict[str, str]:
        return {qid: editor.toPlainText().strip() for qid, editor in self.answer_editors.items()}

    def _schedule_autosave(self) -> None:
        if self._loading_answers or self.attempt_id is None:
            return
        self.autosave_timer.start()

    def _autosave_answers(self) -> None:
        if self.attempt_id is None:
            return
        self.service.studio.save_answers(self.attempt_id, self._collect_answers())

    def _start_attempt(self, inherit: bool = True) -> None:
        """开始作答（inherit=True 继承历史答案）／重新作答（inherit=False 从空白开始）。"""
        if self.paper_id is None:
            return
        self.autosave_timer.stop()
        attempt = self.service.studio.start_attempt(self.paper_id, inherit=inherit)
        self.attempt_id = int(attempt["id"])
        self._load_paper()
        self.scroll.verticalScrollBar().setValue(0)

        carried = sum(
            1 for value in dict(attempt.get("answers", {})).values() if str(value).strip()
        )
        if not inherit:
            self.action_hint.setText("已从空白开始，这次不带上一次写过的答案。")
        elif carried:
            self.action_hint.setText(f"已把上一次的 {carried} 题答案带过来了，可以直接在上面改。")
        else:
            self.action_hint.setText("这张试卷没有可继承的历史作答，这次从空白开始。")

    def _submit_attempt(self) -> None:
        """「交卷」按钮：先确认再落盘。"""
        if self.attempt_id is None:
            QMessageBox.information(self, "还没有开始作答", "先点「开始作答」，计时才会开始。")
            return
        attempt = self.service.studio.get_attempt(self.attempt_id)
        if attempt is None:
            return
        if str(attempt["status"]) != ATTEMPT_OPEN:
            QMessageBox.information(self, "这次已经交卷", "要重新作答请点「重新作答」，那会新建一次计时。")
            return

        answered = sum(1 for value in self._collect_answers().values() if value)
        total = len(self.answer_editors)
        reply = QMessageBox.question(
            self,
            "确认交卷",
            f"本卷共 {total} 题，已作答 {answered} 题。\n交卷后计时停止，标准答案解锁。\n\n确认交卷？",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.Cancel,
            QMessageBox.StandardButton.Cancel,
        )
        if reply != QMessageBox.StandardButton.Yes:
            return
        self._submit_now()

    def _submit_now(self) -> None:
        """真正落盘交卷，不再问第二遍 —— 「取消作答」里选交卷也走这里。"""
        if self.attempt_id is None:
            return
        self.autosave_timer.stop()
        submitted = self.service.studio.submit_attempt(self.attempt_id, self._collect_answers())
        self._load_paper()
        QMessageBox.information(
            self, "已交卷",
            f"用时 {format_duration(int(submitted['duration_seconds']))}。\n"
            "现在可以「导出给 AI 评分」，或先「查看标准答案」自查。",
        )

    def _cancel_attempt(self) -> None:
        """取消作答：一字未写就直接作废不交卷；写了东西则问要不要交卷。"""
        if self.attempt_id is None:
            QMessageBox.information(self, "没有进行中的作答", "先点「开始作答」。")
            return
        attempt = self.service.studio.get_attempt(self.attempt_id)
        if attempt is None or str(attempt["status"]) != ATTEMPT_OPEN:
            QMessageBox.information(self, "没有进行中的作答", "这次已经交卷了，不用取消。")
            return

        self.autosave_timer.stop()
        if answers_are_blank(self._collect_answers()):
            self.service.studio.discard_attempt(self.attempt_id)
            self.attempt_id = None
            self._load_paper()
            QMessageBox.information(
                self, "已取消作答", "这次一个字都没写，已直接作废，没有交卷。"
            )
            return

        box = QMessageBox(self)
        box.setWindowTitle("取消作答")
        box.setIcon(QMessageBox.Icon.Question)
        box.setText("这次作答已经写了内容。")
        box.setInformativeText(
            "交卷：停止计时并解锁标准答案。\n"
            "放弃本次作答：连同这次写的内容一起删掉，回到上一次记录。"
        )
        submit_button = box.addButton("交卷", QMessageBox.ButtonRole.AcceptRole)
        discard_button = box.addButton("放弃本次作答", QMessageBox.ButtonRole.DestructiveRole)
        keep_button = box.addButton("继续作答", QMessageBox.ButtonRole.RejectRole)
        box.setDefaultButton(keep_button)
        box.exec()

        clicked = box.clickedButton()
        if clicked is submit_button:
            self._submit_now()
        elif clicked is discard_button:
            self.service.studio.discard_attempt(self.attempt_id)
            self.attempt_id = None
            self._load_paper()
            QMessageBox.information(self, "已放弃本次作答", "这次作答已删除，回到上一次记录。")

    def _tick(self) -> None:
        if self.attempt_id is None:
            self.timer_label.setText("00:00")
            return
        attempt = self.service.studio.get_attempt(self.attempt_id)
        if attempt is None:
            self.timer_label.setText("00:00")
            return

        if str(attempt["status"]) == ATTEMPT_OPEN:
            elapsed = self.service.studio.elapsed_seconds(self.attempt_id)
            self.timer_label.setText(format_duration(elapsed))
            self.timer_label.setProperty("status", "info")
            limit_note = ""
            if self.paper_id is not None:
                paper_row = self.service.studio.get_paper(self.paper_id)
                payload = paper_row.get("paper", {}) if paper_row else {}
                limit = int(payload.get("time_limit_minutes", 0) or 0) if isinstance(payload, dict) else 0
                if limit:
                    limit_seconds = limit * 60
                    remain = limit_seconds - elapsed
                    if remain >= 0:
                        limit_note = f" · 限时 {limit} 分钟，剩余 {format_duration(remain)}"
                    else:
                        limit_note = f" · 已超时 {format_duration(-remain)}"
                        self.timer_label.setProperty("status", "fail")
            self.timer_note.setText(f"作答进行中{limit_note}")
            repolish(self.timer_label)
        else:
            self.timer_label.setText(format_duration(int(attempt["duration_seconds"])))
            self.timer_label.setProperty("status", "pass")
            repolish(self.timer_label)
            self.timer_note.setText(
                f"已交卷 · {attempt.get('submitted_at') or '-'}"
                f" · 第 {int(attempt['attempt_no'])} 次作答"
            )

    def _sync_buttons(self) -> None:
        has_paper = self.paper_id is not None
        attempt = self.service.studio.get_attempt(self.attempt_id) if self.attempt_id else None
        is_open = bool(attempt and str(attempt["status"]) == ATTEMPT_OPEN)
        is_submitted = bool(attempt and str(attempt["status"]) in {ATTEMPT_SUBMITTED, ATTEMPT_GRADED})
        graded = bool(attempt and str(attempt["status"]) == ATTEMPT_GRADED)

        self.delete_btn.setEnabled(has_paper)
        self.start_btn.setEnabled(has_paper and not is_open)
        self.submit_btn.setEnabled(is_open)
        self.cancel_btn.setEnabled(is_open)
        self.retry_btn.setEnabled(has_paper and is_submitted)
        self.export_review_btn.setEnabled(is_submitted)
        self.import_grade_btn.setEnabled(is_submitted)
        self.export_report_btn.setEnabled(graded)
        # 标准答案只在交卷后解锁，避免作答中直接看答案。
        self.answer_key_btn.setEnabled(is_submitted)

        if is_open:
            self.status_label.setText("状态：作答中。回答会自动保存到本地，交卷时停止计时。")
            self.action_hint.setText(
                "交卷后才能导出评分请求、导入评分和查看标准答案；想退出这次作答点「取消作答」。"
            )
        elif graded:
            self.status_label.setText("状态：已交卷并已评分。可以导出精简报告，或重新作答一次对比。")
            self.action_hint.setText("「开始作答」会带上这次的答案继续写，「重新作答」才是从空白开始。")
        elif is_submitted:
            self.status_label.setText("状态：已交卷，等待评分。导出评分请求交给 AI，再把返回的 JSON 粘回来。")
            self.action_hint.setText("「开始作答」会带上这次的答案继续写，「重新作答」才是从空白开始。")
        elif has_paper:
            self.status_label.setText("状态：未开始。点「开始作答」启动计时。")
            self.action_hint.setText("「开始作答」会带上上一次写过的答案；没有任何历史时才从空白开始。")
        else:
            self.status_label.setText("")
            self.action_hint.setText("")

        if is_open and not self.clock.isActive():
            self.clock.start()
        elif not is_open and self.clock.isActive():
            self.clock.stop()

    # ------------------------------------------------------------- 评分与导出

    def _render_grade(self) -> None:
        while self.issue_layout.count():
            item = self.issue_layout.takeAt(0)
            widget = item.widget()
            if widget is not None:
                widget.deleteLater()

        if self.attempt_id is None:
            self.grade_card.setVisible(False)
            return
        grade = self.service.studio.get_grade(self.attempt_id)
        if grade is None:
            self.grade_card.setVisible(False)
            return

        self.grade_card.setVisible(True)
        passed = float(grade["percent"]) >= 80.0
        self.grade_banner.setText(
            f"{float(grade['score']):g} / {float(grade['max_score']):g}"
            f" · {float(grade['percent']):g}%"
            f" · {'掌握' if passed else '未达标（<80%）'}"
        )
        self.grade_banner.setProperty("status", "pass" if passed else "fail")
        repolish(self.grade_banner)

        self.grade_summary.setText(str(grade.get("summary", "")))

        scores = grade.get("scores", {})
        per_question = scores.get("per_question", {}) if isinstance(scores, dict) else {}
        per_question = per_question if isinstance(per_question, dict) else {}
        if per_question:
            parts = [f"{qid} {float(value):g}" for qid, value in per_question.items()]
            self.score_line.setText("逐题得分：" + " · ".join(parts))
        else:
            self.score_line.setText("这份评分没有给出逐题得分。")

        issues = grade.get("issues", [])
        issues = issues if isinstance(issues, list) else []
        if not issues:
            empty = QLabel("没有错题。")
            empty.setObjectName("Muted")
            self.issue_layout.addWidget(empty)
            return

        for index, issue in enumerate(issues, start=1):
            if not isinstance(issue, dict):
                continue
            self.issue_layout.addWidget(self._build_issue_card(index, issue))

    def _build_issue_card(self, index: int, issue: dict) -> QWidget:
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

        if issue.get("question_id"):
            badge = QLabel(str(issue["question_id"]).upper())
            badge.setObjectName("IssueTaskBadge")
            header.addWidget(badge, 0, Qt.AlignmentFlag.AlignTop)

        if issue.get("dimension"):
            dimension = str(issue["dimension"])
            dbadge = QLabel(DIMENSION_ZH.get(dimension, dimension))
            dbadge.setObjectName("IssueDimensionBadge")
            header.addWidget(dbadge, 0, Qt.AlignmentFlag.AlignTop)

        title = QLabel(str(issue.get("title") or "需要修正"))
        title.setObjectName("IssueTitle")
        title.setWordWrap(True)
        header.addWidget(title, 1)
        layout.addLayout(header)

        blocks = [
            ("错在哪", issue.get("detail")),
            ("标准答案", issue.get("standard_answer")),
            ("差距", issue.get("learner_gap")),
            ("应改成", issue.get("correction")),
        ]
        for label_text, value in blocks:
            text = str(value or "").strip()
            if not text:
                continue
            block = QLabel(f"{label_text}：{text}")
            block.setObjectName("IssueDetail")
            block.setWordWrap(True)
            block.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
            layout.addWidget(block)
        return card

    def _export_text(self, text: str, filename: str) -> None:
        STUDIO_EXPORT_DIR.mkdir(parents=True, exist_ok=True)
        target = STUDIO_EXPORT_DIR / filename
        target.write_text(text, encoding="utf-8")
        QGuiApplication.clipboard().setText(text)
        QMessageBox.information(
            self, "已导出",
            f"已写入：\n{target}\n\n内容同时已复制到剪贴板，可以直接粘给 AI。",
        )

    def _export_review_request(self) -> None:
        if self.paper_id is None or self.attempt_id is None:
            return
        try:
            text = self.service.studio.build_review_request(self.paper_id, self.attempt_id)
        except PaperStudioError as exc:
            QMessageBox.critical(self, "无法导出", str(exc))
            return
        paper = self.service.studio.get_paper(self.paper_id)
        attempt = self.service.studio.get_attempt(self.attempt_id)
        code = str(paper["paper_code"]) if paper else "paper"
        no = int(attempt["attempt_no"]) if attempt else 0
        self._export_text(text, f"{code}_第{no}次_{self._stamp()}_评分请求.md")

    def _import_grade(self) -> None:
        if self.attempt_id is None:
            QMessageBox.information(self, "没有可评分的作答", "先作答并交卷，再导入评分。")
            return
        dialog = JsonPasteDialog("粘贴评分", self)
        if dialog.exec() != QDialog.DialogCode.Accepted:
            return
        try:
            data = loads_lenient(dialog.editor.toPlainText())
            grade = self.service.studio.import_grade(self.attempt_id, data)
        except (json.JSONDecodeError, ValueError) as exc:
            QMessageBox.critical(self, "评分 JSON 无效", str(exc))
            return
        except PaperStudioError as exc:
            QMessageBox.critical(self, "评分格式不正确", str(exc))
            return

        self._load_paper()
        issues = grade.get("issues", [])
        count = len(issues) if isinstance(issues, list) else 0
        QMessageBox.information(
            self, "评分已导入",
            f"{float(grade['score']):g} / {float(grade['max_score']):g}"
            f"（{float(grade['percent']):g}%）· 错题 {count} 项",
        )

    def _show_answer_key(self) -> None:
        if self.paper_id is None:
            return
        attempt = self.service.studio.get_attempt(self.attempt_id) if self.attempt_id else None
        if attempt is None or str(attempt["status"]) == ATTEMPT_OPEN:
            QMessageBox.information(self, "交卷后解锁", "标准答案在交卷后才允许查看，避免一边作答一边对答案。")
            return
        try:
            text = self.service.studio.build_answer_key(self.paper_id)
        except PaperStudioError as exc:
            QMessageBox.critical(self, "无法生成标准答案", str(exc))
            return

        TextViewDialog("标准答案", text, self).exec()

    def _export_report(self) -> None:
        if self.attempt_id is None:
            return
        try:
            text = self.service.studio.build_report(self.attempt_id)
        except PaperStudioError as exc:
            QMessageBox.critical(self, "无法导出报告", str(exc))
            return
        paper = self.service.studio.get_paper(self.paper_id) if self.paper_id else None
        attempt = self.service.studio.get_attempt(self.attempt_id)
        code = str(paper["paper_code"]) if paper else "paper"
        no = int(attempt["attempt_no"]) if attempt else 0
        self._export_text(text, f"{code}_第{no}次_{self._stamp()}_评分报告.md")

    @staticmethod
    def _stamp() -> str:
        return datetime.now().strftime("%Y%m%d-%H%M%S")

    def has_open_attempt(self) -> bool:
        """供 MainWindow 在关闭前判断是否需要提醒“计时仍在进行”。"""
        if self.paper_id is None:
            return False
        return self.service.studio.open_attempt(self.paper_id) is not None
