from __future__ import annotations

import json
import sqlite3
from contextlib import contextmanager
from datetime import datetime, date, timezone
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

CREATE TABLE IF NOT EXISTS bids (
    id TEXT PRIMARY KEY,
    job_id TEXT,
    job_title TEXT,
    platform TEXT,
    bid_amount REAL,
    bid_at TEXT NOT NULL,
    status TEXT DEFAULT 'pending',
    client_id TEXT,
    proposal TEXT,
    response_at TEXT,
    notes TEXT
);

CREATE TABLE IF NOT EXISTS daily_stats (
    date TEXT PRIMARY KEY,
    jobs_fetched INTEGER DEFAULT 0,
    bids_placed INTEGER DEFAULT 0,
    bids_won INTEGER DEFAULT 0,
    earnings REAL DEFAULT 0.0,
    best_agent TEXT DEFAULT '',
    notes TEXT DEFAULT ''
);

CREATE TABLE IF NOT EXISTS sources (
    name TEXT PRIMARY KEY,
    total_jobs INTEGER DEFAULT 0,
    last_fetched TEXT,
    active INTEGER DEFAULT 1
);

CREATE TABLE IF NOT EXISTS clients (
    id TEXT PRIMARY KEY,
    name TEXT,
    platform TEXT,
    email TEXT,
    total_paid REAL DEFAULT 0.0,
    jobs_completed INTEGER DEFAULT 0,
    rating REAL DEFAULT 0.0,
    notes TEXT,
    created_at TEXT
);

CREATE TABLE IF NOT EXISTS conversations (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    job_id TEXT,
    client_id TEXT,
    message TEXT,
    direction TEXT,
    at TEXT
);

CREATE TABLE IF NOT EXISTS skills (
    name TEXT PRIMARY KEY,
    jobs_count INTEGER DEFAULT 0,
    win_rate REAL DEFAULT 0.0
);

