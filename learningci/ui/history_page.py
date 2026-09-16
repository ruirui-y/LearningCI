from __future__ import annotations

from PyQt6.QtWidgets import QAbstractItemView, QComboBox, QHBoxLayout, QLabel, QTableWidget, QTableWidgetItem, QVBoxLayout, QWidget

from learningci.ui.common import format_duration


class HistoryPage(QWidget):
    def __init__(self, service, parent=None):
        super().__init__(parent)
        self.service = service
        layout = QVBoxLayout(self)
        layout.setContentsMargins(24, 20, 24, 24)
        title = QLabel("History & Statistics")
        title.setObjectName("PageTitle")
        sub = QLabel("专注时间、任务完成度、考试分数分别统计；打卡不能替代能力分。")
        sub.setObjectName("PageSub")
        layout.addWidget(title)
        layout.addWidget(sub)
        top = QHBoxLayout()
        top.addWidget(QLabel("汇总周期"))
        self.period = QComboBox()
        self.period.addItem("每日", "day")
        self.period.addItem("每周", "week")
        self.period.addItem("每月", "month")
        self.period.currentIndexChanged.connect(self.refresh)
        top.addWidget(self.period)
        top.addStretch(1)
        layout.addLayout(top)
        self.table = QTableWidget(0, 6)
        self.table.setHorizontalHeaderLabels(["Period", "Focus", "Task %", "Avg Score", "Exams", "Passed"])
        self.table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        layout.addWidget(self.table, 1)
        self.refresh()

    def refresh(self) -> None:
        period = self.period.currentData() if hasattr(self, "period") else "day"
        if period == "day":
            daily = self.service.daily_history(90)
            rows = [
                {
                    "period": r["day"], "focus_seconds": r["focus_seconds"], "completion": r["completion"],
                    "avg_score": r["avg_score"], "exams": r["exams"], "passed": r["passed"],
                }
                for r in daily
            ]
        else:
            rows = self.service.aggregate_history(period, 365)
        self.table.setRowCount(len(rows))
        for r, row in enumerate(rows):
            vals = [
                row["period"], format_duration(row["focus_seconds"]),
                "-" if row["completion"] is None else f"{row['completion']}%",
                "-" if row["avg_score"] is None else row["avg_score"],
                row["exams"], row["passed"],
            ]
            for c, v in enumerate(vals):
                self.table.setItem(r, c, QTableWidgetItem(str(v)))
        self.table.resizeColumnsToContents()
