"""
HIMAN Reporter — Daily / Weekly / Monthly Reports
==================================================
Ek report banata hai jisme:
- Kitni jobs mili
- Kitni bids ki
- Kitna earn kiya
- Best performing agent
- Conversion rate
- Next steps

Report save hoti hai:
  data/reports/daily_YYYY-MM-DD.txt
  data/reports/weekly_YYYY-WXX.txt
  data/reports/monthly_YYYY-MM.txt
"""

from __future__ import annotations

import os
import sqlite3
from datetime import datetime, timezone, timedelta, date
from pathlib import Path
from typing import Optional

ROOT = Path(__file__).resolve().parent
REPORTS_DIR = ROOT / "data" / "reports"
DB_PATH = ROOT / "data" / "himan.db"


def _conn():
    conn = sqlite3.connect(str(DB_PATH))
    conn.row_factory = sqlite3.Row
    return conn


def _ensure_reports_dir():
    REPORTS_DIR.mkdir(parents=True, exist_ok=True)


# ─── DATA FETCHERS ────────────────────────────────────────────────────────────

def _jobs_in_range(start: str, end: str) -> list[sqlite3.Row]:
    with _conn() as c:
        return c.execute(
            "SELECT * FROM jobs WHERE created_at >= ? AND created_at < ?",
            (start, end)
        ).fetchall()


def _earnings_in_range(start: str, end: str) -> float:
    with _conn() as c:
        row = c.execute(
            "SELECT COALESCE(SUM(amount_usd), 0) FROM earnings WHERE at >= ? AND at < ?",
            (start, end)
        ).fetchone()
    return float(row[0])


def _bids_in_range(start: str, end: str) -> list[sqlite3.Row]:
    with _conn() as c:
        return c.execute(
            "SELECT * FROM bids WHERE bid_at >= ? AND bid_at < ?",
            (start, end)
        ).fetchall()


def _agent_stats_in_range(start: str, end: str) -> dict:
    """Job type se count nikalo."""
    with _conn() as c:
        rows = c.execute(
            "SELECT agent_kind, COUNT(*) as cnt FROM jobs "
            "WHERE created_at >= ? AND created_at < ? GROUP BY agent_kind ORDER BY cnt DESC",
            (start, end)
        ).fetchall()
    return {r["agent_kind"]: r["cnt"] for r in rows}


def _submitted_in_range(start: str, end: str) -> int:
    with _conn() as c:
        row = c.execute(
            "SELECT COUNT(*) FROM jobs WHERE status='submitted' AND updated_at >= ? AND updated_at < ?",
            (start, end)
        ).fetchone()
    return int(row[0])


def _total_jobs() -> int:
    with _conn() as c:
        return int(c.execute("SELECT COUNT(*) FROM jobs").fetchone()[0])


def _total_submitted() -> int:
    with _conn() as c:
        return int(c.execute("SELECT COUNT(*) FROM jobs WHERE status='submitted'").fetchone()[0])


def _total_earnings() -> float:
    with _conn() as c:
        row = c.execute("SELECT COALESCE(SUM(amount_usd), 0) FROM earnings").fetchone()
    return float(row[0])


# ─── REPORT BUILDERS ─────────────────────────────────────────────────────────