CREATE TABLE IF NOT EXISTS agent_memory (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    agent_kind TEXT,
    key TEXT,
    value TEXT,
    updated_at TEXT
);
"""

DEFAULT_AGENTS = [
    ("dev", "Dev Agent"),
    ("writer", "Writer Agent"),
    ("data", "Data Agent"),
    ("design", "Design Agent"),
    ("marketing", "Marketing Agent"),
]

DEFAULT_SOURCES = [
    ("Freelancer", "https://www.freelancer.com"),
    ("PeoplePerHour", "https://www.peopleperhour.com"),
    ("Guru", "https://www.guru.com"),
    ("Remotive", "https://remotive.com"),
]


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _today() -> str:
    return date.today().isoformat()


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
        for name, _ in DEFAULT_SOURCES:
            conn.execute(
                "INSERT OR IGNORE INTO sources(name, total_jobs, last_fetched) VALUES (?, 0, ?)",
                (name, _now()),
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


def list_jobs(limit: int = 50, status: str | None = None) -> list[dict[str, Any]]:
    with connect() as conn:
        if status:
            rows = conn.execute(
                "SELECT * FROM jobs WHERE status=? ORDER BY created_at DESC LIMIT ?",
                (status, limit)
            ).fetchall()
        else:
            rows = conn.execute(
                "SELECT * FROM jobs ORDER BY created_at DESC LIMIT ?", (limit,)
            ).fetchall()
    return [dict(r) for r in rows]


def list_agents() -> list[dict[str, Any]]:
    with connect() as conn:
        rows = conn.execute("SELECT * FROM agents ORDER BY jobs_done DESC").fetchall()
    return [dict(r) for r in rows]


def bump_agent(kind: str, success: bool) -> None:
    """Agent ka counter update karo — har job pe call karo."""
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
    # Also update daily stats
    update_daily_earnings(amount_usd)


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


# ─── DAILY STATS ──────────────────────────────────────────────────────────────

def upsert_daily_stats(jobs_fetched: int = 0, saved: int = 0) -> None:
    """Aaj ke stats update karo."""
    today = _today()
    with connect() as conn:
        existing = conn.execute(
            "SELECT date FROM daily_stats WHERE date=?", (today,)
        ).fetchone()

        if existing:
            conn.execute(
                """UPDATE daily_stats SET
                   jobs_fetched = jobs_fetched + ?,
                   notes = ?
                   WHERE date = ?""",
                (jobs_fetched, f"saved={saved}", today)
            )
        else:
            conn.execute(
                """INSERT INTO daily_stats(date, jobs_fetched, bids_placed, bids_won, earnings, best_agent, notes)
                   VALUES (?, ?, 0, 0, 0.0, '', ?)""",
                (today, jobs_fetched, f"saved={saved}")
            )


def update_daily_bid() -> None:
    """Jab bid karo tab call karo."""
    today = _today()
    with connect() as conn:
        conn.execute(
            """INSERT OR IGNORE INTO daily_stats(date, jobs_fetched, bids_placed, bids_won, earnings, best_agent, notes)
               VALUES (?, 0, 0, 0, 0.0, '', '')""",
            (today,)
        )
        conn.execute(
            "UPDATE daily_stats SET bids_placed = bids_placed + 1 WHERE date = ?",
            (today,)
        )


def update_daily_win(amount: float = 0.0) -> None:
    """Jab koi bid win ho tab call karo."""
    today = _today()
    with connect() as conn:
        conn.execute(
            """INSERT OR IGNORE INTO daily_stats(date, jobs_fetched, bids_placed, bids_won, earnings, best_agent, notes)
               VALUES (?, 0, 0, 0, 0.0, '', '')""",
            (today,)
        )
        conn.execute(
            """UPDATE daily_stats SET
               bids_won = bids_won + 1,
               earnings = earnings + ?
               WHERE date = ?""",
            (amount, today)
        )


def update_daily_earnings(amount: float) -> None:
    """Earnings log hone pe daily stats update."""
    today = _today()
    with connect() as conn:
        conn.execute(
            """INSERT OR IGNORE INTO daily_stats(date, jobs_fetched, bids_placed, bids_won, earnings, best_agent, notes)
               VALUES (?, 0, 0, 0, 0.0, '', '')""",
            (today,)
        )
        conn.execute(
            "UPDATE daily_stats SET earnings = earnings + ? WHERE date = ?",
            (amount, today)
        )


def get_daily_stats(days: int = 7) -> list[dict[str, Any]]:
    """Last N days ke stats."""
    with connect() as conn:
        rows = conn.execute(
            "SELECT * FROM daily_stats ORDER BY date DESC LIMIT ?", (days,)
        ).fetchall()
    return [dict(r) for r in rows]


# ─── BID TRACKING ─────────────────────────────────────────────────────────────

def record_bid(job_id: str, job_title: str, platform: str, bid_amount: float,
               proposal: str = "", notes: str = "") -> str:
    """Jab bid karo tab record karo."""
    from himan.security import new_id
    bid_id = new_id("bid")
    now = _now()
    with connect() as conn:
        conn.execute(
            """INSERT INTO bids(id, job_id, job_title, platform, bid_amount, bid_at, status, proposal, notes)
               VALUES (?, ?, ?, ?, ?, ?, 'pending', ?, ?)""",
            (bid_id, job_id, job_title, platform, bid_amount, now, proposal, notes)
        )
    update_daily_bid()
    return bid_id


def update_bid_status(bid_id: str, status: str, notes: str = "") -> None:
    """Bid ka status update karo — pending/won/lost/no_response."""
    with connect() as conn:
        conn.execute(
            "UPDATE bids SET status=?, response_at=?, notes=? WHERE id=?",
            (status, _now(), notes, bid_id)
        )


def get_bid_stats() -> dict[str, Any]:
    """Bid statistics."""
    with connect() as conn:
        total = conn.execute("SELECT COUNT(*) FROM bids").fetchone()[0]
        won = conn.execute("SELECT COUNT(*) FROM bids WHERE status='won'").fetchone()[0]
        pending = conn.execute("SELECT COUNT(*) FROM bids WHERE status='pending'").fetchone()[0]
        lost = conn.execute("SELECT COUNT(*) FROM bids WHERE status='lost'").fetchone()[0]
    win_rate = round((won / total * 100), 1) if total > 0 else 0
    return {
        "total": total,
        "won": won,
        "pending": pending,
        "lost": lost,
        "win_rate": win_rate,
    }


# ─── SOURCE TRACKING ──────────────────────────────────────────────────────────

def update_source_stats(platform: str, jobs_count: int) -> None:
    """Source ka stats update karo."""
    with connect() as conn:
        conn.execute(
            """INSERT OR IGNORE INTO sources(name, total_jobs, last_fetched)
               VALUES (?, 0, ?)""",
            (platform, _now())
        )
        conn.execute(
            """UPDATE sources SET
               total_jobs = total_jobs + ?,
               last_fetched = ?
               WHERE name = ?""",
            (jobs_count, _now(), platform)
        )
