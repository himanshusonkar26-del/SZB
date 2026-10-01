"""
HIMAN Telegram Alerts
=====================
Tumhe Telegram pe saari important notifications aati hain.
"""

from __future__ import annotations

import httpx
from loguru import logger

from himan.config import settings
from himan.security import redact


def _send(text: str) -> None:
    """Raw message bhejo Telegram pe."""
    if not settings.telegram_ready:
        return
    body = redact(text)[:4000]
    url = f"https://api.telegram.org/bot{settings.telegram_bot_token}/sendMessage"
    try:
        httpx.post(
            url,
            json={
                "chat_id": settings.telegram_chat_id,
                "text": body,
                "parse_mode": "HTML",
            },
            timeout=15,
        )
    except Exception as exc:
        logger.warning("Telegram notify failed: {}", type(exc).__name__)


def notify(text: str) -> None:
    """General notification."""
    _send(f"🤖 HIMAN\n{text}")


def notify_new_job(title: str, score: int, reason: str, url: str = "") -> None:
    """Naya shortlisted job mila."""
    msg = (
        f"🔍 <b>Naya Job Mila!</b>\n"
        f"📋 {title}\n"
        f"⭐ Score: {score}/100\n"
        f"💡 {reason}"
    )
    if url:
        msg += f"\n🔗 {url}"
    _send(msg)


def notify_draft_ready(job_id: str, title: str) -> None:
    """Draft ready hai review ke liye."""
    _send(
        f"✅ <b>Draft Ready!</b>\n"
        f"🆔 {job_id}\n"
        f"📋 {title}\n"
        f"👉 Dashboard pe review karo phir khud submit karo."
    )


def notify_job_blocked(job_id: str, reason: str) -> None:
    """Dangerous job block hua."""
    _send(
        f"🚫 <b>Job Blocked</b>\n"
        f"🆔 {job_id}\n"
        f"⚠️ Reason: {reason}"
    )


def notify_job_failed(job_id: str, title: str) -> None:
    """Job 3 baar fail hua QC mein."""
    _send(
        f"❌ <b>Job Failed QC</b>\n"
        f"🆔 {job_id}\n"
        f"📋 {title}\n"
        f"👉 Tumhara review chahiye."
    )


def notify_earning(amount: float, note: str = "") -> None:
    """Payment log hua."""
    msg = f"💰 <b>Earning Logged!</b>\n${amount:.2f}"
    if note:
        msg += f"\n📝 {note}"
    _send(msg)


def notify_emergency_stop(reason: str) -> None:
    """Emergency stop laga."""
    _send(f"🛑 <b>HIMAN STOPPED</b>\nReason: {reason}")


def notify_system_started() -> None:
    """HIMAN start hua."""
    _send("🚀 <b>HIMAN Pro Started!</b>\nSystem ready hai. Dashboard: http://localhost:8501")


def notify_weekly_report(report: str) -> None:
    """Weekly self-report bhejo."""
    _send(f"📊 <b>HIMAN Weekly Report</b>\n\n{report[:3000]}")


def notify_search_summary(total: int, shortlisted: int) -> None:
    """Search complete hua."""
    _send(
        f"🔍 <b>Search Complete</b>\n"
        f"Total jobs found: {total}\n"
        f"Shortlisted: {shortlisted}\n"
        f"👉 Dashboard pe dekho."
    )
