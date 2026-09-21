from __future__ import annotations

from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import QFrame, QLabel, QVBoxLayout


class StatCard(QFrame):
    def __init__(self, label: str, value: str = "-", hint: str = "", parent=None):
        super().__init__(parent)
        self.setObjectName("StatCard")
        layout = QVBoxLayout(self)
        layout.setContentsMargins(14, 12, 14, 12)
        layout.setSpacing(4)
        self.label = QLabel(label)
        self.label.setObjectName("StatLabel")
        self.value = QLabel(value)
        self.value.setObjectName("StatValue")
        self.hint = QLabel(hint)
        self.hint.setObjectName("StatHint")
        self.hint.setWordWrap(True)
        layout.addWidget(self.label)
        layout.addWidget(self.value)
        layout.addWidget(self.hint)
        layout.addStretch(1)

    def set_value(self, value: str, hint: str | None = None) -> None:
        self.value.setText(value)
        if hint is not None:
            self.hint.setText(hint)


def format_duration(seconds: int) -> str:
    seconds = max(0, int(seconds))
    hours, rem = divmod(seconds, 3600)
    minutes, secs = divmod(rem, 60)
    if hours:
        return f"{hours:02d}:{minutes:02d}:{secs:02d}"
    return f"{minutes:02d}:{secs:02d}"


def format_hours(seconds: int) -> str:
    return f"{seconds / 3600:.1f} h"

BUNDLE_STATE_ZH = {
    "GENERATED": "草稿（待细化）",
    "REVIEWED": "已审核（可执行）",
    "FROZEN": "执行中（可覆盖）",
    "MISSING": "缺失",
}

LEARNING_STATE_ZH = {
    "CURRENT": "当前节点",
    "PREP_REQUIRED": "当前节点待准备",
    "LOCKED": "未解锁",
    "PASSED": "已通过",
    "OPTIONAL": "可选研究",
}

PRIORITY_ZH = {
    "CORE": "主线",
    "OPTIONAL": "可选",
}


def bundle_state_text(value: str) -> str:
    return BUNDLE_STATE_ZH.get(str(value).upper(), str(value))


def learning_state_text(value: str) -> str:
    return LEARNING_STATE_ZH.get(str(value).upper(), str(value))


def priority_text(value: str) -> str:
    return PRIORITY_ZH.get(str(value).upper(), str(value))
