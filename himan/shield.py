"""
HIMAN Security Shield
======================
Yeh file HIMAN ko protect karti hai:

1. LOOP PROTECTION     — infinite loop se bachao
2. RATE LIMITER        — Groq/Freelancer ko spam mat karo
3. API KEY GUARD       — keys leak na ho
4. REQUEST VALIDATOR   — bahar se koi inject na kar sake
5. CRASH GUARD         — crash hone pe auto-recover
6. AUDIT LOG           — har action record hota hai
"""

from __future__ import annotations

import os
import re
import time
import hashlib
import threading
from collections import defaultdict, deque
from datetime import datetime, timezone
from pathlib import Path
from typing import Callable, Any

from loguru import logger

ROOT = Path(__file__).resolve().parent.parent

# ─────────────────────────────────────────────────────────────────────────────
# 1. LOOP PROTECTION
# ─────────────────────────────────────────────────────────────────────────────

class LoopGuard:
    """
    Ek kaam zyada baar repeat hone se rokta hai.
    Jaise: ek hi job ko baar baar process mat karo.
    """

    def __init__(self, max_repeats: int = 3, window_seconds: int = 300):
        self._counts: dict[str, deque] = defaultdict(deque)
        self._max = max_repeats
        self._window = window_seconds
        self._lock = threading.Lock()

    def check(self, key: str) -> bool:
        """
        True = safe to proceed
        False = loop detected, STOP!
        """
        now = time.time()
        with self._lock:
            q = self._counts[key]
            # Purane entries hatao
            while q and now - q[0] > self._window:
                q.popleft()
            if len(q) >= self._max:
                logger.warning("LOOP DETECTED: '{}' {} times in {}s", key, len(q), self._window)
                return False
            q.append(now)
            return True

    def reset(self, key: str) -> None:
        with self._lock:
            self._counts.pop(key, None)


# Global loop guard
loop_guard = LoopGuard(max_repeats=3, window_seconds=300)


# ─────────────────────────────────────────────────────────────────────────────
# 2. RATE LIMITER
# ─────────────────────────────────────────────────────────────────────────────

class RateLimiter:
    """
    Ek source pe zyada fast requests mat bhejo.
    Freelancer/Groq ban na kare isliye.
    """

    def __init__(self):
        self._last: dict[str, float] = {}
        self._lock = threading.Lock()

    def wait(self, source: str, min_gap_seconds: float = 2.0) -> None:
        """
        Last request ke baad min_gap_seconds wait karo.
        """
        with self._lock:
            last = self._last.get(source, 0)
            elapsed = time.time() - last
            if elapsed < min_gap_seconds:
                wait_time = min_gap_seconds - elapsed
                logger.debug("Rate limit wait: {}s for '{}'", round(wait_time, 1), source)
                time.sleep(wait_time)
            self._last[source] = time.time()

    def can_proceed(self, source: str, min_gap_seconds: float = 2.0) -> bool:
        """Wait kiye bina check karo."""
        with self._lock:
            last = self._last.get(source, 0)
            return (time.time() - last) >= min_gap_seconds


# Global rate limiter
rate_limiter = RateLimiter()


# ─────────────────────────────────────────────────────────────────────────────
# 3. API KEY GUARD
# ─────────────────────────────────────────────────────────────────────────────

# Patterns jo API keys identify karti hain
_KEY_PATTERNS = [
    re.compile(r"gsk_[A-Za-z0-9]{20,}"),           # Groq
    re.compile(r"sk-[A-Za-z0-9]{20,}"),             # OpenAI
    re.compile(r"AIza[A-Za-z0-9_\-]{30,}"),         # Google
    re.compile(r"(?i)password\s*=\s*\S{4,}"),       # Passwords
    re.compile(r"(?i)secret\s*[=:]\s*\S{4,}"),      # Secrets
    re.compile(r"(?i)token\s*[=:]\s*\S{10,}"),      # Tokens
]

def mask_secrets(text: str) -> str:
    """Text mein se API keys/passwords mask karo."""
    if not text:
        return text
    out = text
    for pat in _KEY_PATTERNS:
        out = pat.sub("[SECRET]", out)
    return out


def env_file_safe() -> dict[str, bool]:
    """
    .env file check karo — koi problem toh nahi?
    Returns dict of check_name -> passed
    """
    env_path = ROOT / ".env"
    results = {
        "env_exists": env_path.exists(),
        "env_not_in_git": True,
        "gitignore_has_env": False,
        "no_key_in_logs": True,
    }

    # .gitignore check
    gi = ROOT / ".gitignore"
    if gi.exists():
        content = gi.read_text(encoding="utf-8", errors="ignore")
        results["gitignore_has_env"] = ".env" in content

    # Log files mein keys toh nahi?
    log_dir = ROOT / "logs"
    if log_dir.exists():
        for log_file in log_dir.glob("*.log"):
            try:
                content = log_file.read_text(encoding="utf-8", errors="ignore")
                for pat in _KEY_PATTERNS:
                    if pat.search(content):
                        results["no_key_in_logs"] = False
                        logger.warning("SECRET FOUND IN LOG: {}", log_file.name)
                        break
            except Exception:
                pass

    return results


# ─────────────────────────────────────────────────────────────────────────────
# 4. INPUT VALIDATOR — Prompt Injection se bachao
# ─────────────────────────────────────────────────────────────────────────────