def _build_report(title: str, start: str, end: str, period_label: str) -> str:
    """Ek period ka report build karo."""
    now_str = datetime.now().strftime("%d %b %Y %H:%M")

    jobs = _jobs_in_range(start, end)
    earnings = _earnings_in_range(start, end)
    bids_placed = _submitted_in_range(start, end)
    agent_stats = _agent_stats_in_range(start, end)

    total_jobs_found = len(jobs)
    ready_jobs = [j for j in jobs if j["status"] == "ready"]
    skipped_jobs = [j for j in jobs if j["status"] == "skipped"]
    submitted_jobs = [j for j in jobs if j["status"] == "submitted"]

    # Conversion rate
    if total_jobs_found > 0:
        conv_rate = (bids_placed / total_jobs_found) * 100
    else:
        conv_rate = 0.0

    # Best agent
    best_agent = max(agent_stats, key=agent_stats.get) if agent_stats else "N/A"
    best_agent_icon = {"dev": "💻", "writer": "✍️", "data": "📊", "design": "🎨", "marketing": "📣"}.get(best_agent, "🤖")

    # All time totals
    all_jobs = _total_jobs()
    all_submitted = _total_submitted()
    all_earnings = _total_earnings()

    # ── Report Text ─────────────────────────────────────────────────────
    lines = []
    lines.append("=" * 60)
    lines.append(f"  HIMAN AI — {title}")
    lines.append(f"  Generated: {now_str}")
    lines.append("=" * 60)
    lines.append("")

    lines.append(f"📅 Period: {period_label}")
    lines.append("")

    lines.append("─" * 40)
    lines.append("  📊 IS PERIOD KA SUMMARY")
    lines.append("─" * 40)
    lines.append(f"  🔍 Jobs Dhundhe:     {total_jobs_found}")
    lines.append(f"  ✅ Bids Ki (Manual): {bids_placed}")
    lines.append(f"  ⚡ Ready (Pending):  {len(ready_jobs)}")
    lines.append(f"  ⏭️  Skipped:          {len(skipped_jobs)}")
    lines.append(f"  📈 Conversion Rate:  {conv_rate:.1f}%")
    lines.append(f"  💰 Earnings:         ${earnings:.2f}")
    lines.append("")

    lines.append("─" * 40)
    lines.append("  🤖 AGENT BREAKDOWN")
    lines.append("─" * 40)
    agent_icons = {"dev": "💻", "writer": "✍️", "data": "📊", "design": "🎨", "marketing": "📣"}
    for agent, count in sorted(agent_stats.items(), key=lambda x: -x[1]):
        icon = agent_icons.get(agent, "🤖")
        bar = "█" * min(count, 20)
        lines.append(f"  {icon} {agent.title():12s}: {count:3d}  {bar}")
    if agent_stats:
        lines.append(f"\n  🏆 Best Agent: {best_agent_icon} {best_agent.title()}")
    lines.append("")

    if submitted_jobs:
        lines.append("─" * 40)
        lines.append("  📝 BIDS KI GAYI JOBS (Last 10)")
        lines.append("─" * 40)
        for j in list(submitted_jobs)[-10:]:
            bgt = j["budget"] or "N/A"
            lines.append(f"  • {j['title'][:50]:<50s}  [{bgt}]")
        lines.append("")

    lines.append("─" * 40)
    lines.append("  📦 ALL TIME TOTALS")
    lines.append("─" * 40)
    lines.append(f"  Total Jobs:      {all_jobs}")
    lines.append(f"  Total Bids:      {all_submitted}")
    lines.append(f"  Total Earnings:  ${all_earnings:.2f}")
    if all_submitted > 0:
        all_conv = (all_submitted / all_jobs * 100) if all_jobs > 0 else 0
        lines.append(f"  Overall Conv:    {all_conv:.1f}%")
    lines.append("")

    lines.append("─" * 40)
    lines.append("  🎯 NEXT STEPS")
    lines.append("─" * 40)
    if len(ready_jobs) > 0:
        lines.append(f"  ⚡ {len(ready_jobs)} jobs BID READY hain — abhi bid karo!")
        lines.append(f"     Dashboard: http://localhost:8501")
    if earnings == 0:
        lines.append("  💡 Paise tab aayenge jab manually Freelancer pe bid karoge.")
        lines.append("  💡 Har din 5-10 bids karo — results 1-2 hafte mein aate hain.")
    else:
        lines.append(f"  🎉 Is period mein ${earnings:.2f} kamaye — achha kaam!")
    lines.append("")

    lines.append("=" * 60)
    lines.append("  HIMAN — Har kaam mein best hoon 💪")
    lines.append("=" * 60)

    return "\n".join(lines)


# ─── PUBLIC API ───────────────────────────────────────────────────────────────

def generate_daily_report(target_date: Optional[date] = None) -> tuple[str, str]:
    """
    Aaj ka report generate karo.
    Returns: (report_text, file_path)
    """
    _ensure_reports_dir()
    d = target_date or date.today()
    start = datetime(d.year, d.month, d.day, 0, 0, 0, tzinfo=timezone.utc).isoformat()
    end   = datetime(d.year, d.month, d.day, 23, 59, 59, tzinfo=timezone.utc).isoformat()
    period_label = d.strftime("%A, %d %B %Y")

    report = _build_report(
        title=f"DAILY REPORT — {d.strftime('%d %b %Y')}",
        start=start,
        end=end,
        period_label=period_label,
    )

    fname = REPORTS_DIR / f"daily_{d.isoformat()}.txt"
    fname.write_text(report, encoding="utf-8")
    return report, str(fname)


