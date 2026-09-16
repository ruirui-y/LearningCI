from __future__ import annotations

import sys

from PyQt6.QtWidgets import QApplication, QMessageBox

from learningci.config import (
    APP_NAME, APP_VERSION, DB_PATH, DEFAULT_BUNDLE_DIR, DEFAULT_PLAN_PATH,
    prepare_local_database,
)
from learningci.core.bundle_loader import ensure_bundles_imported
from learningci.core.plan_loader import ensure_plan_imported
from learningci.core.service import LearningService
from learningci.database import Database
from learningci.theme import apply_dark_theme
from learningci.ui.main_window import MainWindow


def run() -> int:
    restored = prepare_local_database()
    app = QApplication(sys.argv)
    app.setApplicationName(APP_NAME)
    app.setApplicationVersion(APP_VERSION)
    apply_dark_theme(app)

    db = Database(DB_PATH)
    db.initialize()
    try:
        ensure_plan_imported(db, DEFAULT_PLAN_PATH)
        ensure_bundles_imported(db, DEFAULT_BUNDLE_DIR)
    except Exception as exc:
        QMessageBox.critical(None, "LearningCI 无法加载冻结计划", str(exc))
        db.close()
        return 2

    service = LearningService(db)
    window = MainWindow(service)
    if restored:
        window.setWindowTitle("LearningCI · 已从 sync/learningci.db 恢复")
    window.show()
    code = app.exec()
    db.close()
    return code
