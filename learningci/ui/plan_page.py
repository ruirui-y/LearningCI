from __future__ import annotations

from PyQt6.QtWidgets import QAbstractItemView, QLabel, QTableWidget, QTableWidgetItem, QVBoxLayout, QWidget


class PlanPage(QWidget):
    def __init__(self, service, parent=None):
        super().__init__(parent)
        self.service = service
        layout = QVBoxLayout(self)
        layout.setContentsMargins(24, 20, 24, 24)
        title = QLabel("Frozen Plan")
        title.setObjectName("PageTitle")
        sub = QLabel("只读。CORE 主线按顺序推进；OPTIONAL 节点不会阻塞主线，也不能在普通学习日临时激活。")
        sub.setObjectName("PageSub")
        sub.setWordWrap(True)
        layout.addWidget(title)
        layout.addWidget(sub)
        self.table = QTableWidget(0, 8)
        self.table.setHorizontalHeaderLabels(["Order", "Node", "Stage", "Priority", "Title", "Status", "Current", "Stable"])
        self.table.horizontalHeader().setStretchLastSection(True)
        self.table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        layout.addWidget(self.table, 1)
        self.refresh()

    def refresh(self) -> None:
        nodes = self.service.list_nodes()
        self.table.setRowCount(len(nodes))
        for r, node in enumerate(nodes):
            values = [
                node["order_index"], node["node_code"], node["stage"], node["priority"], node["title"], node["status"],
                "-" if node["current_score"] is None else node["current_score"],
                "-" if node["stable_score"] is None else node["stable_score"],
            ]
            for c, value in enumerate(values):
                self.table.setItem(r, c, QTableWidgetItem(str(value)))
        self.table.resizeColumnsToContents()