def generate_weekly_report(target_date: Optional[date] = None) -> tuple[str, str]:
    """
    Is hafte ka report generate karo (Monday to Sunday).
    Returns: (report_text, file_path)
    """
    _ensure_reports_dir()
    d = target_date or date.today()
    # Monday of this week
    monday = d - timedelta(days=d.weekday())
    sunday = monday + timedelta(days=6)

    start = datetime(monday.year, monday.month, monday.day, 0, 0, 0, tzinfo=timezone.utc).isoformat()
    end   = datetime(sunday.year, sunday.month, sunday.day, 23, 59, 59, tzinfo=timezone.utc).isoformat()

    week_num = monday.isocalendar()[1]
    period_label = f"{monday.strftime('%d %b')} – {sunday.strftime('%d %b %Y')} (Week {week_num})"

    report = _build_report(
        title=f"WEEKLY REPORT — Week {week_num}, {monday.year}",
        start=start,
        end=end,
        period_label=period_label,
    )

    fname = REPORTS_DIR / f"weekly_{monday.year}-W{week_num:02d}.txt"
    fname.write_text(report, encoding="utf-8")
    return report, str(fname)


def generate_monthly_report(target_date: Optional[date] = None) -> tuple[str, str]:
    """
    Is mahine ka report generate karo.
    Returns: (report_text, file_path)
    """
    _ensure_reports_dir()
    d = target_date or date.today()
    start = datetime(d.year, d.month, 1, 0, 0, 0, tzinfo=timezone.utc).isoformat()
    # Next month first day
    if d.month == 12:
        end_d = date(d.year + 1, 1, 1)
    else:
        end_d = date(d.year, d.month + 1, 1)
    end = datetime(end_d.year, end_d.month, end_d.day, 0, 0, 0, tzinfo=timezone.utc).isoformat()

    period_label = d.strftime("%B %Y")

    report = _build_report(
        title=f"MONTHLY REPORT — {d.strftime('%B %Y')}",
        start=start,
        end=end,
        period_label=period_label,
    )

    fname = REPORTS_DIR / f"monthly_{d.year}-{d.month:02d}.txt"
    fname.write_text(report, encoding="utf-8")
    return report, str(fname)


def get_quick_stats() -> dict:
    """Dashboard ke liye quick stats dict."""
    today = date.today()
    start_day  = datetime(today.year, today.month, today.day, 0, 0, 0, tzinfo=timezone.utc).isoformat()
    start_week = (datetime.now(timezone.utc) - timedelta(days=datetime.now().weekday())).replace(hour=0, minute=0, second=0, microsecond=0).isoformat()
    start_month= datetime(today.year, today.month, 1, 0, 0, 0, tzinfo=timezone.utc).isoformat()
    end        = datetime(today.year + 1, 1, 1, tzinfo=timezone.utc).isoformat()

    return {
        "today": {
            "jobs_found":  len(_jobs_in_range(start_day, end)),
            "bids_placed": _submitted_in_range(start_day, end),
            "earnings":    _earnings_in_range(start_day, end),
        },
        "week": {
            "jobs_found":  len(_jobs_in_range(start_week, end)),
            "bids_placed": _submitted_in_range(start_week, end),
            "earnings":    _earnings_in_range(start_week, end),
        },
        "month": {
            "jobs_found":  len(_jobs_in_range(start_month, end)),
            "bids_placed": _submitted_in_range(start_month, end),
            "earnings":    _earnings_in_range(start_month, end),
        },
        "all_time": {
            "jobs_found":  _total_jobs(),
            "bids_placed": _total_submitted(),
            "earnings":    _total_earnings(),
        },
    }


# ── Quick test ───────────────────────────────────────────────────────────────
if __name__ == "__main__":
    import sys
    sys.path.insert(0, str(ROOT))

    print("Generating reports...")
    text, path = generate_daily_report()
    # Print safely — ignore emoji encoding issues on Windows terminal
    safe_text = text.encode("ascii", errors="replace").decode("ascii")
    print(safe_text)
    print(f"\nSaved to: {path}")

    _, wpath = generate_weekly_report()
    print(f"Weekly: {wpath}")

    _, mpath = generate_monthly_report()
    print(f"Monthly: {mpath}")
    print("All reports generated OK!")
