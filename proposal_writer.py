"""
HIMAN Proposal Writer — v2.0 UPGRADED
=======================================
Winning cover letters likhta hai jo client ko impress kare.
Har agent type ke liye alag strategy hai.
"""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from himan.llm import chat_text
from himan.config import settings

# ─── PROFILE ──────────────────────────────────────────────────────────────────
PROFILE = """
Freelancer: Himanshu
Skills: Python automation, web scraping, data entry, content writing,
        SEO optimization, WordPress, virtual assistant tasks, API integration,
        chatbot development, Excel/Google Sheets, online research,
        social media management, email marketing, copywriting, transcription,
        lead generation, customer support, React basics, Flask/Django
Experience: 2+ years on Freelancer.com
Location: India (available 24/7)
Rate: Budget-friendly, quality guaranteed
Strengths: Fast delivery, clear communication, revision included
"""

# ─── AGENT PROMPTS v2.0 — More specific, more winning ────────────────────────
PROMPTS = {
    "dev": """You are a senior freelance developer writing a winning bid proposal.

Freelancer profile:
{profile}

WINNING FORMULA:
1. First sentence: Directly address THEIR specific technical problem (use exact words from job)
2. Second: Show you've done this EXACT thing before (specific, not vague)
3. Third: Give concrete delivery plan (what you'll do, how long)
4. Fourth: One smart technical question to show expertise
5. Keep total under 120 words
6. NO "Dear Client", NO "I am a developer", NO generic opener
7. Sound like a real human expert, not a robot
8. Do NOT say "AI" or "ChatGPT"
9. End with your name: Himanshu""",

    "writer": """You are an expert content writer writing a winning freelance proposal.

Freelancer profile:
{profile}

WINNING FORMULA:
1. First sentence: Show you understand their content goal (be specific to their niche)
2. Second: Prove your writing skill with ONE impressive example or result
3. Third: Tell them exactly what you'll deliver (word count, format, timeline)
4. Fourth: Engaging question about their audience or goal
5. Keep total under 110 words
6. NO generic opener
7. Conversational, warm tone — like a professional friend
8. Do NOT mention AI
9. End with: Himanshu""",

    "data": """You are an accurate data specialist writing a winning freelance proposal.

Freelancer profile:
{profile}

WINNING FORMULA:
1. First sentence: Acknowledge their specific data task
2. Second: Show your accuracy/speed ("I can handle X rows per hour" or "99.9% accuracy")
3. Third: Offer FREE small test sample to prove skills
4. Fourth: Mention specific tools (Excel, Google Sheets, Python scripts if needed)
5. Keep total under 90 words — SHORT wins in data entry
6. No fluff, straight to point
7. Do NOT mention AI
8. End with: Himanshu""",

    "design": """You are a creative designer writing a winning freelance proposal.

Freelancer profile:
{profile}

WINNING FORMULA:
1. First sentence: Show you understand their brand/design vision
2. Second: Reference a specific design style or trend relevant to their industry
3. Third: Process — how many concepts, revisions included
4. Fourth: Ask about their brand colors, fonts, or inspirations
5. Keep total under 110 words
6. Creative but professional tone
7. Do NOT mention AI
8. End with: Himanshu""",

    "marketing": """You are a results-driven marketer writing a winning freelance proposal.

Freelancer profile:
{profile}

WINNING FORMULA:
1. First sentence: Identify their marketing pain point
2. Second: Give ONE specific result you've achieved (e.g., "increased CTR by 40%")
3. Third: Tell them exactly what strategy you'll implement
4. Fourth: Smart question about their target audience or current metrics
5. Keep total under 120 words
6. Confident, results-focused tone — use numbers
7. Do NOT mention AI
8. End with: Himanshu""",
}


def write_proposal(title: str, description: str, budget: str = "", kind: str = "") -> str:
    """
    Job ke liye ek winning proposal likhta hai.
    
    Args:
        title: Job title
        description: Job description
        budget: Budget (optional)
        kind: Agent type — dev/writer/data/design/marketing
    
    Returns:
        Winning proposal text
    """
    if not settings.groq_ready:
        return _fallback_proposal(title, kind or "writer")

    if not kind or kind not in PROMPTS:
        kind = _detect_kind(title, description)

    system_prompt = PROMPTS[kind].format(profile=PROFILE)

    # Smart context extraction
    desc_preview = description[:1500]
    budget_line = f"\nClient's Budget: {budget}" if budget else ""

    user_msg = f"""Job Title: {title}
{budget_line}

Job Description:
{desc_preview}

Write a SHORT (under 120 words), WINNING proposal that gets a RESPONSE.
Be specific to THIS job. Do not be generic. Sound human."""

    try:
        proposal = chat_text(
            [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_msg},
            ],
            temperature=0.7,  # Slightly higher for more natural writing
        )
        proposal = proposal.strip()

        # Quality check — too short means AI failed
        if len(proposal) < 50:
            return _fallback_proposal(title, kind)

        return proposal

    except Exception as exc:
        from loguru import logger
        logger.warning("Proposal write failed: {}", exc)
        return _fallback_proposal(title, kind)


