from __future__ import annotations

from pathlib import Path

from PyQt6.QtCore import pyqtSignal
from PyQt6.QtWidgets import (
    QAbstractItemView, QApplication, QFileDialog, QFrame, QHBoxLayout, QLabel, QMessageBox,
    QPushButton, QTableWidget, QTableWidgetItem, QTextEdit, QVBoxLayout, QWidget,
)

from learningci.config import REFINE_EXPORT_DIR
from learningci.ui.common import bundle_state_text, learning_state_text, priority_text


class NodePreparePage(QWidget):
    data_changed = pyqtSignal()
    open_node = pyqtSignal(dict)

    def __init__(self, service, parent=None):
        super().__init__(parent)
        self.service = service
        self.rows: list[dict] = []
        self._build_ui()
        self.refresh()

    def _build_ui(self) -> None:
        root = QVBoxLayout(self)
        root.setContentsMargins(24, 20, 24, 24)
        root.setSpacing(12)

        title = QLabel("节点准备")
        title.setObjectName("PageTitle")
        sub = QLabel(
            "这里不改变学习路线，只把即将执行的节点细化成可逐项打卡的任务。"
            "不接任何 AI API：导出 ZIP → 上传给 ChatGPT → 导回 JSON → 本地校验 → 你确认后采用。"
        )
        sub.setObjectName("PageSub")
        sub.setWordWrap(True)
        root.addWidget(title)
        root.addWidget(sub)

        explain = QFrame()
        explain.setObjectName("InfoCard")
        explain_box = QVBoxLayout(explain)
        explain_box.setContentsMargins(14, 12, 14, 12)
        e = QLabel(
            "节点准备由系统管理，不是学习任务。\n"
            "• 草稿：节点尚未生成可执行任务包。\n"
            "• 已审核：任务结构通过校验，可以进入学习。\n"
            "• 执行中：节点已经开始学习，但子执行包仍允许迭代覆盖。\n\n"
            "系统会自动检查任务组边界、must_learn 覆盖和验收条件。\n"
            "学习者只需要完成叶子任务、记录真实证据，并通过能力核对。\n\n"
            "不会要求你提前理解路线管理、Verification 或内部审核流程。"
        )
        e.setWordWrap(True)
        e.setObjectName("Secondary")
        explain_box.addWidget(e)
        root.addWidget(explain)

        self.table = QTableWidget(0, 9)
        self.table.setHorizontalHeaderLabels([
            "顺序", "Node", "阶段", "优先级", "Title", "叶子任务", "执行包状态", "学习状态", "可准备"
        ])
        self.table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.table.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        self.table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.table.itemSelectionChanged.connect(self._selection_changed)
        self.table.itemDoubleClicked.connect(self._open_selected_node)
        root.addWidget(self.table, 1)

        actions = QHBoxLayout()
        self.export_btn = QPushButton("生成学习任务包并复制 AI 提示词")
        self.export_btn.setObjectName("PrimaryButton")
        self.import_btn = QPushButton("导入 ChatGPT 细化结果")
        self.import_btn.setObjectName("SuccessButton")
        self.skip_btn = QPushButton("跳过当前节点")
        self.skip_btn.setObjectName("SecondaryButton")
        self.refresh_btn = QPushButton("刷新")
        self.refresh_btn.setObjectName("SecondaryButton")
        actions.addWidget(self.export_btn)
        actions.addWidget(self.import_btn)
        actions.addWidget(self.skip_btn)
        actions.addWidget(self.refresh_btn)
        actions.addStretch(1)
        root.addLayout(actions)

        self.detail = QTextEdit()
        self.detail.setReadOnly(True)
        self.detail.setMinimumHeight(165)
        self.detail.setPlaceholderText("选择一个节点后，这里会显示准备规则。")
        root.addWidget(self.detail)

        self.export_btn.clicked.connect(self._export)
        self.import_btn.clicked.connect(self._import)
        self.refresh_btn.clicked.connect(self.refresh)
        self.skip_btn.clicked.connect(self._skip_selected)

    def refresh(self) -> None:
        self.rows = self.service.list_preparation_nodes()
        self.table.setRowCount(len(self.rows))
        for r, row in enumerate(self.rows):
            values = [
                row["order_index"], row["node_code"], row["stage"], priority_text(row["priority"]), row["title"],
                row["task_count"], bundle_state_text(row["bundle_state"]), learning_state_text(row["learning_state"]),
                "是" if row.get("in_prepare_window") else "否",
            ]
            for c, value in enumerate(values):
                self.table.setItem(r, c, QTableWidgetItem(str(value)))
        self.table.resizeColumnsToContents()
        if self.rows and self.table.currentRow() < 0:
            idx = next(
                (i for i, x in enumerate(self.rows)
                 if x.get("in_prepare_window")),
                0,
            )
            self.table.selectRow(idx)
        self._selection_changed()

    def _selected(self) -> dict | None:
        row = self.table.currentRow()
        if row < 0 or row >= len(self.rows):
            return None
        return self.rows[row]

    def _selection_changed(self) -> None:
        row = self._selected()
        if not row:
            self.export_btn.setEnabled(False)
            self.import_btn.setEnabled(False)
            self.detail.clear()
            return
        # 子节点执行包允许迭代覆盖；是否可细化只由三节点准备窗口决定。
        allowed = bool(row.get("in_prepare_window"))
        self.export_btn.setEnabled(allowed)
        self.import_btn.setEnabled(allowed)
        self.skip_btn.setEnabled(row.get("learning_state") in {"CURRENT", "PREP_REQUIRED"})
        window_note = "已进入三节点准备窗口，可以细化。" if row.get("in_prepare_window") else "尚未进入三节点准备窗口，暂时禁止细化。"
        self.detail.setPlainText(
            f"Node：{row['node_code']}\n"
            f"Title：{row['title']}\n"
            f"节点能力：{row['capability']}\n\n"
            f"当前执行包：{bundle_state_text(row['bundle_state'])} · 第 {row['bundle_revision']} 版 · "
            f"{row['task_count']} 个叶子任务\n"
            f"固定试卷：{row['paper_id']}\n"
            f"学习状态：{learning_state_text(row['learning_state'])}\n"
            f"准备窗口：{window_note}\n\n"
            "导出的 ZIP 已包含：冻结根路线中的节点定义、当前可迭代执行包、NebulaRPC 总计划、前置节点结果、"
            "返回 JSON 结构约束、自检清单和求职证据背景。导出成功后，LearningCI 还会自动把精确的 AI 提示词复制到剪贴板。\n\n"
            "下一步只需要：上传 ZIP → 粘贴剪贴板提示词 → 发送 → 下载 AI 生成的 JSON 文件 → 回本页导入。"
        )


    def _open_selected_node(self, item=None) -> None:
        row = self._selected()
        if not row:
            return
        state = row.get("learning_state")
        if state not in ("PASSED", "CURRENT", "PREP_REQUIRED", "PREPARE", "PREP", "READY"):
            QMessageBox.information(
                self,
                "无法进入学习",
                f"Node：{row['node_code']}\n\n当前学习状态：{learning_state_text(state)}\n\n未解锁节点不能进入学习界面。",
            )
            return
        self.open_node.emit(row)

    def _skip_selected(self) -> None:
        row = self._selected()
        if not row:
            return
        reply = QMessageBox.question(
            self,
            "跳过节点",
            f"确认跳过 {row['node_code']}？\n\n跳过后允许继续推进路线。",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
        )
        if reply == QMessageBox.StandardButton.Yes:
            self.service.skip_node(row["id"])
            self.refresh()
            self.data_changed.emit()

    def _export(self) -> None:
        row = self._selected()
        if not row:
            return
        default = REFINE_EXPORT_DIR / f"{row['node_code']}_节点细化包.zip"
        path, _ = QFileDialog.getSaveFileName(
            self, "保存节点细化包", str(default), "ZIP 压缩包 (*.zip)"
        )
        if not path:
            return
        try:
            result = self.service.export_refinement_package(row["id"], Path(path))
            prompt = self.service.get_refinement_ai_prompt(row["id"])
            QApplication.clipboard().setText(prompt)
            QMessageBox.information(
                self,
                "节点细化包已导出",
                f"已生成：\n{result}\n\n"
                "AI 节点细化提示词已经自动复制到系统剪贴板。\n\n"
                "下一步：\n"
                "1. 把这个 ZIP 上传给 ChatGPT\n"
                "2. 直接 Ctrl+V 粘贴提示词并发送\n"
                "3. 下载 ChatGPT 生成的 JSON 文件后回到本页直接导入\n\n"
                "如果剪贴板被覆盖，ZIP 内的 00-复制给AI的提示词.txt 保存了同一份提示词。",
            )
        except Exception as exc:
            QMessageBox.critical(self, "导出失败", str(exc))

    def _import(self) -> None:
        row = self._selected()
        if not row:
            return
        path, _ = QFileDialog.getOpenFileName(
            self, "选择 ChatGPT 返回的细化结果", "", "JSON 文件 (*.json)"
        )
        if not path:
            return
        try:
            preview = self.service.preview_refined_bundle(row["id"], Path(path))
            warnings = preview.get("structure_warnings", [])
            warning_text = ""
            if warnings:
                warning_text = "\n结构提醒：\n- " + "\n- ".join(warnings) + "\n"
            recommended = preview.get("recommended_task_range", [20, 30])
            added = preview.get("added_task_ids", [])
            removed = preview.get("removed_task_ids", [])
            modified = preview.get("modified_task_ids", [])
            diff_text = (
                f"任务变化：新增 {len(added)} / 删除 {len(removed)} / 修改 {len(modified)}\n"
            )
            if removed:
                diff_text += "删除：" + "、".join(removed[:6]) + (" …" if len(removed) > 6 else "") + "\n"
            if modified:
                diff_text += "修改：" + "、".join(modified[:6]) + (" …" if len(modified) > 6 else "") + "\n"
            answer = QMessageBox.question(
                self,
                "确认采用细化结果",
                f"Node：{preview['node_code']}\n\n"
                f"任务组：{preview['old_groups']} → {preview['new_groups']}（结构保护已通过）\n"
                f"叶子任务：{preview['old_tasks']} → {preview['new_tasks']} "
                f"（通常建议 {recommended[0]}~{recommended[1]}）\n"
                f"执行包状态：{bundle_state_text(preview['old_state'])} → {bundle_state_text(preview['new_state'])}\n"
                f"下一版本：第 {preview['next_revision']} 版\n"
                f"固定试卷：{preview['paper_id']}\n"
                f"{diff_text}"
                f"{warning_text}\n"
                "返回文件已经通过格式、路线与任务组结构校验。是否正式覆盖当前子执行包？\n"
                "根计划和固定试卷不会改变；采用前旧执行包会自动备份。",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                QMessageBox.StandardButton.No,
            )
            if answer != QMessageBox.StandardButton.Yes:
                return
            result = self.service.apply_refined_bundle(row["id"], Path(preview["staged_path"]))
            QMessageBox.information(
                self,
                "细化结果已采用",
                f"Node：{result['node_code']}\n"
                f"叶子任务：{result['old_tasks']} → {result['new_tasks']}\n"
                f"执行包状态：{bundle_state_text(result['old_state'])} → {bundle_state_text(result['new_state'])}\n"
                f"版本：第 {result['revision']} 版\n"
                f"固定试卷：{result['paper_id']}\n\n"
                f"旧版本备份：\n{result['backup_path']}\n\n"
                "节点执行包已更新。根计划与固定试卷继续受保护；子执行包后续仍可通过本页迭代覆盖。",
            )
            self.refresh()
            self.data_changed.emit()
        except Exception as exc:
            QMessageBox.critical(self, "导入失败", str(exc))
