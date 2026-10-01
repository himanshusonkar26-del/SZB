from __future__ import annotations

from pathlib import Path

from himan.config import STOP_FILE, ensure_dirs


def is_stopped() -> bool:
    return STOP_FILE.exists()


def stop(reason: str = "manual") -> None:
    ensure_dirs()
    STOP_FILE.write_text(reason.strip() or "manual", encoding="utf-8")


def resume() -> None:
    if STOP_FILE.exists():
        STOP_FILE.unlink()


def status() -> str:
    if not is_stopped():
        return "running"
    reason = STOP_FILE.read_text(encoding="utf-8").strip()
    return f"STOPPED: {reason}"
