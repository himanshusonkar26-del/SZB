from __future__ import annotations

import re
import secrets
from pathlib import Path

from cryptography.fernet import Fernet
from loguru import logger

from himan.config import DATA_DIR, LOG_DIR, MASTER_KEY_FILE, ensure_dirs, settings

SECRET_PATTERNS = [
    re.compile(r"gsk_[A-Za-z0-9]+"),
    re.compile(r"sk-[A-Za-z0-9]+"),
    re.compile(r"(?i)(api[_-]?key|password|passwd|secret|token)\s*[:=]\s*\S+"),
]


def redact(text: str) -> str:
    if not text:
        return text
    out = text
    for pat in SECRET_PATTERNS:
        out = pat.sub("[REDACTED]", out)
    return out


class RedactingSink:
    def write(self, message: str) -> None:
        print(redact(message), end="")


def setup_logging() -> None:
    ensure_dirs()
    logger.remove()
    logger.add(RedactingSink(), level=settings.log_level)
    logger.add(str(LOG_DIR / "himan.log"), rotation="2 MB", retention=8, level=settings.log_level)


def get_fernet() -> Fernet:
    ensure_dirs()
    if not MASTER_KEY_FILE.exists():
        MASTER_KEY_FILE.write_bytes(Fernet.generate_key())
        try:
            MASTER_KEY_FILE.chmod(0o600)
        except OSError:
            pass
    return Fernet(MASTER_KEY_FILE.read_bytes())


def encrypt_text(plain: str) -> bytes:
    return get_fernet().encrypt(plain.encode("utf-8"))


def decrypt_text(token: bytes) -> str:
    return get_fernet().decrypt(token).decode("utf-8")


def safe_job_text(text: str) -> str:
    cleaned = (text or "").strip()
    if len(cleaned) > settings.max_job_chars:
        raise ValueError(f"Job text too long (max {settings.max_job_chars} chars).")
    return cleaned


def is_within_data(path: Path) -> bool:
    try:
        path.resolve().relative_to(DATA_DIR.resolve())
        return True
    except ValueError:
        return False


def new_id(prefix: str) -> str:
    return f"{prefix}_{secrets.token_hex(4)}"
