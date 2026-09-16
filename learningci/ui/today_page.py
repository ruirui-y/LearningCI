from __future__ import annotations

from datetime import datetime

from PyQt6.QtCore import Qt, QTimer, pyqtSignal
from PyQt6.QtWidgets import (
    QAbstractItemView, QFormLayout, QFrame, QGridLayout, QHBoxLayout, QLabel,
    QLineEdit, QMessageBox, QProgressBar, QPushButton, QScrollArea, QSplitter,
    QTextEdit, QTreeWidget, QTreeWidgetItem, QVBoxLayout, QWidget, QHeaderView
)

from learningci.ui.common import StatCard, format_duration, format_hours
from learningci.ui.dialogs import AssessmentDialog


class TodayPage(QWidget):
    data_changed = pyqtSignal()

    TASK_ROLE = Qt.ItemDataRole.UserRole

    def __init__(self, service, parent=None):
        super().__init__(parent)
        self.service = service
        self.node: dict | None = None
        self.selected_task_code: str | None = None
        self._refreshing_tree = False
        self.timer = QTimer(self)
        self.timer.timeout.connect(self._tick)
        self._build_ui()
        self.refresh()

    def _build_ui(self) -> None:
        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        self.scroll = QScrollArea()
        self.scroll.setWidgetResizable(True)
        self.scroll.setObjectName("TodayScroll")
        body = QWidget()
        root = QVBoxLayout(body)
        root.setContentsMargins(24, 20, 24, 28)
        root.setSpacing(14)
        self.scroll.setWidget(body)
        outer.addWidget(self.scroll)

        self.title = QLabel("今日学习")
        self.title.setObjectName("PageTitle")
        self.subtitle = QLabel("今天只推进一个主线节点。详细叶子任务逐个打卡；固定试卷从节点开始就可查看。")
        self.subtitle.setObjectName("PageSub")
        root.addWidget(self.title)
        root.addWidget(self.subtitle)

        stats = QGridLayout()
        stats.setSpacing(10)
        self.today_focus = StatCard("今日专注", "0 min", "总学习计时")
        self.week_focus = StatCard("本周专注", "0.0 h", "周一开始汇总")
        self.month_focus = StatCard("本月专注", "0.0 h", "自然月汇总")
        self.task_stat = StatCard("节点任务", "0%", "叶子任务完成度")
        self.score_stat = StatCard("当前能力分", "-", "同时保留稳定分 / 历史最高分")
        for i, card in enumerate([self.today_focus, self.week_focus, self.month_focus, self.task_stat, self.score_stat]):
            stats.addWidget(card, 0, i)
        root.addLayout(stats)

        node_card = QFrame()
        node_card.setObjectName("Card")
        node_layout = QVBoxLayout(node_card)
        node_layout.setContentsMargins(16, 14, 16, 14)
        node_layout.setSpacing(8)
        self.node_code = QLabel("-")
        self.node_code.setObjectName("Secondary")
        self.node_title = QLabel("没有节点")
        self.node_title.setObjectName("SectionTitle")
        self.capability = QLabel("")
        self.capability.setWordWrap(True)
        self.capability.setObjectName("Secondary")
        self.project_info = QLabel("")
        self.project_info.setWordWrap(True)
        self.project_info.setObjectName("ProjectPath")
        node_layout.addWidget(self.node_code)
        node_layout.addWidget(self.node_title)
        node_layout.addWidget(self.capability)
        node_layout.addWidget(self.project_info)
        root.addWidget(node_card)

        focus_row = QHBoxLayout()
        self.timer_label = QLabel("00:00")
        self.timer_label.setObjectName("FocusTimer")
        self.start_btn = QPushButton("开始学习")
        self.start_btn.setObjectName("SuccessButton")
        self.stop_btn = QPushButton("结束学习")
        self.stop_btn.setObjectName("DangerButton")
        self.verify_btn = QPushButton("进入正式测试")
        self.verify_btn.setObjectName("PrimaryButton")
        focus_row.addWidget(self.timer_label)
        focus_row.addStretch(1)
        focus_row.addWidget(self.start_btn)
        focus_row.addWidget(self.stop_btn)
        focus_row.addWidget(self.verify_btn)
        root.addLayout(focus_row)

        task_card = QFrame()
        task_card.setObjectName("Card")
        task_layout = QVBoxLayout(task_card)
        task_layout.setContentsMargins(16, 14, 16, 14)
        task_layout.setSpacing(10)
        task_head = QHBoxLayout()
        task_title = QLabel("详细执行清单")
        task_title.setObjectName("SectionTitle")
        self.task_count_label = QLabel("")
        self.task_count_label.setObjectName("Secondary")
        task_head.addWidget(task_title)
        task_head.addStretch(1)
        task_head.addWidget(self.task_count_label)
        task_layout.addLayout(task_head)
        self.progress = QProgressBar()
        self.progress.setRange(0, 100)
        task_layout.addWidget(self.progress)

        splitter = QSplitter(Qt.Orientation.Horizontal)
        splitter.setObjectName("TaskSplitter")
        self.task_tree = QTreeWidget()
        self.task_tree.setObjectName("TaskTree")
        self.task_tree.setColumnCount(3)
        self.task_tree.setHeaderLabels(["任务", "状态", "累计"])
        self.task_tree.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        self.task_tree.setAlternatingRowColors(False)
        self.task_tree.header().setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
        self.task_tree.header().setSectionResizeMode(1, QHeaderView.ResizeMode.ResizeToContents)
        self.task_tree.header().setSectionResizeMode(2, QHeaderView.ResizeMode.ResizeToContents)
        self.task_tree.itemSelectionChanged.connect(self._task_selected)
        self.task_tree.itemChanged.connect(self._task_item_changed)
        splitter.addWidget(self.task_tree)

        detail = QFrame()
        detail.setObjectName("TaskDetailCard")
        detail_layout = QVBoxLayout(detail)
        detail_layout.setContentsMargins(14, 12, 14, 12)
        detail_layout.setSpacing(8)
        self.detail_title = QLabel("选择左侧叶子任务查看细节")
        self.detail_title.setObjectName("SectionTitle")
        self.detail_title.setWordWrap(True)
        self.detail_purpose = QLabel("")
        self.detail_purpose.setObjectName("Secondary")
        self.detail_purpose.setWordWrap(True)
        self.detail_text = QLabel("")
        self.detail_text.setWordWrap(True)
        self.done_when = QLabel("")
        self.done_when.setWordWrap(True)
        self.done_when.setObjectName("TaskCriteria")
        detail_layout.addWidget(self.detail_title)
        detail_layout.addWidget(self.detail_purpose)
        detail_layout.addWidget(self.detail_text)
        detail_layout.addWidget(self.done_when)

        form = QFormLayout()
        self.source_path_edit = QLineEdit()
        self.source_path_edit.setPlaceholderText("例如 muduo/net/TcpConnection.cc")
        self.function_edit = QLineEdit()
        self.function_edit.setPlaceholderText("例如 TcpConnection::sendInLoop")
        self.evidence_note_edit = QTextEdit()
        self.evidence_note_edit.setMinimumHeight(80)
        self.evidence_note_edit.setPlaceholderText("git grep / IDE 调用链 / 测试结果 / 观察结论等")
        form.addRow("源码/产物路径", self.source_path_edit)
        form.addRow("函数/入口", self.function_edit)
        form.addRow("证据备注", self.evidence_note_edit)
        detail_layout.addLayout(form)

        task_timer_row = QHBoxLayout()
        self.task_timer_label = QLabel("任务累计 00:00")
        self.task_timer_label.setObjectName("TaskTimer")
        self.task_start_btn = QPushButton("开始此任务")
        self.task_start_btn.setObjectName("SuccessButton")
        self.task_stop_btn = QPushButton("暂停此任务")
        self.task_stop_btn.setObjectName("DangerButton")
        self.save_evidence_btn = QPushButton("保存证据")
        self.save_evidence_btn.setObjectName("SecondaryButton")
        self.complete_task_btn = QPushButton("完成打卡")
        self.complete_task_btn.setObjectName("PrimaryButton")
        task_timer_row.addWidget(self.task_timer_label)
        task_timer_row.addStretch(1)
        task_timer_row.addWidget(self.task_start_btn)
        task_timer_row.addWidget(self.task_stop_btn)
        task_timer_row.addWidget(self.save_evidence_btn)
        task_timer_row.addWidget(self.complete_task_btn)
        detail_layout.addLayout(task_timer_row)
        detail_layout.addStretch(1)
        splitter.addWidget(detail)
        splitter.setSizes([620, 520])
        task_layout.addWidget(splitter)
        root.addWidget(task_card)

        paper_card = QFrame()
        paper_card.setObjectName("Card")
        paper_layout = QVBoxLayout(paper_card)
        paper_layout.setContentsMargins(16, 14, 16, 14)
        paper_layout.setSpacing(8)
        paper_head = QHBoxLayout()
        paper_title = QLabel("固定试卷预览")
        paper_title.setObjectName("SectionTitle")
        self.paper_meta = QLabel("")
        self.paper_meta.setObjectName("ProjectPath")
        paper_head.addWidget(paper_title)
        paper_head.addStretch(1)
        paper_head.addWidget(self.paper_meta)
        paper_layout.addLayout(paper_head)
        paper_note = QLabel("试卷从节点开始就固定可见，用来明确通关目标；所有必做叶子任务完成后才允许正式提交。首次未通过后仍使用同一张试卷。")
        paper_note.setObjectName("Muted")
        paper_note.setWordWrap(True)
        paper_layout.addWidget(paper_note)
        self.paper_tree = QTreeWidget()
        self.paper_tree.setObjectName("PaperPreviewTree")
        self.paper_tree.setHeaderHidden(True)
        self.paper_tree.setMinimumHeight(230)
        paper_layout.addWidget(self.paper_tree)
        root.addWidget(paper_card)
        root.addStretch(1)

        self.start_btn.clicked.connect(self._start_learning)
        self.stop_btn.clicked.connect(self._stop_learning)
        self.verify_btn.clicked.connect(self._open_verification)
        self.task_start_btn.clicked.connect(self._start_task)
        self.task_stop_btn.clicked.connect(self._stop_task)
        self.save_evidence_btn.clicked.connect(self._save_evidence)
        self.complete_task_btn.clicked.connect(self._toggle_selected_complete)

    def refresh(self) -> None:
        prev_task = self.selected_task_code
        self.node = self.service.get_active_node()
        self.selected_task_code = None
        self.task_tree.clear()
        self.paper_tree.clear()
        if not self.node:
            self.node_code.setText("主线完成")
            self.node_title.setText("当前 CORE 主线已完成")
            self.capability.setText("可选研究节点可以在主线完成后单独启用。")
            self.project_info.setText("")
            for btn in [self.start_btn, self.stop_btn, self.verify_btn, self.task_start_btn, self.task_stop_btn, self.save_evidence_btn, self.complete_task_btn]:
                btn.setEnabled(False)
            return

        self.node_code.setText(f"{self.node['node_code']}  ·  Stage {self.node['stage']}  ·  {self.node['priority']}")
        self.node_title.setText(self.node["title"])
        self.capability.setText(self.node["capability"])
        anchor = self.node.get("project_anchor", {})
        paths = anchor.get("paths", [])
        if paths:
            rendered = "\n".join(f"  • NebulaRPC/{p}" for p in paths)
            self.project_info.setText("目标项目产物（不是 LearningCI/docs）：\n" + rendered)
        else:
            self.project_info.setText("目标项目：NebulaRPC")

        if self.node.get("bundle_state") != "FROZEN":
            self.project_info.setText(
                self.project_info.text() +
                "\n\n⚠ 当前 Node 的节点执行包仍是草稿。请先到左侧‘节点准备’导出细化包，"
                "让 ChatGPT 细化后导回。LearningCI 不会用粗粒度草稿开始正式学习。"
            )
            notice = QTreeWidgetItem(["当前节点尚未准备完成", "待细化", "-"])
            self.task_tree.addTopLevelItem(notice)
            self.paper_meta.setText("等待节点细化")
            self.paper_tree.addTopLevelItem(QTreeWidgetItem(["细化完成并到达主线后，这里会显示冻结的首次固定试卷。"]))
            self._refresh_metrics()
            self.start_btn.setEnabled(False)
            self.stop_btn.setEnabled(False)
            self.verify_btn.setEnabled(False)
            for btn in [self.task_start_btn, self.task_stop_btn, self.save_evidence_btn, self.complete_task_btn]:
                btn.setEnabled(False)
            return

        self._populate_task_tree(prev_task)
        self._populate_paper_preview()
        self._refresh_metrics()
        self._refresh_timer_state()

    def _populate_task_tree(self, preferred_task: str | None = None) -> None:
        if not self.node:
            return
        self._refreshing_tree = True
        self.task_tree.clear()
        tree = self.service.get_leaf_task_tree(self.node["id"])
        first_leaf = None
        preferred_item = None
        for gi, group in enumerate(tree):
            done = sum(1 for x in group["items"] if x.get("completed"))
            total = len(group["items"])
            parent = QTreeWidgetItem([group["title"], f"{done}/{total}", ""])
            parent.setFlags(parent.flags() & ~Qt.ItemFlag.ItemIsUserCheckable)
            parent.setData(0, self.TASK_ROLE, None)
            self.task_tree.addTopLevelItem(parent)
            parent.setExpanded(gi == 0 or (done and done < total))
            for task in group["items"]:
                status = "进行中" if task.get("in_progress") else ("完成" if task.get("completed") else "待办")
                item = QTreeWidgetItem([task["title"], status, format_duration(int(task.get("total_seconds", 0)))])
                item.setFlags(item.flags() | Qt.ItemFlag.ItemIsUserCheckable)
                item.setCheckState(0, Qt.CheckState.Checked if task.get("completed") else Qt.CheckState.Unchecked)
                item.setData(0, self.TASK_ROLE, task["id"])
                parent.addChild(item)
                if first_leaf is None:
                    first_leaf = item
                if preferred_task and task["id"] == preferred_task:
                    preferred_item = item
        self._refreshing_tree = False
        target = preferred_item or first_leaf
        if target:
            self.task_tree.setCurrentItem(target)
            self.selected_task_code = target.data(0, self.TASK_ROLE)
            self._load_task_detail(self.selected_task_code)

    def _task_selected(self) -> None:
        items = self.task_tree.selectedItems()
        if not items:
            return
        code = items[0].data(0, self.TASK_ROLE)
        if not code:
            return
        self.selected_task_code = str(code)
        self._load_task_detail(self.selected_task_code)

    def _task_item_changed(self, item: QTreeWidgetItem, column: int) -> None:
        if self._refreshing_tree or not self.node:
            return
        code = item.data(0, self.TASK_ROLE)
        if not code:
            return
        checked = item.checkState(0) == Qt.CheckState.Checked
        try:
            self.service.set_leaf_task_completed(self.node["id"], str(code), checked)
        except Exception as exc:
            QMessageBox.warning(self, "任务尚不能完成", str(exc))
            self._populate_task_tree(str(code))
            return
        self._populate_task_tree(str(code))
        self._refresh_metrics()
        self._refresh_timer_state()
        self.data_changed.emit()

    def _load_task_detail(self, task_code: str) -> None:
        if not self.node:
            return
        task = self.service.get_leaf_task(self.node["id"], task_code)
        self.detail_title.setText(task.get("title", task_code))
        self.detail_purpose.setText(f"目的：{task.get('purpose', '')}")
        estimate = int(task.get("estimated_minutes", 0) or 0)
        self.detail_text.setText(f"操作：{task.get('detail', '')}\n预计：{estimate} min")
        criteria = "\n".join(f"□ {x}" for x in task.get("done_when", []))
        self.done_when.setText("完成标准：\n" + criteria)
        self.source_path_edit.setText(str(task.get("source_path", "") or ""))
        self.function_edit.setText(str(task.get("function_name", "") or ""))
        self.evidence_note_edit.setPlainText(str(task.get("evidence_note", "") or ""))
        self.task_timer_label.setText(f"任务累计 {format_duration(int(task.get('total_seconds', 0) or 0))}")
        self.complete_task_btn.setText("取消完成" if bool(task.get("completed")) else "完成打卡")
        self._refresh_task_buttons()

    def _save_evidence(self, silent: bool = False) -> None:
        if not self.node or not self.selected_task_code:
            return
        self.service.save_leaf_task_evidence(
            self.node["id"], self.selected_task_code,
            self.source_path_edit.text(), self.function_edit.text(), self.evidence_note_edit.toPlainText(),
        )
        if not silent:
            QMessageBox.information(self, "证据已保存", "当前叶子任务的路径、函数和备注已保存到 SQLite。")

    def _toggle_selected_complete(self) -> None:
        if not self.node or not self.selected_task_code:
            return
        self._save_evidence(silent=True)
        task = self.service.get_leaf_task(self.node["id"], self.selected_task_code)
        try:
            self.service.set_leaf_task_completed(self.node["id"], self.selected_task_code, not bool(task.get("completed")))
        except Exception as exc:
            QMessageBox.warning(self, "任务尚不能完成", str(exc))
            return
        self._populate_task_tree(self.selected_task_code)
        self._refresh_metrics()
        self._refresh_timer_state()
        self.data_changed.emit()

    def _start_task(self) -> None:
        if not self.node or not self.selected_task_code:
            return
        self._save_evidence(silent=True)
        self.service.start_task_focus(self.node["id"], self.selected_task_code)
        self._populate_task_tree(self.selected_task_code)
        self._refresh_timer_state()
        self.data_changed.emit()

    def _stop_task(self) -> None:
        self.service.end_task_focus()
        self._populate_task_tree(self.selected_task_code)
        self._refresh_timer_state()
        self._refresh_metrics()
        self.data_changed.emit()

    def _populate_paper_preview(self) -> None:
        if not self.node:
            return
        paper = self.service.get_frozen_verification_paper(self.node["id"])
        self.paper_meta.setText(f"{paper.get('_paper_code', paper.get('paper_id', 'V1'))} · 100 分")
        self.paper_tree.clear()
        for idx, q in enumerate(paper.get("questions", []), start=1):
            head = QTreeWidgetItem([f"Q{idx} · {str(q.get('dimension','')).upper()} · {q.get('max_score')} 分"])
            detail = QTreeWidgetItem([str(q.get("question", ""))])
            detail.setFlags(detail.flags() & ~Qt.ItemFlag.ItemIsSelectable)
            head.addChild(detail)
            self.paper_tree.addTopLevelItem(head)
            head.setExpanded(idx == 1)

    def _refresh_metrics(self) -> None:
        summary = self.service.focus_summary()
        self.today_focus.set_value(format_duration(summary["today"]))
        self.week_focus.set_value(format_hours(summary["week"]))
        self.month_focus.set_value(format_hours(summary["month"]))
        if self.node:
            done, total, pct = self.service.task_completion(self.node["id"])
            self.task_stat.set_value(f"{pct}%", f"必做任务 {done}/{total}")
            self.task_count_label.setText(f"必做任务 {done} / {total}")
            self.progress.setValue(pct)
            current = self.node.get("current_score")
            stable = self.node.get("stable_score")
            best = self.node.get("best_score")
            hint = f"稳定分 {stable if stable is not None else '-'} · 最高分 {best if best is not None else '-'}"
            self.score_stat.set_value("-" if current is None else str(current), hint)

    def _start_learning(self) -> None:
        if not self.node:
            return
        self.service.start_focus(self.node["id"])
        self._refresh_timer_state()
        self.data_changed.emit()

    def _stop_learning(self) -> None:
        seconds = self.service.end_focus()
        if seconds <= 0:
            QMessageBox.information(self, "没有进行中的学习", "当前没有活动专注计时。")
        self._populate_task_tree(self.selected_task_code)
        self._refresh_timer_state()
        self._refresh_metrics()
        self.data_changed.emit()

    def _refresh_task_buttons(self) -> None:
        active = self.service.active_task_session()
        has_task = bool(self.selected_task_code and self.node)
        selected_running = bool(active and has_task and active["node_id"] == self.node["id"] and active["task_code"] == self.selected_task_code)
        self.task_start_btn.setEnabled(has_task and not selected_running)
        self.task_stop_btn.setEnabled(selected_running)
        self.save_evidence_btn.setEnabled(has_task)
        self.complete_task_btn.setEnabled(has_task and not selected_running)

    def _refresh_timer_state(self) -> None:
        active = self.service.active_focus_session()
        running = bool(active)
        self.start_btn.setEnabled(not running and self.node is not None)
        self.stop_btn.setEnabled(running)
        if self.node is not None:
            done, total, _pct = self.service.task_completion(self.node["id"])
            self.verify_btn.setEnabled((not running) and (not self.service.active_task_session()) and (total == 0 or done == total))
        else:
            self.verify_btn.setEnabled(False)
        if running or self.service.active_task_session():
            self.timer.start(1000)
            self._tick()
        else:
            self.timer.stop()
            self.timer_label.setText("00:00")
        self._refresh_task_buttons()

    def _tick(self) -> None:
        active = self.service.active_focus_session()
        if active:
            elapsed = int((datetime.now() - datetime.fromisoformat(active["started_at"])).total_seconds())
            self.timer_label.setText(format_duration(elapsed))
        else:
            self.timer_label.setText("00:00")
        active_task = self.service.active_task_session()
        if active_task and self.node and self.selected_task_code == active_task["task_code"]:
            base = self.service.get_leaf_task(self.node["id"], self.selected_task_code).get("total_seconds", 0) or 0
            elapsed = int((datetime.now() - datetime.fromisoformat(active_task["started_at"])).total_seconds())
            self.task_timer_label.setText(f"任务累计 {format_duration(int(base) + max(0, elapsed))}")
        self._refresh_metrics()

    def _open_verification(self) -> None:
        if not self.node:
            return
        if self.service.active_focus_session() or self.service.active_task_session():
            QMessageBox.warning(self, "先结束学习", "结束当前专注/叶子任务计时后才能进入正式测试。")
            return
        done, total, _pct = self.service.task_completion(self.node["id"])
        if total and done < total:
            QMessageBox.warning(
                self, "详细验收任务未完成",
                f"当前仅完成 {done}/{total} 个必做叶子任务。固定试卷可以提前查看，但不能提前提交。",
            )
            return
        dlg = AssessmentDialog(self.service, self.node, parent=self)
        dlg.graded.connect(self._after_grade)
        dlg.exec()

    def _after_grade(self) -> None:
        self.refresh()
        self.data_changed.emit()