def _detect_kind(title: str, description: str) -> str:
    """Job type detect karo keywords se."""
    blob = (title + " " + description).lower()
    if any(w in blob for w in ["python", "script", "code", "api", "bot", "automation", "website",
                                "web app", "backend", "frontend", "react", "django", "flask",
                                "developer", "programmer", "javascript", "software"]):
        return "dev"
    if any(w in blob for w in ["write", "article", "blog", "content", "seo", "copywriting",
                                "proofread", "editing", "transcrib", "translat", "caption"]):
        return "writer"
    if any(w in blob for w in ["data entry", "excel", "spreadsheet", "copy paste", "typing",
                                "research", "virtual assistant", "lead gen", "scrape", "list"]):
        return "data"
    if any(w in blob for w in ["design", "logo", "graphic", "banner", "ui", "figma",
                                "photoshop", "illustrator", "creative", "visual"]):
        return "design"
    if any(w in blob for w in ["marketing", "social media", "email campaign", "ads", "facebook",
                                "instagram", "linkedin", "twitter", "google ads", "ppc"]):
        return "marketing"
    return "writer"


def _fallback_proposal(title: str, kind: str) -> str:
    """Agar AI nahi chala toh strong template."""
    templates = {
        "dev": (
            "I've built exactly this kind of solution before — {title}.\n\n"
            "My approach: Start with a clean architecture, write modular code with error handling, "
            "test thoroughly, and deliver with documentation.\n\n"
            "Delivery: 2-3 days for initial version, revisions included.\n\n"
            "Quick question: What's the expected input/output format?\n\nHimanshu"
        ),
        "writer": (
            "Your project for '{title}' caught my attention immediately.\n\n"
            "I write content that ranks AND converts — SEO-optimized, engaging, and tailored "
            "to your audience. Fast turnaround with unlimited revisions.\n\n"
            "What's the primary goal — traffic, conversions, or brand awareness?\n\nHimanshu"
        ),
        "data": (
            "I can handle '{title}' with 99%+ accuracy.\n\n"
            "I'm available to start immediately and can do a FREE test sample "
            "so you can verify quality before committing.\n\n"
            "Tools: Excel, Google Sheets, Python (for bulk work).\n\nHimanshu"
        ),
        "design": (
            "Your project '{title}' is right up my alley.\n\n"
            "I'll deliver clean, modern designs that match your brand. "
            "3 initial concepts + unlimited revisions until you're 100% happy.\n\n"
            "What style/colors are you going for?\n\nHimanshu"
        ),
        "marketing": (
            "I can help you grow with '{title}'.\n\n"
            "My campaigns focus on real results — engagement, conversions, ROI. "
            "I'll build a strategy tailored to your audience and goals.\n\n"
            "What's your current biggest marketing challenge?\n\nHimanshu"
        ),
    }
    template = templates.get(kind, templates["writer"])
    return template.format(title=title)


def improve_proposal(proposal: str, job_title: str, feedback: str) -> str:
    """Existing proposal ko feedback ke basis pe improve karo."""
    if not settings.groq_ready:
        return proposal

    try:
        improved = chat_text(
            [
                {
                    "role": "system",
                    "content": (
                        "You are HIMAN. Improve this freelance proposal based on feedback. "
                        "Keep it natural, human, and under 130 words. "
                        "Make it more specific and compelling. Do NOT mention AI."
                    ),
                },
                {
                    "role": "user",
                    "content": (
                        f"Job: {job_title}\n\n"
                        f"Current proposal:\n{proposal}\n\n"
                        f"Feedback to address: {feedback}\n\n"
                        "Rewrite it better:"
                    ),
                },
            ],
            temperature=0.5,
        )
        return improved.strip()
    except Exception:
        return proposal


def batch_write(jobs: list[dict]) -> list[dict]:
    """Multiple jobs ke liye proposals likho."""
    for job in jobs:
        try:
            proposal = write_proposal(
                title=job.get("title", ""),
                description=job.get("description", ""),
                budget=job.get("budget", ""),
                kind=job.get("agent_kind", ""),
            )
            job["proposal"] = proposal
        except Exception:
            job["proposal"] = ""
    return jobs
