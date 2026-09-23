from __future__ import annotations

import sqlite3
from contextlib import contextmanager
from pathlib import Path
from typing import Iterator

SCHEMA_VERSION = 6

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
    execution_mode TEXT NOT NULL DEFAULT 'BUILD',
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

CREATE TABLE IF NOT EXISTS node_bundles (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    node_id INTEGER NOT NULL UNIQUE REFERENCES nodes(id) ON DELETE CASCADE,
    bundle_hash TEXT NOT NULL,
    bundle_json TEXT NOT NULL,
    source_path TEXT NOT NULL,
    imported_at TEXT NOT NULL,
    bundle_state TEXT NOT NULL DEFAULT 'GENERATED',
    revision INTEGER NOT NULL DEFAULT 1,
    updated_at TEXT
);

CREATE TABLE IF NOT EXISTS assessment_papers (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    node_id INTEGER NOT NULL REFERENCES nodes(id) ON DELETE CASCADE,
    paper_code TEXT NOT NULL UNIQUE,
    paper_kind TEXT NOT NULL,
    paper_version INTEGER NOT NULL DEFAULT 1,
    paper_hash TEXT NOT NULL,
    paper_json TEXT NOT NULL,
    source_bundle_hash TEXT,
    created_at TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_papers_node_kind ON assessment_papers(node_id, paper_kind);

-- v0.1.x coarse task progress kept for backward compatibility/history.
CREATE TABLE IF NOT EXISTS task_progress (
    day TEXT NOT NULL,
    node_id INTEGER NOT NULL REFERENCES nodes(id) ON DELETE CASCADE,
    task_index INTEGER NOT NULL,
    completed INTEGER NOT NULL DEFAULT 0,
    completed_at TEXT,
    PRIMARY KEY(day, node_id, task_index)
);

CREATE TABLE IF NOT EXISTS leaf_task_progress (
    node_id INTEGER NOT NULL REFERENCES nodes(id) ON DELETE CASCADE,
    task_code TEXT NOT NULL,
    completed INTEGER NOT NULL DEFAULT 0,
    completed_at TEXT,
    source_path TEXT NOT NULL DEFAULT '',
    function_name TEXT NOT NULL DEFAULT '',
    evidence_note TEXT NOT NULL DEFAULT '',
    total_seconds INTEGER NOT NULL DEFAULT 0,
    first_started_at TEXT,
    updated_at TEXT NOT NULL,
    PRIMARY KEY(node_id, task_code)
);
CREATE INDEX IF NOT EXISTS idx_leaf_tasks_node ON leaf_task_progress(node_id, completed);

CREATE TABLE IF NOT EXISTS section_assessments (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    node_id INTEGER NOT NULL REFERENCES nodes(id) ON DELETE CASCADE,
    group_id TEXT NOT NULL,
    attempt_no INTEGER NOT NULL,
    understanding INTEGER NOT NULL,
    evidence INTEGER NOT NULL,
    boundary INTEGER NOT NULL,
    completeness INTEGER NOT NULL,
    total INTEGER NOT NULL,
    passed INTEGER NOT NULL,
    evidence_hash TEXT NOT NULL,
    grade_json TEXT NOT NULL,
    created_at TEXT NOT NULL,
    UNIQUE(node_id, group_id, attempt_no)
);
CREATE INDEX IF NOT EXISTS idx_section_assessments_node_group
    ON section_assessments(node_id, group_id, id);

CREATE TABLE IF NOT EXISTS focus_sessions (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    node_id INTEGER NOT NULL REFERENCES nodes(id),
    started_at TEXT NOT NULL,
    ended_at TEXT,
    duration_seconds INTEGER,
    created_at TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_focus_started ON focus_sessions(started_at);

CREATE TABLE IF NOT EXISTS task_focus_sessions (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    node_id INTEGER NOT NULL REFERENCES nodes(id) ON DELETE CASCADE,
    task_code TEXT NOT NULL,
    started_at TEXT NOT NULL,
    ended_at TEXT,
    duration_seconds INTEGER,
    created_at TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_task_focus_active ON task_focus_sessions(ended_at, node_id);

CREATE TABLE IF NOT EXISTS daily_progress_snapshots (
    day TEXT NOT NULL,
    node_id INTEGER NOT NULL REFERENCES nodes(id) ON DELETE CASCADE,
    done_required INTEGER NOT NULL,
    total_required INTEGER NOT NULL,
    completion_pct INTEGER NOT NULL,
    updated_at TEXT NOT NULL,
    PRIMARY KEY(day, node_id)
);

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
    issues_json TEXT NOT NULL DEFAULT '[]',
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
        self._migrate_schema()
        self.conn.execute(
            "INSERT INTO app_meta(key,value) VALUES('schema_version',?) "
            "ON CONFLICT(key) DO UPDATE SET value=excluded.value",
            (str(SCHEMA_VERSION),),
        )
        self.conn.commit()

    def _migrate_schema(self) -> None:
        """Idempotent lightweight migrations for existing v0.2.x databases."""
        columns = {row[1] for row in self.conn.execute("PRAGMA table_info(node_bundles)").fetchall()}
        if "bundle_state" not in columns:
            self.conn.execute("ALTER TABLE node_bundles ADD COLUMN bundle_state TEXT NOT NULL DEFAULT 'GENERATED'")
        if "revision" not in columns:
            self.conn.execute("ALTER TABLE node_bundles ADD COLUMN revision INTEGER NOT NULL DEFAULT 1")
        if "updated_at" not in columns:
            self.conn.execute("ALTER TABLE node_bundles ADD COLUMN updated_at TEXT")

        node_columns = {row[1] for row in self.conn.execute("PRAGMA table_info(nodes)").fetchall()}
        if "execution_mode" not in node_columns:
            self.conn.execute("ALTER TABLE nodes ADD COLUMN execution_mode TEXT NOT NULL DEFAULT 'BUILD'")

        score_columns = {row[1] for row in self.conn.execute("PRAGMA table_info(score_records)").fetchall()}
        if "issues_json" not in score_columns:
            self.conn.execute("ALTER TABLE score_records ADD COLUMN issues_json TEXT NOT NULL DEFAULT '[]'")

        # v0.2.0 already stored compiler.status inside bundle_json. Promote that state into
        # a dedicated column once so future generated bundles remain replaceable until frozen.
        rows = self.conn.execute(
            "SELECT id,bundle_json,bundle_state,updated_at,imported_at FROM node_bundles"
        ).fetchall()
        import json
        for row in rows:
            state = row["bundle_state"] or "GENERATED"
            if state == "GENERATED":
                try:
                    data = json.loads(row["bundle_json"])
                    raw = str(data.get("compiler", {}).get("status", "GENERATED")).upper()
                    if raw in {"REVIEWED", "FROZEN"}:
                        state = raw
                except Exception:
                    pass
            self.conn.execute(
                "UPDATE node_bundles SET bundle_state=?, updated_at=COALESCE(updated_at,imported_at) WHERE id=?",
                (state, row["id"]),
            )

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

    def backup_to(self, target: Path) -> Path:
        """Create/update a consistent SQLite snapshot while the app is open.

        Do not copy the live database file with shutil/copy: the live DB may be in WAL
        mode and committed pages can still live in ``learningci.db-wal``.  Instead, let
        SQLite copy a transactionally consistent view directly into the destination
        database.

        Writing directly to ``target`` also avoids the old Windows-only failure where
        we created ``*.tmp`` and then tried to unlink/replace an existing
        ``sync/learningci.db`` while another process briefly held a file handle.
        """
        target = Path(target)
        target.parent.mkdir(parents=True, exist_ok=True)

        self.conn.commit()
        # SQLite backup can overwrite an existing destination database safely; no
        # filesystem unlink/rename is necessary.  A normal reader may keep the file
        # open and SQLite will coordinate through database locks instead of Windows
        # delete-sharing semantics.
        with sqlite3.connect(target, timeout=10.0) as dst:
            dst.execute("PRAGMA busy_timeout=10000")
            self.conn.backup(dst)
            dst.execute("PRAGMA journal_mode=DELETE")
            dst.commit()

            ok = dst.execute("PRAGMA integrity_check").fetchone()[0]
            if ok != "ok":
                raise RuntimeError(f"同步快照 integrity_check 失败: {ok}")

        return target

    def restore_from(self, source: Path) -> None:
        """Restore a snapshot into the live local database connection."""
        source = Path(source)
        if not source.exists():
            raise FileNotFoundError(source)
        with sqlite3.connect(source) as src:
            src.row_factory = sqlite3.Row
            ok = src.execute("PRAGMA integrity_check").fetchone()[0]
            if ok != "ok":
                raise RuntimeError(f"同步快照 integrity_check 失败: {ok}")
            if not src.execute("SELECT 1 FROM sqlite_master WHERE type='table' AND name='plans'").fetchone():
                raise RuntimeError("同步快照不是有效的 LearningCI 数据库：缺少 plans 表")
            src.backup(self.conn)
        self.conn.execute("PRAGMA foreign_keys = ON")
        self.conn.commit()

    def integrity_check(self) -> str:
        return str(self.conn.execute("PRAGMA integrity_check").fetchone()[0])
