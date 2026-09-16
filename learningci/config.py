from __future__ import annotations

import os
import shutil
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
DATA_DIR = Path(os.environ.get("LEARNINGCI_DATA_DIR", REPO_ROOT / "data"))
SYNC_DIR = REPO_ROOT / "sync"
DB_PATH = DATA_DIR / "learningci.db"
SYNC_DB_PATH = SYNC_DIR / "learningci.db"
PLAN_DIR = REPO_ROOT / "plans" / "nebularpc"
DEFAULT_PLAN_PATH = PLAN_DIR / "plan.json"
DEFAULT_BUNDLE_DIR = PLAN_DIR / "节点执行包"
MASTER_PLAN_PATH = PLAN_DIR / "NebulaRPC总计划.md"
REFINE_EXPORT_DIR = PLAN_DIR / "导出" / "节点细化"
REFINE_PROPOSED_DIR = PLAN_DIR / "待审核"
APP_NAME = "LearningCI"
APP_VERSION = "0.3.4"


def ensure_dirs() -> None:
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    SYNC_DIR.mkdir(parents=True, exist_ok=True)
    DEFAULT_BUNDLE_DIR.mkdir(parents=True, exist_ok=True)
    REFINE_EXPORT_DIR.mkdir(parents=True, exist_ok=True)
    REFINE_PROPOSED_DIR.mkdir(parents=True, exist_ok=True)


def prepare_local_database() -> bool:
    """If local DB is missing but a Git-tracked snapshot exists, restore it before opening SQLite."""
    ensure_dirs()
    if not DB_PATH.exists() and SYNC_DB_PATH.exists() and SYNC_DB_PATH.stat().st_size > 0:
        shutil.copy2(SYNC_DB_PATH, DB_PATH)
        return True
    return False
