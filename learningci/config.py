from __future__ import annotations

import os
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parent.parent
DATA_DIR = Path(os.environ.get("LEARNINGCI_DATA_DIR", REPO_ROOT / "data"))
DB_PATH = DATA_DIR / "learningci.db"
DEFAULT_PLAN_PATH = REPO_ROOT / "plans" / "nebularpc" / "plan.json"
APP_NAME = "LearningCI"
APP_VERSION = "0.1.1"


def ensure_data_dir() -> None:
    DATA_DIR.mkdir(parents=True, exist_ok=True)
