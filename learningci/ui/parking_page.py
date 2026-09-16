from __future__ import annotations

from PyQt6.QtWidgets import QAbstractItemView, QHBoxLayout, QLabel, QLineEdit, QPushButton, QTableWidget, QTableWidgetItem, QVBoxLayout, QWidget


class ParkingPage(QWidget):
    def __init__(self, service, parent=None):
        super().__init__(parent)
        self.service = service
        layout = QVBoxLayout(self)
        layout.setContentsMargins(24, 20, 24, 24)
        title = QLabel("Parking Lot")
        title.setObjectName("PageTitle")
        sub = QLabel("想到更短路线、新技术、别的项目时只记录，不在今天处理。")
        sub.setObjectName("PageSub")
        layout.addWidget(title)
        layout.addWidget(sub)
        row = QHBoxLayout()
        self.input = QLineEdit()
        self.input.setPlaceholderText("例如：以后比较 io_uring 与 epoll；今天不切换")
        add_btn = QPushButton("记录")
        add_btn.setObjectName("PrimaryButton")
        add_btn.clicked.connect(self._add)
        row.addWidget(self.input, 1)
        row.addWidget(add_btn)
        layout.addLayout(row)
        self.table = QTableWidget(0, 4)
        self.table.setHorizontalHeaderLabels(["Time", "Source Node", "Content", "Status"])
        self.table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.table.horizontalHeader().setStretchLastSection(True)
        layout.addWidget(self.table, 1)
        self.refresh()

    def _add(self) -> None:
        node = self.service.get_active_node()
        self.service.add_parking_item(self.input.text(), node["id"] if node else None)
        self.input.clear()
        self.refresh()

    def refresh(self) -> None:
        rows = self.service.list_parking()
        self.table.setRowCount(len(rows))
        for r, row in enumerate(rows):
            vals = [row["created_at"], row["node_code"] or "-", row["content"], row["status"]]
            for c, v in enumerate(vals):
                self.table.setItem(r, c, QTableWidgetItem(str(v)))
        self.table.resizeColumnsToContents()
