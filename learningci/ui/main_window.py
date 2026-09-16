from __future__ import annotations

from PyQt6.QtWidgets import (
    QFrame, QHBoxLayout, QLabel, QMainWindow, QMessageBox, QPushButton,
    QStackedWidget, QVBoxLayout, QWidget
)

from learningci.ui.data_sync_page import DataSyncPage
from learningci.ui.history_page import HistoryPage
from learningci.ui.parking_page import ParkingPage
from learningci.ui.plan_page import PlanPage
from learningci.ui.node_prepare_page import NodePreparePage
from learningci.ui.reviews_page import ReviewsPage
from learningci.ui.today_page import TodayPage


class MainWindow(QMainWindow):
    def __init__(self, service, parent=None):
        super().__init__(parent)
        self.service = service
        self.setWindowTitle("LearningCI")
        self.resize(1440, 900)
        self.setMinimumSize(1180, 760)
        self.nav_buttons: list[QPushButton] = []
        self.pages: list[QWidget] = []
        self._build_ui()

    def _build_ui(self) -> None:
        central = QWidget()
        self.setCentralWidget(central)
        root = QHBoxLayout(central)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)

        sidebar = QFrame()
        sidebar.setObjectName("Sidebar")
        sidebar.setFixedWidth(220)
        side = QVBoxLayout(sidebar)
        side.setContentsMargins(14, 18, 14, 18)
        side.setSpacing(6)
        title = QLabel("LearningCI")
        title.setObjectName("AppTitle")
        sub = QLabel("能力验证系统 · v0.3.5")
        sub.setObjectName("AppSub")
        side.addWidget(title)
        side.addWidget(sub)
        side.addSpacing(18)

        self.stack = QStackedWidget()
        self.today = TodayPage(self.service)
        self.plan = PlanPage(self.service)
        self.prepare = NodePreparePage(self.service)
        self.reviews = ReviewsPage(self.service)
        self.history = HistoryPage(self.service)
        self.parking = ParkingPage(self.service)
        self.sync = DataSyncPage(self.service)
        self.pages = [self.today, self.plan, self.prepare, self.reviews, self.history, self.parking, self.sync]
        labels = ["今日学习", "冻结计划", "节点准备", "复测队列", "学习统计", "想法停车场", "数据同步"]
        for index, (label, page) in enumerate(zip(labels, self.pages)):
            self.stack.addWidget(page)
            btn = QPushButton(label)
            btn.setObjectName("NavButton")
            btn.setProperty("active", "true" if index == 0 else "false")
            btn.clicked.connect(lambda _checked=False, i=index: self._select_page(i))
            self.nav_buttons.append(btn)
            side.addWidget(btn)

        side.addStretch(1)
        lock = QLabel("● 路线与已冻结试卷受保护")
        lock.setProperty("status", "info")
        side.addWidget(lock)
        lock_sub = QLabel("plan.json 固定学习路线\n节点执行包仅在冻结前允许细化")
        lock_sub.setWordWrap(True)
        lock_sub.setObjectName("AppSub")
        side.addWidget(lock_sub)

        root.addWidget(sidebar)
        root.addWidget(self.stack, 1)

        self.today.data_changed.connect(self._refresh_all)
        self.sync.data_changed.connect(self._refresh_all)
        self.prepare.data_changed.connect(self._refresh_all)

    def _select_page(self, index: int) -> None:
        self.stack.setCurrentIndex(index)
        for i, btn in enumerate(self.nav_buttons):
            btn.setProperty("active", "true" if i == index else "false")
            btn.style().unpolish(btn)
            btn.style().polish(btn)
        page = self.pages[index]
        if hasattr(page, "refresh"):
            page.refresh()

    def _refresh_all(self) -> None:
        for page in self.pages:
            if hasattr(page, "refresh"):
                page.refresh()

    def closeEvent(self, event) -> None:
        self.today.save_pending_edits()
        if self.service.active_focus_session() or self.service.active_task_session():
            reply = QMessageBox.question(
                self,
                "学习计时仍在进行",
                "当前总专注或叶子任务计时尚未结束。LearningCI 不允许静默退出并继续累计时间。\n\n结束学习并退出？",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.Cancel,
                QMessageBox.StandardButton.Cancel,
            )
            if reply != QMessageBox.StandardButton.Yes:
                event.ignore()
                return
            self.service.end_focus()
        event.accept()
