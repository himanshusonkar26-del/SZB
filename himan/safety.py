from __future__ import annotations

import re
from dataclasses import dataclass

from himan.config import settings
from himan.llm import chat_json

BLOCK_KEYWORDS = [
    r"\bkeylogger\b",
    r"\bransomware\b",
    r"\bmalware\b",
    r"\bbotnet\b",
    r"\bddos\b",
    r"\bcarding\b",
    r"\bcvvs?\b",
    r"\botp\s*(bypass|steal|grab)\b",
    r"\bchild\s*(porn|pornography|sexual)\b",
    r"\bcsam\b",
    r"\bunderage\b",
    r"\bmake\s+a\s+bomb\b",
    r"\bexplosive\b",
    r"\bhack\s+(into|account|password)\b",
    r"\bunauthorized\s+access\b",
    r"\bphishing\s+(kit|page|site)\b",
    r"\bfake\s+(id|passport|license)\b",
    r"\bdrug\s+(shipping|trafficking)\b",
]

SCAM_KEYWORDS = [
    r"pay\s+(a\s+)?(registration|membership|training)\s+fee",
    r"send\s+(your\s+)?(bank|otp|pin|cvv|password)",
    r"western\s+union.*(first|upfront)",
    r"guaranteed\s+\$\d+",
    r"work\s+from\s+home.*no\s+experience.*\$\d{3,}",
    r"crypto\s+giveaway",
    r"seed\s+phrase",
    r"private\s+key",
]

REVIEW_KEYWORDS = [
    r"\bcaptcha\s+farm\b",
    r"\bfake\s+reviews?\b",
    r"\bexam\s+help\b",
    r"\bwrite\s+my\s+assignment\b",
    r"\blogin\s+to\s+(my|client)\s+account\b",
]


@dataclass
class SafetyVerdict:
    level: str  # allow | review | block
    reasons: list[str]
    category: str

    @property
    def blocked(self) -> bool:
        return self.level == "block"


def _hits(patterns: list[str], text: str) -> list[str]:
    found = []
    for pat in patterns:
        if re.search(pat, text, flags=re.I):
            found.append(pat)
    return found


def rule_scan(title: str, description: str) -> SafetyVerdict:
    blob = f"{title}\n{description}"
    reasons: list[str] = []
    if _hits(BLOCK_KEYWORDS, blob):
        reasons.append("blocked_keyword")
        return SafetyVerdict("block", reasons, "illegal_or_abuse")
    if _hits(SCAM_KEYWORDS, blob):
        reasons.append("scam_pattern")
        return SafetyVerdict("block", reasons, "scam")
    if _hits(REVIEW_KEYWORDS, blob):
        reasons.append("needs_human_review")
        return SafetyVerdict("review", reasons, "sensitive")
    return SafetyVerdict("allow", [], "ok")


def llm_scan(title: str, description: str) -> SafetyVerdict | None:
    if not settings.groq_ready:
        return None
    prompt = {
        "role": "system",
        "content": (
            "You are HIMAN Safety. Classify freelance job requests. "
            "Return JSON: {\"level\":\"allow|review|block\",\"category\":\"string\",\"reasons\":[\"...\"]}. "
            "BLOCK: crime, malware, hacking, CSAM, weapons, fraud, credential theft, phishing. "
            "REVIEW: academic cheating, fake reviews, logging into someone else's account, grey-area. "
            "ALLOW: normal writing, coding, data, design, marketing work the user will submit themselves."
        ),
    }
    user = {
        "role": "user",
        "content": f"Title: {title}\n\nDescription:\n{description[:8000]}",
    }
    try:
        data = chat_json([prompt, user])
        level = str(data.get("level", "review")).lower()
        if level not in {"allow", "review", "block"}:
            level = "review"
        reasons = data.get("reasons") or []
        if not isinstance(reasons, list):
            reasons = [str(reasons)]
        return SafetyVerdict(level, [str(r) for r in reasons][:8], str(data.get("category", "unknown")))
    except Exception:
        return SafetyVerdict("review", ["llm_safety_unavailable"], "unknown")


def combine(rule: SafetyVerdict, llm: SafetyVerdict | None) -> SafetyVerdict:
    if llm is None:
        return rule
    rank = {"allow": 0, "review": 1, "block": 2}
    level = rule.level if rank[rule.level] >= rank[llm.level] else llm.level
    reasons = list(dict.fromkeys(rule.reasons + llm.reasons))
    category = llm.category if rank[llm.level] >= rank[rule.level] else rule.category
    return SafetyVerdict(level, reasons, category)


def assess_job(title: str, description: str) -> SafetyVerdict:
    if not settings.safety_enabled:
        return SafetyVerdict("review", ["safety_flag_off_forced_review"], "policy")
    rule = rule_scan(title, description)
    if rule.blocked:
        return rule
    llm = llm_scan(title, description)
    return combine(rule, llm)
