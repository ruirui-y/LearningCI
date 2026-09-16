from __future__ import annotations

from datetime import datetime

from PyQt6.QtCore import QTimer, pyqtSignal
from PyQt6.QtWidgets import (
    QCheckBox, QFrame, QGridLayout, QHBoxLayout, QLabel, QMessageBox,
    QProgressBar, QPushButton, QVBoxLayout, QWidget
)

from learningci.ui.common import StatCard, format_duration, format_hours
from learningci.ui.dialogs import AssessmentDialog


class TodayPage(QWidget):
    data_changed = pyqtSignal()

    def __init__(self, service, parent=None):
        super().__init__(parent)
        self.service = service
        self.node: dict | None = None
        self.task_checks: list[QCheckBox] = []
        self.timer = QTimer(self)
        self.timer.timeout.connect(self._tick)
        self._build_ui()
        self.refresh()

    def _build_ui(self) -> None:
        root = QVBoxLayout(self)
        root.setContentsMargins(24, 20, 24, 24)
        root.setSpacing(14)

        self.title = QLabel("Today")
        self.title.setObjectName("PageTitle")
        self.subtitle = QLabel("今天只推进一个 CORE 节点。主路线不可在普通学习日修改。")
        self.subtitle.setObjectName("PageSub")
        root.addWidget(self.title)
        root.addWidget(self.subtitle)

        stats = QGridLayout()
        stats.setSpacing(10)
        self.today_focus = StatCard("今日专注", "0 min", "开始学习 → 结束学习")
        self.week_focus = StatCard("本周专注", "0.0 h", "周一开始汇总")
        self.month_focus = StatCard("本月专注", "0.0 h", "自然月汇总")
        self.task_stat = StatCard("今日任务", "0%", "最低任务完成度")
        self.score_stat = StatCard("当前能力分", "-", "Stable / Best 同时保留")
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
        self.verify_btn = QPushButton("开始 Verification")
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
        task_layout.addWidget(QLabel("今日最低验收任务"))
        self.progress = QProgressBar()
        self.progress.setRange(0, 100)
        task_layout.addWidget(self.progress)
        self.task_container = QVBoxLayout()
        task_layout.addLayout(self.task_container)
        root.addWidget(task_card, 1)

        self.start_btn.clicked.connect(self._start_learning)
        self.stop_btn.clicked.connect(self._stop_learning)
        self.verify_btn.clicked.connect(self._open_verification)

    def refresh(self) -> None:
        self.node = self.service.get_active_node()
        self._clear_tasks()
        if not self.node:
            self.node_code.setText("MAINLINE DONE")
            self.node_title.setText("当前 CORE 主线已完成")
            self.capability.setText("OPTIONAL 研究节点仍可在后续版本化计划中单独启用。")
            self.project_info.setText("")
            self.start_btn.setEnabled(False)
            self.stop_btn.setEnabled(False)
            self.verify_btn.setEnabled(False)
            return

        self.node_code.setText(f"{self.node['node_code']}  ·  Stage {self.node['stage']}  ·  {self.node['priority']}")
        self.node_title.setText(self.node["title"])
        self.capability.setText(self.node["capability"])
        anchor = self.node.get("project_anchor", {})
        paths = anchor.get("paths", [])
        if paths:
            rendered = "\n".join(f"  • NebulaRPC/{p}" for p in paths)
            self.project_info.setText(
                "目标项目产物（不是 LearningCI/docs）：\n" + rendered
            )
        else:
            self.project_info.setText("目标项目：NebulaRPC")

        for state in self.service.get_task_states(self.node["id"]):
            cb = QCheckBox(state["text"])
            cb.setChecked(state["completed"])
            cb.stateChanged.connect(lambda _v, idx=state["index"], box=cb: self._task_changed(idx, box.isChecked()))
            self.task_container.addWidget(cb)
            self.task_checks.append(cb)
        self.task_container.addStretch(1)
        self._refresh_metrics()
        self._refresh_timer_state()

    def _clear_tasks(self) -> None:
        while self.task_container.count():
            item = self.task_container.takeAt(0)
            widget = item.widget()
            if widget:
                widget.deleteLater()
        self.task_checks.clear()

    def _task_changed(self, idx: int, checked: bool) -> None:
        if not self.node:
            return
        self.service.set_task_completed(self.node["id"], idx, checked)
        self._refresh_metrics()
        self._refresh_timer_state()
        self.data_changed.emit()

    def _refresh_metrics(self) -> None:
        summary = self.service.focus_summary()
        self.today_focus.set_value(format_duration(summary["today"]))
        self.week_focus.set_value(format_hours(summary["week"]))
        self.month_focus.set_value(format_hours(summary["month"]))
        if self.node:
            done, total, pct = self.service.task_completion(self.node["id"])
            self.task_stat.set_value(f"{pct}%", f"{done}/{total} completed")
            self.progress.setValue(pct)
            current = self.node.get("current_score")
            stable = self.node.get("stable_score")
            best = self.node.get("best_score")
            hint = f"Stable {stable if stable is not None else '-'} · Best {best if best is not None else '-'}"
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
        self._refresh_timer_state()
        self._refresh_metrics()
        self.data_changed.emit()

    def _refresh_timer_state(self) -> None:
        active = self.service.active_focus_session()
        running = bool(active)
        self.start_btn.setEnabled(not running and self.node is not None)
        self.stop_btn.setEnabled(running)
        if self.node is not None:
            done, total, _pct = self.service.task_completion(self.node["id"])
            self.verify_btn.setEnabled((not running) and (total == 0 or done == total))
        else:
            self.verify_btn.setEnabled(False)
        if running:
            self.timer.start(1000)
            self._tick()
        else:
            self.timer.stop()
            self.timer_label.setText("00:00")

    def _tick(self) -> None:
        active = self.service.active_focus_session()
        if not active:
            self._refresh_timer_state()
            return
        elapsed = int((datetime.now() - datetime.fromisoformat(active["started_at"])).total_seconds())
        self.timer_label.setText(format_duration(elapsed))
        self._refresh_metrics()

    def _open_verification(self) -> None:
        if not self.node:
            return
        if self.service.active_focus_session():
            QMessageBox.warning(self, "先结束学习", "结束当前专注计时后才能进入 Verification。")
            return
        done, total, _pct = self.service.task_completion(self.node["id"])
        if total and done < total:
            QMessageBox.warning(
                self, "最低验收任务未完成",
                f"当前仅完成 {done}/{total}。LearningCI 不允许跳过冻结计划中的最低任务。",
            )
            return
        dlg = AssessmentDialog(self.service, self.node, parent=self)
        dlg.graded.connect(self._after_grade)
        dlg.exec()

    def _after_grade(self) -> None:
        self.refresh()
        self.data_changed.emit()