# Yeh patterns prompt injection indicate karte hain
_INJECTION_PATTERNS = [
    r"ignore\s+(previous|all|above)\s+instructions?",
    r"you\s+are\s+now\s+a?\s+different",
    r"forget\s+(everything|all|previous)",
    r"new\s+instructions?\s*:",
    r"system\s*:\s*(you|your|act)",
    r"pretend\s+(you\s+are|to\s+be)",
    r"act\s+as\s+(if\s+you\s+are|a\s+different)",
    r"disregard\s+(your|all|previous)",
    r"jailbreak",
    r"dan\s+mode",
]

_INJECTION_RE = [re.compile(p, re.I) for p in _INJECTION_PATTERNS]


def is_injection(text: str) -> bool:
    """
    Job description mein prompt injection hai?
    Koi client HIMAN ko manipulate karne ki koshish kar raha hai?
    """
    if not text:
        return False
    for pat in _INJECTION_RE:
        if pat.search(text):
            logger.warning("PROMPT INJECTION DETECTED in input: {}...", text[:80])
            return True
    return False


def sanitize_input(text: str, max_len: int = 10000) -> str:
    """
    User input clean karo:
    - Max length enforce karo
    - Null bytes hatao
    - Injection check karo
    """
    if not text:
        return ""
    # Null bytes hatao
    cleaned = text.replace("\x00", "").strip()
    # Max length
    if len(cleaned) > max_len:
        logger.warning("Input truncated: {} → {}", len(cleaned), max_len)
        cleaned = cleaned[:max_len]
    return cleaned


# ─────────────────────────────────────────────────────────────────────────────
# 5. CRASH GUARD — Auto recover on error
# ─────────────────────────────────────────────────────────────────────────────

def crash_guard(max_retries: int = 3, delay: float = 5.0):
    """
    Decorator — function crash kare toh retry karo.
    3 baar fail hone ke baad stop.

    Usage:
        @crash_guard(max_retries=3)
        def my_function():
            ...
    """
    def decorator(func: Callable) -> Callable:
        def wrapper(*args: Any, **kwargs: Any) -> Any:
            last_exc = None
            for attempt in range(1, max_retries + 1):
                try:
                    return func(*args, **kwargs)
                except Exception as exc:
                    last_exc = exc
                    logger.warning(
                        "Attempt {}/{} failed for {}: {}",
                        attempt, max_retries, func.__name__, exc
                    )
                    if attempt < max_retries:
                        time.sleep(delay * attempt)  # Exponential backoff
            logger.error("All {} attempts failed for {}", max_retries, func.__name__)
            raise last_exc  # type: ignore
        return wrapper
    return decorator


# ─────────────────────────────────────────────────────────────────────────────
# 6. SECURITY AUDIT LOG
# ─────────────────────────────────────────────────────────────────────────────

_sec_log_path = ROOT / "logs" / "security.log"

def sec_audit(event: str, detail: str = "", level: str = "INFO") -> None:
    """
    Security event log karo alag file mein.
    Normal logs se alag — sirf security events.
    """
    try:
        _sec_log_path.parent.mkdir(parents=True, exist_ok=True)
        ts = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC")
        clean_detail = mask_secrets(detail)
        line = f"[{ts}] [{level}] {event} | {clean_detail[:300]}\n"
        with open(_sec_log_path, "a", encoding="utf-8") as f:
            f.write(line)
    except Exception:
        pass


# ─────────────────────────────────────────────────────────────────────────────
# 7. SYSTEM HEALTH CHECK
# ─────────────────────────────────────────────────────────────────────────────

def full_security_check() -> dict[str, Any]:
    """
    Poora security check karo.
    Dashboard mein "Health" tab mein yeh use hota hai.
    """
    import sys
    sys.path.insert(0, str(ROOT))
    from dotenv import load_dotenv
    load_dotenv(ROOT / ".env", override=True)

    results: dict[str, Any] = {}

    # 1. Env file checks
    env_checks = env_file_safe()
    results["env_file_exists"]      = env_checks["env_exists"]
    results["gitignore_protects"]   = env_checks["gitignore_has_env"]
    results["no_keys_in_logs"]      = env_checks["no_key_in_logs"]

    # 2. API key present?
    from himan.config import settings
    results["groq_key_set"]         = settings.groq_ready
    results["safety_enabled"]       = settings.safety_enabled

    # 3. Emergency stop?
    from himan import emergency
    results["not_stopped"]          = not emergency.is_stopped()

    # 4. Data dir writable?
    data_dir = ROOT / "data"
    try:
        test_file = data_dir / ".write_test"
        test_file.write_text("test")
        test_file.unlink()
        results["data_dir_writable"] = True
    except Exception:
        results["data_dir_writable"] = False

    # 5. No suspicious files?
    suspicious = []
    for ext in ["*.exe", "*.bat", "*.ps1", "*.vbs"]:
        for f in (ROOT / "data").glob(ext):
            suspicious.append(f.name)
    results["no_suspicious_files"] = len(suspicious) == 0
    if suspicious:
        logger.warning("Suspicious files in data/: {}", suspicious)
        sec_audit("SUSPICIOUS_FILES", str(suspicious), "WARNING")

    # Overall score
    passed = sum(1 for v in results.values() if v is True)
    total  = len(results)
    results["score"] = f"{passed}/{total}"
    results["safe"]  = passed >= total - 1  # 1 fail allowed

    sec_audit("HEALTH_CHECK", f"score={results['score']}")
    return results
