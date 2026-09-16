from __future__ import annotations

from PyQt6.QtWidgets import QAbstractItemView, QLabel, QPushButton, QTableWidget, QTableWidgetItem, QVBoxLayout, QWidget

from learningci.ui.dialogs import AssessmentDialog


class ReviewsPage(QWidget):
    def __init__(self, service, parent=None):
        super().__init__(parent)
        self.service = service
        self.rows: list[dict] = []
        layout = QVBoxLayout(self)
        layout.setContentsMargins(24, 20, 24, 24)
        title = QLabel("复测队列")
        title.setObjectName("PageTitle")
        sub = QLabel("主线不回退；低分或遗忘节点通过复测队列重新出现。")
        sub.setObjectName("PageSub")
        layout.addWidget(title)
        layout.addWidget(sub)
        self.table = QTableWidget(0, 5)
        self.table.setHorizontalHeaderLabels(["到期日", "复测类型", "Node", "Title", "稳定分"])
        self.table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        layout.addWidget(self.table, 1)
        self.start_btn = QPushButton("开始选中的复测")
        self.start_btn.setObjectName("PrimaryButton")
        self.start_btn.clicked.connect(self._start_review)
        layout.addWidget(self.start_btn)
        self.refresh()

    def refresh(self) -> None:
        self.rows = self.service.due_reviews()
        self.table.setRowCount(len(self.rows))
        for r, row in enumerate(self.rows):
            vals = [row["due_date"], row["review_type"], row["node_code"], row["title"], row["stable_score"] or "-"]
            for c, v in enumerate(vals):
                self.table.setItem(r, c, QTableWidgetItem(str(v)))
        self.table.resizeColumnsToContents()
        self.start_btn.setEnabled(bool(self.rows))

    def _start_review(self) -> None:
        row = self.table.currentRow()
        if row < 0 or row >= len(self.rows):
            return
        review = self.rows[row]
        node = self.service.get_node(review["node_id"])
        dlg = AssessmentDialog(self.service, node, review=review, parent=self)
        dlg.graded.connect(self.refresh)
        dlg.exec()
        self.refresh()
