from __future__ import annotations

import json
import sqlite3
from contextlib import contextmanager
from datetime import datetime, timezone
from typing import Any, Iterator

from himan.config import DB_PATH, ensure_dirs

SCHEMA = """
CREATE TABLE IF NOT EXISTS jobs (
    id TEXT PRIMARY KEY,
    title TEXT NOT NULL,
    description TEXT NOT NULL,
    budget TEXT,
    source_note TEXT,
    status TEXT NOT NULL,
    safety_level TEXT,
    safety_json TEXT,
    agent_kind TEXT,
    draft TEXT,
    qc_notes TEXT,
    retries INTEGER DEFAULT 0,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS agents (
    kind TEXT PRIMARY KEY,
    label TEXT NOT NULL,
    jobs_done INTEGER DEFAULT 0,
    jobs_failed INTEGER DEFAULT 0,
    score REAL DEFAULT 50
);

CREATE TABLE IF NOT EXISTS audit (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    at TEXT NOT NULL,
    action TEXT NOT NULL,
    job_id TEXT,
    detail TEXT
);

CREATE TABLE IF NOT EXISTS earnings (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    at TEXT NOT NULL,
    amount_usd REAL NOT NULL,
    note TEXT
);
"""

DEFAULT_AGENTS = [
    ("dev", "Dev Agent"),
    ("writer", "Writer Agent"),
    ("data", "Data Agent"),
    ("design", "Design Agent"),
    ("marketing", "Marketing Agent"),
]


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


@contextmanager
def connect() -> Iterator[sqlite3.Connection]:
    ensure_dirs()
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    try:
        yield conn
        conn.commit()
    finally:
        conn.close()


def init_db() -> None:
    with connect() as conn:
        conn.executescript(SCHEMA)
        for kind, label in DEFAULT_AGENTS:
            conn.execute(
                "INSERT OR IGNORE INTO agents(kind, label) VALUES (?, ?)",
                (kind, label),
            )


def audit(action: str, job_id: str | None = None, detail: str = "") -> None:
    with connect() as conn:
        conn.execute(
            "INSERT INTO audit(at, action, job_id, detail) VALUES (?, ?, ?, ?)",
            (_now(), action, job_id, detail[:2000]),
        )


def insert_job(job: dict[str, Any]) -> None:
    now = _now()
    with connect() as conn:
        conn.execute(
            """INSERT INTO jobs(id, title, description, budget, source_note, status,
               safety_level, safety_json, agent_kind, draft, qc_notes, retries, created_at, updated_at)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (
                job["id"],
                job["title"],
                job["description"],
                job.get("budget") or "",
                job.get("source_note") or "",
                job["status"],
                job.get("safety_level") or "",
                json.dumps(job.get("safety") or {}),
                job.get("agent_kind"),
                job.get("draft") or "",
                job.get("qc_notes") or "",
                job.get("retries") or 0,
                now,
                now,
            ),
        )


def update_job(job_id: str, **fields: Any) -> None:
    if not fields:
        return
    fields["updated_at"] = _now()
    if "safety" in fields:
        fields["safety_json"] = json.dumps(fields.pop("safety"))
    keys = ", ".join(f"{k}=?" for k in fields)
    vals = list(fields.values()) + [job_id]
    with connect() as conn:
        conn.execute(f"UPDATE jobs SET {keys} WHERE id=?", vals)


def get_job(job_id: str) -> dict[str, Any] | None:
    with connect() as conn:
        row = conn.execute("SELECT * FROM jobs WHERE id=?", (job_id,)).fetchone()
    return dict(row) if row else None


def list_jobs(limit: int = 50) -> list[dict[str, Any]]:
    with connect() as conn:
        rows = conn.execute(
            "SELECT * FROM jobs ORDER BY created_at DESC LIMIT ?", (limit,)
        ).fetchall()
    return [dict(r) for r in rows]


def list_agents() -> list[dict[str, Any]]:
    with connect() as conn:
        rows = conn.execute("SELECT * FROM agents ORDER BY kind").fetchall()
    return [dict(r) for r in rows]


def bump_agent(kind: str, success: bool) -> None:
    with connect() as conn:
        if success:
            conn.execute(
                "UPDATE agents SET jobs_done=jobs_done+1, score=MIN(100, score+2) WHERE kind=?",
                (kind,),
            )
        else:
            conn.execute(
                "UPDATE agents SET jobs_failed=jobs_failed+1, score=MAX(0, score-3) WHERE kind=?",
                (kind,),
            )


def add_earning(amount_usd: float, note: str = "") -> None:
    with connect() as conn:
        conn.execute(
            "INSERT INTO earnings(at, amount_usd, note) VALUES (?, ?, ?)",
            (_now(), amount_usd, note),
        )


def month_earnings() -> float:
    with connect() as conn:
        row = conn.execute(
            "SELECT COALESCE(SUM(amount_usd), 0) AS t FROM earnings"
        ).fetchone()
    return float(row["t"] if row else 0)


def recent_audit(limit: int = 40) -> list[dict[str, Any]]:
    with connect() as conn:
        rows = conn.execute(
            "SELECT * FROM audit ORDER BY id DESC LIMIT ?", (limit,)
        ).fetchall()
    return [dict(r) for r in rows]
