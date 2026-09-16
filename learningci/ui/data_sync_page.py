from __future__ import annotations

from pathlib import Path

from PyQt6.QtCore import pyqtSignal
from PyQt6.QtWidgets import (
    QFrame, QHBoxLayout, QLabel, QMessageBox, QPushButton, QVBoxLayout, QWidget
)

from learningci.config import DB_PATH, SYNC_DB_PATH


def _size_text(size: int) -> str:
    if size < 1024:
        return f"{size} B"
    if size < 1024 * 1024:
        return f"{size / 1024:.1f} KiB"
    return f"{size / 1024 / 1024:.2f} MiB"


class DataSyncPage(QWidget):
    data_changed = pyqtSignal()

    def __init__(self, service, parent=None):
        super().__init__(parent)
        self.service = service
        self._build_ui()
        self.refresh()

    def _build_ui(self) -> None:
        root = QVBoxLayout(self)
        root.setContentsMargins(24, 20, 24, 24)
        root.setSpacing(14)

        title = QLabel("数据同步")
        title.setObjectName("PageTitle")
        sub = QLabel("运行数据库保存在 data/；Git 只提交 sync/learningci.db 一致性快照。换电脑 pull 后可直接恢复。")
        sub.setObjectName("PageSub")
        sub.setWordWrap(True)
        root.addWidget(title)
        root.addWidget(sub)

        card = QFrame()
        card.setObjectName("Card")
        box = QVBoxLayout(card)
        box.setContentsMargins(16, 14, 16, 14)
        box.setSpacing(10)
        self.local_label = QLabel("")
        self.local_label.setWordWrap(True)
        self.local_label.setObjectName("Secondary")
        self.snapshot_label = QLabel("")
        self.snapshot_label.setWordWrap(True)
        self.snapshot_label.setObjectName("ProjectPath")
        box.addWidget(QLabel("本地运行数据库"))
        box.addWidget(self.local_label)
        box.addSpacing(8)
        box.addWidget(QLabel("Git 同步快照"))
        box.addWidget(self.snapshot_label)
        root.addWidget(card)

        actions = QHBoxLayout()
        self.export_btn = QPushButton("生成 / 更新 Git 同步快照")
        self.export_btn.setObjectName("PrimaryButton")
        self.restore_btn = QPushButton("从同步快照恢复到本机")
        self.restore_btn.setObjectName("DangerButton")
        self.check_btn = QPushButton("检查本地数据库")
        self.check_btn.setObjectName("SecondaryButton")
        actions.addWidget(self.export_btn)
        actions.addWidget(self.restore_btn)
        actions.addWidget(self.check_btn)
        actions.addStretch(1)
        root.addLayout(actions)

        warn = QFrame()
        warn.setObjectName("WarningCard")
        warn_box = QVBoxLayout(warn)
        warn_box.setContentsMargins(14, 12, 14, 12)
        w = QLabel(
            "同步规则：同一时间只在一台电脑上写 LearningCI。学习结束 → 生成快照 → git add/commit/push；"
            "另一台电脑先 git pull → 恢复快照 → 再继续学习。不要尝试 merge 两个同时修改过的 SQLite 文件。"
        )
        w.setWordWrap(True)
        w.setObjectName("WarnNote")
        warn_box.addWidget(w)
        root.addWidget(warn)
        root.addStretch(1)

        self.export_btn.clicked.connect(self._export)
        self.restore_btn.clicked.connect(self._restore)
        self.check_btn.clicked.connect(self._check)

    def refresh(self) -> None:
        local_size = DB_PATH.stat().st_size if DB_PATH.exists() else 0
        self.local_label.setText(f"{DB_PATH}\n大小：{_size_text(local_size)}")
        info = self.service.sync_snapshot_info()
        if info["exists"]:
            self.snapshot_label.setText(
                f"{info['path']}\n大小：{_size_text(info['size_bytes'])} · 更新时间：{info['mtime']}\n"
                "这个文件允许提交到 Git。"
            )
        else:
            self.snapshot_label.setText(f"{SYNC_DB_PATH}\n尚未生成同步快照。")
        self.restore_btn.setEnabled(bool(info["exists"]))

    def _export(self) -> None:
        try:
            result = self.service.create_sync_snapshot()
            QMessageBox.information(
                self,
                "同步快照已生成",
                f"已使用 SQLite backup API 生成一致性快照：\n{result['path']}\n\n"
                "现在可以把 sync/learningci.db 提交到你的数据仓库 / 私有 Git 仓库。",
            )
            self.refresh()
        except Exception as exc:
            QMessageBox.critical(self, "生成快照失败", str(exc))

    def _restore(self) -> None:
        reply = QMessageBox.warning(
            self,
            "确认恢复同步快照",
            "这会用 sync/learningci.db 覆盖当前本地运行数据。\n\n"
            "如果本机存在尚未同步的新学习记录，请先生成快照或备份。\n\n继续？",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.Cancel,
            QMessageBox.StandardButton.Cancel,
        )
        if reply != QMessageBox.StandardButton.Yes:
            return
        try:
            result = self.service.restore_sync_snapshot()
            QMessageBox.information(
                self, "恢复完成",
                f"数据库已从同步快照恢复。integrity_check: {result['integrity']}\n界面将重新读取数据。",
            )
            self.refresh()
            self.data_changed.emit()
        except Exception as exc:
            QMessageBox.critical(self, "恢复失败", str(exc))

    def _check(self) -> None:
        try:
            result = self.service.db.integrity_check()
            QMessageBox.information(self, "数据库完整性检查", result)
        except Exception as exc:
            QMessageBox.critical(self, "数据库检查失败", str(exc))
