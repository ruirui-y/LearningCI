from __future__ import annotations

from PyQt6.QtWidgets import QAbstractItemView, QLabel, QTableWidget, QTableWidgetItem, QVBoxLayout, QWidget

from learningci.ui.common import bundle_state_text, learning_state_text, priority_text


class PlanPage(QWidget):
    def __init__(self, service, parent=None):
        super().__init__(parent)
        self.service = service
        layout = QVBoxLayout(self)
        layout.setContentsMargins(24, 20, 24, 24)
        title = QLabel("冻结计划")
        title.setObjectName("PageTitle")
        sub = QLabel(
            "只读。plan.json 决定主路线；‘节点执行包’决定某个 Node 具体怎么做以及首次固定试卷。"
            "主线节点按顺序推进，可选节点不阻塞主线。"
        )
        sub.setObjectName("PageSub")
        sub.setWordWrap(True)
        layout.addWidget(title)
        layout.addWidget(sub)
        legend = QLabel(
            "字段说明：执行包状态 = 当前 Node 的任务清单是否已细化/审核/进入执行；子执行包可迭代覆盖；"
            "固定试卷 = 这个 Node 第一次正式验收使用的试卷；"
            "学习状态 = 当前是否轮到它；正式测试总分 70 即可推进下一 Node，80+ 作为稳定掌握目标；"
            "稳定分 = 把延迟复测后的掉分也算进去的长期成绩。"
        )
        legend.setObjectName("Secondary")
        legend.setWordWrap(True)
        layout.addWidget(legend)
        self.table = QTableWidget(0, 11)
        self.table.setHorizontalHeaderLabels([
            "顺序", "Node", "阶段", "优先级", "Title", "叶子任务", "执行包状态", "固定试卷", "学习状态", "当前分", "稳定分"
        ])
        self.table.horizontalHeader().setStretchLastSection(True)
        self.table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.table.setToolTip(
            "执行包状态：草稿（待细化）→ 已审核（可执行）→ 执行中（可覆盖）。\n"
            "固定试卷：节点开始时就能预览，首次未通过时继续使用同一张试卷。"
        )
        layout.addWidget(self.table, 1)
        self.refresh()

    def refresh(self) -> None:
        nodes = self.service.list_preparation_nodes()
        self.table.setRowCount(len(nodes))
        for r, node in enumerate(nodes):
            values = [
                node["order_index"], node["node_code"], node["stage"], priority_text(node["priority"]), node["title"],
                node["task_count"], bundle_state_text(node["bundle_state"]), node["paper_id"],
                learning_state_text(node["learning_state"]),
                "-" if node["current_score"] is None else node["current_score"],
                "-" if node["stable_score"] is None else node["stable_score"],
            ]
            for c, value in enumerate(values):
                self.table.setItem(r, c, QTableWidgetItem(str(value)))
        self.table.resizeColumnsToContents()
