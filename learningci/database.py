from __future__ import annotations

import sqlite3
from contextlib import contextmanager
from pathlib import Path
from typing import Iterator


SCHEMA_SQL = r"""
PRAGMA foreign_keys = ON;

CREATE TABLE IF NOT EXISTS app_meta (
    key TEXT PRIMARY KEY,
    value TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS plans (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    plan_code TEXT NOT NULL UNIQUE,
    name TEXT NOT NULL,
    version TEXT NOT NULL,
    plan_hash TEXT NOT NULL,
    source_path TEXT NOT NULL,
    imported_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS nodes (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    plan_id INTEGER NOT NULL REFERENCES plans(id) ON DELETE CASCADE,
    node_code TEXT NOT NULL UNIQUE,
    stage TEXT NOT NULL,
    order_index INTEGER NOT NULL,
    title TEXT NOT NULL,
    capability TEXT NOT NULL,
    priority TEXT NOT NULL DEFAULT 'CORE',
    target_score INTEGER NOT NULL DEFAULT 80,
    status TEXT NOT NULL DEFAULT 'READY',
    tasks_json TEXT NOT NULL,
    must_learn_json TEXT NOT NULL,
    out_of_scope_json TEXT NOT NULL,
    scoring_json TEXT NOT NULL,
    project_anchor_json TEXT NOT NULL,
    current_score INTEGER,
    best_score INTEGER,
    stable_score INTEGER,
    first_pass_at TEXT,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_nodes_plan_order ON nodes(plan_id, order_index);

CREATE TABLE IF NOT EXISTS task_progress (
    day TEXT NOT NULL,
    node_id INTEGER NOT NULL REFERENCES nodes(id) ON DELETE CASCADE,
    task_index INTEGER NOT NULL,
    completed INTEGER NOT NULL DEFAULT 0,
    completed_at TEXT,
    PRIMARY KEY(day, node_id, task_index)
);

CREATE TABLE IF NOT EXISTS focus_sessions (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    node_id INTEGER NOT NULL REFERENCES nodes(id),
    started_at TEXT NOT NULL,
    ended_at TEXT,
    duration_seconds INTEGER,
    created_at TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_focus_started ON focus_sessions(started_at);

CREATE TABLE IF NOT EXISTS attempts (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    node_id INTEGER NOT NULL REFERENCES nodes(id),
    review_id INTEGER,
    attempt_no INTEGER NOT NULL,
    attempt_kind TEXT NOT NULL DEFAULT 'VERIFICATION',
    test_json TEXT NOT NULL,
    answer_text TEXT NOT NULL DEFAULT '',
    status TEXT NOT NULL DEFAULT 'OPEN',
    created_at TEXT NOT NULL,
    graded_at TEXT
);

CREATE TABLE IF NOT EXISTS score_records (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    attempt_id INTEGER NOT NULL UNIQUE REFERENCES attempts(id) ON DELETE CASCADE,
    node_id INTEGER NOT NULL REFERENCES nodes(id),
    score_day TEXT NOT NULL,
    explanation INTEGER NOT NULL,
    prediction INTEGER NOT NULL,
    implementation INTEGER NOT NULL,
    diagnosis INTEGER NOT NULL,
    transfer INTEGER NOT NULL,
    total INTEGER NOT NULL,
    passed INTEGER NOT NULL,
    evidence_json TEXT NOT NULL,
    weaknesses_json TEXT NOT NULL,
    created_at TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_scores_node ON score_records(node_id, created_at);
CREATE INDEX IF NOT EXISTS idx_scores_day ON score_records(score_day);

CREATE TABLE IF NOT EXISTS reviews (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    node_id INTEGER NOT NULL REFERENCES nodes(id) ON DELETE CASCADE,
    review_type TEXT NOT NULL,
    due_date TEXT NOT NULL,
    status TEXT NOT NULL DEFAULT 'PENDING',
    source_score_id INTEGER REFERENCES score_records(id),
    completed_attempt_id INTEGER REFERENCES attempts(id),
    created_at TEXT NOT NULL,
    UNIQUE(node_id, review_type, due_date)
);
CREATE INDEX IF NOT EXISTS idx_reviews_due ON reviews(status, due_date);

CREATE TABLE IF NOT EXISTS parking_lot (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    content TEXT NOT NULL,
    source_node_id INTEGER REFERENCES nodes(id),
    status TEXT NOT NULL DEFAULT 'PENDING',
    created_at TEXT NOT NULL,
    reviewed_at TEXT
);
"""


class Database:
    def __init__(self, path: Path):
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.conn = sqlite3.connect(self.path)
        self.conn.row_factory = sqlite3.Row
        self.conn.execute("PRAGMA foreign_keys = ON")

    def initialize(self) -> None:
        self.conn.executescript(SCHEMA_SQL)
        self.conn.commit()

    def close(self) -> None:
        self.conn.close()

    @contextmanager
    def transaction(self) -> Iterator[sqlite3.Connection]:
        try:
            yield self.conn
            self.conn.commit()
        except Exception:
            self.conn.rollback()
            raise
