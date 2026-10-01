from __future__ import annotations

from himan.llm import chat_json, chat_text

KINDS = {
    "dev": "software, scripts, APIs, websites, automation code the user will paste themselves",
    "writer": "articles, blogs, product copy, SEO drafts",
    "data": "spreadsheets, research summaries, cleanup plans (no scraping live sites)",
    "design": "design briefs, layout copy, image prompts — not logos stolen from brands",
    "marketing": "ad copy, social captions, email drafts",
}

SYSTEM = {
    "dev": "You are HIMAN Dev. Write clear code and short usage notes. No malware, exploits, or account takeover.",
    "writer": "You are HIMAN Writer. Draft original content. No fake testimonials or plagiarism.",
    "data": "You are HIMAN Data. Outline analysis and tables. Do not instruct scraping of login-walled sites.",
    "design": "You are HIMAN Design. Deliver a design brief and structure. No trademark impersonation.",
    "marketing": "You are HIMAN Marketing. Honest copy only. No fake scarcity or scam funnels.",
}


def classify_kind(title: str, description: str) -> str:
    try:
        data = chat_json(
            [
                {
                    "role": "system",
                    "content": (
                        "Pick one job kind. JSON: {\"kind\":\"dev|writer|data|design|marketing\"}. "
                        + " ".join(f"{k}: {v}." for k, v in KINDS.items())
                    ),
                },
                {"role": "user", "content": f"{title}\n\n{description[:6000]}"},
            ]
        )
        kind = str(data.get("kind", "writer")).lower()
        return kind if kind in KINDS else "writer"
    except Exception:
        return "writer"


def produce_draft(kind: str, title: str, description: str, budget: str) -> str:
    kind = kind if kind in SYSTEM else "writer"
    return chat_text(
        [
            {"role": "system", "content": SYSTEM[kind]},
            {
                "role": "user",
                "content": (
                    f"Job title: {title}\nBudget note: {budget or 'n/a'}\n\n"
                    f"Requirements:\n{description}\n\n"
                    "Deliver a complete first draft the human can review and submit themselves."
                ),
            },
        ],
        temperature=0.4,
    )


def qc_round(round_name: str, title: str, description: str, draft: str) -> dict:
    data = chat_json(
        [
            {
                "role": "system",
                "content": (
                    f"You are HIMAN QC ({round_name}). JSON: "
                    '{"pass": true|false, "notes": "string", "score": 0-100}. '
                    "Fail if unsafe, off-brief, empty, or low quality."
                ),
            },
            {
                "role": "user",
                "content": f"Brief:\n{title}\n{description[:4000]}\n\nDraft:\n{draft[:10000]}",
            },
        ]
    )
    passed = bool(data.get("pass"))
    notes = str(data.get("notes", ""))
    try:
        score = int(data.get("score", 0))
    except (TypeError, ValueError):
        score = 0
    return {"pass": passed, "notes": notes, "score": score}


def revise_draft(kind: str, title: str, description: str, draft: str, notes: str) -> str:
    kind = kind if kind in SYSTEM else "writer"
    return chat_text(
        [
            {"role": "system", "content": SYSTEM[kind] + " Improve the draft. Keep it safe."},
            {
                "role": "user",
                "content": f"Brief: {title}\n{description[:4000]}\n\nQC notes:\n{notes}\n\nDraft:\n{draft[:10000]}",
            },
        ],
        temperature=0.35,
    )
