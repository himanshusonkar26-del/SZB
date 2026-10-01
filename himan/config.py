from __future__ import annotations

import os
from pathlib import Path

from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parent.parent
load_dotenv(ROOT / ".env")

DATA_DIR = ROOT / "data"
LOG_DIR = ROOT / "logs"
STOP_FILE = DATA_DIR / "EMERGENCY_STOP"
MASTER_KEY_FILE = DATA_DIR / "master.key"
DB_PATH = DATA_DIR / "himan.db"


def _bool(name: str, default: bool = True) -> bool:
    raw = os.getenv(name)
    if raw is None:
        return default
    return raw.strip().lower() in {"1", "true", "yes", "on"}


class Settings:
    groq_api_key: str = os.getenv("GROQ_API_KEY", "").strip()
    groq_model: str = os.getenv("GROQ_MODEL", "qwen/qwen3.8-27b").strip()
    telegram_bot_token: str = os.getenv("TELEGRAM_BOT_TOKEN", "").strip()
    telegram_chat_id: str = os.getenv("TELEGRAM_CHAT_ID", "").strip()
    monthly_goal_usd: float = float(os.getenv("MONTHLY_GOAL_USD", "100") or 100)
    safety_enabled: bool = _bool("SAFETY_SYSTEM_ENABLED", True)
    max_agents: int = int(os.getenv("MAX_AGENTS", "6") or 6)
    max_retries: int = int(os.getenv("MAX_RETRY_ATTEMPTS", "3") or 3)
    dashboard_password: str = os.getenv("DASHBOARD_PASSWORD", "").strip()
    dashboard_port: int = int(os.getenv("DASHBOARD_PORT", "8501") or 8501)
    log_level: str = os.getenv("LOG_LEVEL", "INFO").strip().upper()
    max_job_chars: int = 20_000

    @property
    def groq_ready(self) -> bool:
        return bool(self.groq_api_key) and not self.groq_api_key.startswith("your_")

    @property
    def telegram_ready(self) -> bool:
        token = self.telegram_bot_token
        chat = self.telegram_chat_id
        if not token or not chat:
            return False
        if token.startswith("your_") or chat.startswith("your_"):
            return False
        return True


settings = Settings()


def ensure_dirs() -> None:
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    LOG_DIR.mkdir(parents=True, exist_ok=True)
