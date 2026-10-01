"""
HIMAN Proposal Writer
=====================
Har job ke liye ek winning cover letter likhta hai.
Client ko convince karne wala — professional aur personalized.

Jo sab agents kaam karte hain is file mein:
- Dev Agent    → Coding jobs ke liye
- Writer Agent → Content jobs ke liye
- Data Agent   → Data entry jobs ke liye
- Design Agent → Design jobs ke liye
- Marketing Agent → Marketing jobs ke liye
"""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from himan.llm import chat_text
from himan.config import settings

# ─── Profile — HIMAN ki skills jo proposal mein use hoti hain ────────────────
PROFILE = """
Name: Himanshu (HIMAN)
Skills: Python, Web Automation, Data Entry, Content Writing, Web Scraping,
        SEO, WordPress, Virtual Assistant, API Integration, Chatbots,
        Excel, Research, Social Media Marketing
Experience: 2+ years freelancing
Location: India
Rate: Flexible (depends on project)
"""

# ─── System prompts for each agent type ─────────────────────────────────────

PROMPTS = {
    "dev": """You are HIMAN Dev Agent writing a freelance cover letter.
Profile: {profile}

Rules:
- Start with understanding THEIR specific problem (mention their project)
- Show relevant technical skill (Python/automation/web dev)
- Give ONE short example of similar work
- Mention delivery timeline
- End with a question to engage client
- Keep it under 150 words
- NO generic opener like "Hello, I am a developer..."
- Sound like a real human, not a robot
- Do NOT mention AI""",

    "writer": """You are HIMAN Writer Agent writing a freelance cover letter.
Profile: {profile}

Rules:
- Open with understanding their content need
- Show writing skill with ONE strong sentence
- Mention relevant experience (blogs, SEO, articles)
- Promise quality + quick turnaround
- Ask an engaging question about their target audience
- Keep it under 130 words
- Natural, conversational tone
- Do NOT mention AI""",

    "data": """You are HIMAN Data Agent writing a freelance cover letter.
Profile: {profile}

Rules:
- Acknowledge their data task specifically
- Show accuracy + speed (mention tools: Excel, Google Sheets, etc.)
- Offer to do a small FREE sample test
- Mention availability
- Keep it short — under 100 words
- Professional, to the point
- Do NOT mention AI""",

    "design": """You are HIMAN Design Agent writing a freelance cover letter.
Profile: {profile}

Rules:
- Show you understand their brand/design vision
- Mention relevant design skills
- Offer to share portfolio examples
- Ask about their brand colors/style
- Under 120 words
- Creative but professional tone
- Do NOT mention AI""",

    "marketing": """You are HIMAN Marketing Agent writing a freelance cover letter.
Profile: {profile}

Rules:
- Show understanding of their marketing goal
- Give ONE data point or result from past work
- Mention platforms you know (Facebook, Instagram, Google Ads, etc.)
- Under 130 words
- Confident, results-focused tone
- Do NOT mention AI""",
}


def write_proposal(title: str, description: str, budget: str = "", kind: str = "") -> str:
    """
    Job ke liye ek winning proposal likhta hai.
    
    Args:
        title: Job title
        description: Job description
        budget: Budget (optional)
        kind: Agent type — dev/writer/data/design/marketing (auto-detect if empty)
    
    Returns:
        Proposal text (tum copy karke bid mein paste karo)
    """
    if not settings.groq_ready:
        return _fallback_proposal(title, kind)

    # Agent type detect karo agar nahi diya
    if not kind or kind not in PROMPTS:
        kind = _detect_kind(title, description)

    system_prompt = PROMPTS[kind].format(profile=PROFILE)

    user_msg = f"""Job Title: {title}

Job Description:
{description[:2000]}

Budget: {budget or "Not mentioned"}

Write a winning cover letter/proposal for this job."""

    try:
        proposal = chat_text(
            [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_msg},
            ],
            temperature=0.6,
        )
        return proposal.strip()
    except Exception as exc:
        from loguru import logger
        logger.warning("Proposal write failed: {}", exc)
        return _fallback_proposal(title, kind)


def _detect_kind(title: str, description: str) -> str:
    """Job type detect karo keywords se."""
    blob = (title + " " + description).lower()
    if any(w in blob for w in ["python", "script", "code", "api", "bot", "automation", "website", "web app", "backend", "frontend", "react", "django", "flask"]):
        return "dev"
    if any(w in blob for w in ["write", "article", "blog", "content", "seo", "copywriting", "proofread", "editing"]):
        return "writer"
    if any(w in blob for w in ["data entry", "excel", "spreadsheet", "copy paste", "typing", "research", "virtual assistant"]):
        return "data"
    if any(w in blob for w in ["design", "logo", "graphic", "banner", "ui", "figma", "photoshop", "illustrator"]):
        return "design"
    if any(w in blob for w in ["marketing", "social media", "email", "ads", "campaign", "facebook", "instagram", "seo"]):
        return "marketing"
    return "writer"


def _fallback_proposal(title: str, kind: str) -> str:
    """Agar AI nahi chala toh basic template."""
    templates = {
        "dev": (
            "Hi,\n\nI've carefully reviewed your project requirements for '{title}' "
            "and I'm confident I can deliver exactly what you need.\n\n"
            "I have strong experience in Python, automation, and web development. "
            "I can start immediately and deliver on time.\n\n"
            "Could you share more details about the expected output format? "
            "Happy to discuss further.\n\nBest regards"
        ),
        "writer": (
            "Hi,\n\nI noticed you need help with '{title}' — I'd love to take this on.\n\n"
            "I have experience writing engaging, SEO-optimized content that drives results. "
            "I can deliver quality work within your deadline.\n\n"
            "What's the primary audience for this content?\n\nBest regards"
        ),
        "data": (
            "Hi,\n\nI can help you with '{title}'.\n\n"
            "I'm detail-oriented and fast with data tasks. "
            "I'm available to start right away and can do a small test sample if needed.\n\n"
            "Best regards"
        ),
        "design": (
            "Hi,\n\nYour project '{title}' caught my attention.\n\n"
            "I can create clean, professional designs tailored to your brand. "
            "Could you share your brand guidelines or color preferences?\n\nBest regards"
        ),
        "marketing": (
            "Hi,\n\nI'd love to help with '{title}'.\n\n"
            "I have hands-on experience with digital marketing campaigns that deliver real results. "
            "What's your primary marketing goal?\n\nBest regards"
        ),
    }
    template = templates.get(kind, templates["writer"])
    return template.format(title=title)


def improve_proposal(proposal: str, job_title: str, feedback: str) -> str:
    """
    Existing proposal ko improve karo feedback ke basis pe.
    Dashboard mein 'Improve' button press karne pe use hota hai.
    """
    if not settings.groq_ready:
        return proposal

    try:
        improved = chat_text(
            [
                {
                    "role": "system",
                    "content": (
                        "You are HIMAN. Improve this freelance proposal based on feedback. "
                        "Keep it natural and human. Under 150 words. Do NOT mention AI."
                    ),
                },
                {
                    "role": "user",
                    "content": f"Job: {job_title}\n\nCurrent proposal:\n{proposal}\n\nFeedback: {feedback}\n\nImprove it:",
                },
            ],
            temperature=0.5,
        )
        return improved.strip()
    except Exception:
        return proposal


def batch_write(jobs: list[dict]) -> list[dict]:
    """
    Multiple jobs ke liye ek saath proposals likho.
    Returns same list with 'proposal' key added.
    """
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
