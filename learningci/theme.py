from __future__ import annotations

from PyQt6.QtGui import QColor, QPalette
from PyQt6.QtWidgets import QApplication

# Centralized dark palette. Page/widget code should not scatter literal colors.
APP_BG = "#0F1115"
SIDEBAR_BG = "#11141A"
CARD_BG = "#171A21"
CARD_BG_ALT = "#1D212A"
CARD_HOVER = "#222833"
BORDER = "#2A303B"
BORDER_HOVER = "#3A4250"
TEXT_PRIMARY = "#F3F4F6"
TEXT_SECONDARY = "#9CA3AF"
TEXT_MUTED = "#6B7280"
PRIMARY = "#3B82F6"
PRIMARY_BG = "#1E3A5F"
PRIMARY_HOVER = "#285782"
PRIMARY_PRESSED = "#152C49"
SUCCESS = "#22C55E"
SUCCESS_BG = "#163B2A"
SUCCESS_HOVER = "#1D5038"
SUCCESS_PRESSED = "#102A1D"
DANGER = "#EF4444"
DANGER_BG = "#422020"
DANGER_HOVER = "#5A2929"
DANGER_PRESSED = "#311717"
WARNING = "#F59E0B"
SELECTION = "#2A3548"


def build_qss() -> str:
    return f"""
    QWidget {{
        background-color: {APP_BG};
        color: {TEXT_PRIMARY};
        font-family: "Microsoft YaHei", "PingFang SC", "SimHei", "Segoe UI";
        font-size: 13px;
    }}
    QMainWindow, QDialog {{ background-color: {APP_BG}; }}
    QLabel {{ background: transparent; color: {TEXT_PRIMARY}; }}

    QFrame#Sidebar {{
        background-color: {SIDEBAR_BG};
        border-right: 1px solid {BORDER};
    }}
    QLabel#AppTitle {{ font-size: 18px; font-weight: 700; }}
    QLabel#AppSub {{ color: {TEXT_MUTED}; font-size: 11px; }}
    QLabel#PageTitle {{ font-size: 24px; font-weight: 700; }}
    QLabel#PageSub {{ color: {TEXT_SECONDARY}; }}
    QLabel#SectionTitle {{ font-size: 15px; font-weight: 700; }}
    QLabel#Muted {{ color: {TEXT_MUTED}; }}
    QLabel#Secondary {{ color: {TEXT_SECONDARY}; }}
    QLabel#FocusTimer {{ font-size: 30px; font-weight: 700; letter-spacing: 1px; }}
    QLabel#QuestionHeader {{ color: {TEXT_SECONDARY}; font-size: 12px; font-weight: 700; }}
    QLabel#QuestionText {{ color: {TEXT_PRIMARY}; font-size: 13px; line-height: 1.45; }}
    QLabel#ProjectPath {{ color: {WARNING}; font-size: 12px; }}

    QFrame#Card, QFrame#StatCard, QFrame#QuestionCard {{
        background-color: {CARD_BG};
        border: 1px solid {BORDER};
        border-radius: 10px;
    }}
    QFrame#QuestionCard:hover {{ border-color: {BORDER_HOVER}; }}
    QLabel#StatLabel {{ color: {TEXT_SECONDARY}; font-size: 11px; }}
    QLabel#StatValue {{ font-size: 22px; font-weight: 700; }}
    QLabel#StatHint {{ color: {TEXT_MUTED}; font-size: 10px; }}

    QPushButton {{
        background-color: {CARD_BG_ALT};
        color: {TEXT_PRIMARY};
        border: 1px solid {BORDER};
        border-radius: 7px;
        padding: 8px 15px;
        min-height: 18px;
    }}
    QPushButton:hover {{
        background-color: {CARD_HOVER};
        border-color: {BORDER_HOVER};
    }}
    QPushButton:pressed {{
        background-color: #181C23;
        border-color: #323A47;
        padding-top: 9px;
        padding-bottom: 7px;
    }}
    QPushButton:focus {{ border-color: #4A79AC; }}
    QPushButton:disabled {{
        color: {TEXT_MUTED};
        background-color: {CARD_BG};
        border-color: {BORDER};
    }}

    QPushButton#PrimaryButton {{
        background-color: {PRIMARY_BG};
        border-color: #2A5377;
        color: {TEXT_PRIMARY};
        font-weight: 650;
    }}
    QPushButton#PrimaryButton:hover {{ background-color: {PRIMARY_HOVER}; border-color: #3B6F9B; }}
    QPushButton#PrimaryButton:pressed {{ background-color: {PRIMARY_PRESSED}; border-color: #23435F; }}

    QPushButton#SuccessButton {{
        background-color: {SUCCESS_BG};
        border-color: #236B48;
        color: #CFFAE1;
        font-weight: 650;
    }}
    QPushButton#SuccessButton:hover {{ background-color: {SUCCESS_HOVER}; border-color: #2B8658; }}
    QPushButton#SuccessButton:pressed {{ background-color: {SUCCESS_PRESSED}; border-color: #1C5B3A; }}

    QPushButton#DangerButton {{
        background-color: {DANGER_BG};
        border-color: #713535;
        color: #FFD4D4;
        font-weight: 650;
    }}
    QPushButton#DangerButton:hover {{ background-color: {DANGER_HOVER}; border-color: #914343; }}
    QPushButton#DangerButton:pressed {{ background-color: {DANGER_PRESSED}; border-color: #652E2E; }}

    QPushButton#SecondaryButton {{
        background-color: {CARD_BG_ALT};
        border-color: {BORDER_HOVER};
        color: {TEXT_PRIMARY};
        font-weight: 600;
    }}
    QPushButton#SecondaryButton:hover {{ background-color: #29313D; border-color: #4A5564; }}
    QPushButton#SecondaryButton:pressed {{ background-color: #1A2028; border-color: #394352; }}

    QPushButton#NavButton {{
        text-align: left;
        padding: 10px 12px;
        border: none;
        border-left: 3px solid transparent;
        border-radius: 6px;
        background: transparent;
        color: {TEXT_SECONDARY};
    }}
    QPushButton#NavButton:hover {{ background-color: {CARD_BG}; color: {TEXT_PRIMARY}; }}
    QPushButton#NavButton:pressed {{ background-color: #1A1F27; }}
    QPushButton#NavButton[active="true"] {{
        background-color: {CARD_BG_ALT};
        color: {TEXT_PRIMARY};
        border-left: 3px solid {PRIMARY};
        font-weight: 650;
    }}

    QLineEdit, QTextEdit, QPlainTextEdit, QSpinBox, QComboBox {{
        background-color: {CARD_BG_ALT};
        color: {TEXT_PRIMARY};
        border: 1px solid {BORDER};
        border-radius: 7px;
        padding: 7px;
        selection-background-color: {SELECTION};
        selection-color: {TEXT_PRIMARY};
    }}
    QLineEdit:hover, QTextEdit:hover, QPlainTextEdit:hover, QSpinBox:hover, QComboBox:hover {{
        border-color: {BORDER_HOVER};
    }}
    QLineEdit:focus, QTextEdit:focus, QPlainTextEdit:focus, QSpinBox:focus, QComboBox:focus {{
        border-color: #3A6EA5;
    }}
    QTextEdit#AnswerEditor {{ background-color: #141820; }}

    QCheckBox {{ spacing: 8px; }}
    QCheckBox::indicator {{
        width: 18px; height: 18px;
        border-radius: 4px;
        border: 1px solid #3A4250;
        background: {CARD_BG_ALT};
    }}
    QCheckBox::indicator:hover {{ border-color: #57708D; background: #222A35; }}
    QCheckBox::indicator:checked {{ background: {PRIMARY}; border-color: {PRIMARY}; }}
    QCheckBox::indicator:checked:hover {{ background: #5596F0; border-color: #5596F0; }}

    QProgressBar {{
        background-color: {CARD_BG_ALT};
        border: 1px solid {BORDER};
        border-radius: 6px;
        height: 12px;
        text-align: center;
        color: transparent;
    }}
    QProgressBar::chunk {{ background-color: {PRIMARY}; border-radius: 5px; }}

    QTableWidget {{
        background-color: {CARD_BG};
        alternate-background-color: {CARD_BG_ALT};
        color: {TEXT_PRIMARY};
        border: 1px solid {BORDER};
        gridline-color: {BORDER};
        selection-background-color: {SELECTION};
        selection-color: {TEXT_PRIMARY};
        outline: 0;
    }}
    QTableWidget::item {{ padding: 6px; }}
    QTableWidget::item:hover {{ background-color: #222A35; }}
    QHeaderView::section {{
        background-color: {CARD_BG_ALT}; color: {TEXT_SECONDARY}; padding: 7px;
        border: none; border-right: 1px solid {BORDER}; border-bottom: 1px solid {BORDER}; font-weight: 600;
    }}

    QScrollArea#AssessmentScroll {{ background: transparent; border: none; }}
    QScrollArea#AssessmentScroll > QWidget > QWidget {{ background: transparent; }}
    QScrollBar:vertical {{ background: {CARD_BG}; width: 12px; margin: 0; }}
    QScrollBar::handle:vertical {{ background: #3A4250; border-radius: 4px; min-height: 24px; }}
    QScrollBar::handle:vertical:hover {{ background: #4A5260; }}
    QScrollBar::handle:vertical:pressed {{ background: #596473; }}
    QScrollBar::add-line, QScrollBar::sub-line {{ width: 0; height: 0; border: none; }}
    QScrollBar::add-page, QScrollBar::sub-page {{ background: {CARD_BG}; }}

    QLabel#ResultBanner {{
        background-color: {CARD_BG};
        border: 1px solid {BORDER};
        border-radius: 8px;
        padding: 10px 12px;
        font-weight: 700;
    }}
    QLabel[status="pass"] {{ color: {SUCCESS}; }}
    QLabel[status="fail"] {{ color: {DANGER}; }}
    QLabel[status="warn"] {{ color: {WARNING}; }}
    QLabel[status="info"] {{ color: {PRIMARY}; }}


    QFrame#TaskDetailCard {{
        background-color: #141820;
        border: 1px solid {BORDER};
        border-radius: 9px;
    }}
    QFrame#WarningCard {{
        background-color: #241D12;
        border: 1px solid #5C4722;
        border-radius: 9px;
    }}
    QLabel#TaskCriteria {{
        color: {TEXT_SECONDARY};
        background-color: {CARD_BG_ALT};
        border: 1px solid {BORDER};
        border-radius: 6px;
        padding: 8px;
    }}
    QLabel#TaskTimer {{
        color: {PRIMARY};
        font-size: 13px;
        font-weight: 700;
    }}
    QLabel#WarnNote {{
        color: {WARNING};
    }}

    QTreeWidget#TaskTree, QTreeWidget#PaperPreviewTree {{
        background-color: {CARD_BG};
        alternate-background-color: {CARD_BG};
        color: {TEXT_PRIMARY};
        border: 1px solid {BORDER};
        border-radius: 8px;
        outline: 0;
        selection-background-color: {SELECTION};
        selection-color: {TEXT_PRIMARY};
    }}
    QTreeWidget#TaskTree::item, QTreeWidget#PaperPreviewTree::item {{
        padding: 5px 4px;
        border-bottom: 1px solid #202630;
    }}
    QTreeWidget#TaskTree::item:hover, QTreeWidget#PaperPreviewTree::item:hover {{
        background-color: #222A35;
    }}
    QTreeWidget#TaskTree::item:selected, QTreeWidget#PaperPreviewTree::item:selected {{
        background-color: {SELECTION};
    }}
    QTreeWidget#TaskTree::branch, QTreeWidget#PaperPreviewTree::branch {{
        background: transparent;
    }}
    QTreeWidget QHeaderView::section {{
        background-color: {CARD_BG_ALT};
        color: {TEXT_SECONDARY};
        border: none;
        border-bottom: 1px solid {BORDER};
        padding: 6px;
        font-weight: 600;
    }}
    QSplitter#TaskSplitter::handle {{
        background-color: {BORDER};
        width: 2px;
    }}
    QScrollArea#TodayScroll {{
        border: none;
        background: transparent;
    }}
    QScrollArea#TodayScroll > QWidget > QWidget {{
        background: transparent;
    }}

    QToolTip {{ background-color: {CARD_BG_ALT}; color: {TEXT_PRIMARY}; border: 1px solid {BORDER}; padding: 4px 6px; }}
    QMessageBox {{ background-color: {CARD_BG}; }}
    """


def apply_dark_theme(app: QApplication) -> None:
    palette = app.palette()
    palette.setColor(QPalette.ColorRole.Window, QColor(APP_BG))
    palette.setColor(QPalette.ColorRole.WindowText, QColor(TEXT_PRIMARY))
    palette.setColor(QPalette.ColorRole.Base, QColor(CARD_BG_ALT))
    palette.setColor(QPalette.ColorRole.AlternateBase, QColor(CARD_BG))
    palette.setColor(QPalette.ColorRole.Text, QColor(TEXT_PRIMARY))
    palette.setColor(QPalette.ColorRole.Button, QColor(CARD_BG_ALT))
    palette.setColor(QPalette.ColorRole.ButtonText, QColor(TEXT_PRIMARY))
    palette.setColor(QPalette.ColorRole.ToolTipBase, QColor(CARD_BG_ALT))
    palette.setColor(QPalette.ColorRole.ToolTipText, QColor(TEXT_PRIMARY))
    palette.setColor(QPalette.ColorRole.Highlight, QColor(SELECTION))
    palette.setColor(QPalette.ColorRole.HighlightedText, QColor(TEXT_PRIMARY))
    app.setPalette(palette)
    app.setStyleSheet(build_qss())
