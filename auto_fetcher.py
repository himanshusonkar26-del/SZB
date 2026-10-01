"""
HIMAN Auto Fetcher — Fixed Version
====================================
Freelancer.com public API se jobs fetch karta hai (RSS nahi — API use karta hai).
Har 30 min mein automatically chalega.
"""

from __future__ import annotations

import sys, os, time, random, json
from pathlib import Path
from datetime import datetime

ROOT = Path(__file__).resolve().parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from dotenv import load_dotenv
load_dotenv(ROOT / ".env", override=True)

from loguru import logger
import httpx

from himan.config import settings
from himan import emergency, memory
from himan.safety import assess_job
from himan.security import new_id, setup_logging
from himan.shield import loop_guard, rate_limiter, is_injection, sanitize_input, sec_audit, crash_guard

setup_logging()

_seen_titles: set[str] = set()

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/124.0 Safari/537.36",
    "Accept": "application/json",
    "Accept-Language": "en-US,en;q=0.9",
}

# Freelancer API — in skills ke jobs dhundho
SKILL_SEARCHES = [
    "python",
    "data-entry",
    "content-writing",
    "web-scraping",
    "automation",
    "wordpress",
    "seo",
    "virtual-assistant",
]


def _delay(lo=2.0, hi=4.5):
    time.sleep(random.uniform(lo, hi))


def fetch_freelancer_jobs(limit_per_skill=8) -> list[dict]:
    """Freelancer public API se jobs fetch karo."""
    all_jobs = []
    seen_ids = set()

    for skill in SKILL_SEARCHES:
        _delay(2.0, 4.0)
        # Rate limiter — Freelancer ban na kare
        rate_limiter.wait("freelancer", min_gap_seconds=3.0)
        url = (
            "https://www.freelancer.com/api/projects/0.1/projects/active/"
            f"?compact=true&limit={limit_per_skill}&job_details=true"
            f"&sort_field=time_updated&or_jobs[]={skill}"
        )
        try:
            resp = httpx.get(url, headers=HEADERS, timeout=20, follow_redirects=True)
            resp.raise_for_status()
            projects = resp.json().get("result", {}).get("projects", [])

            for p in projects:
                pid = str(p.get("id", ""))
                if pid in seen_ids:
                    continue
                seen_ids.add(pid)

                title = (p.get("title") or "").strip()
                desc = (p.get("description") or "").strip()
                bmin = p.get("minimum_budget") or ""
                bmax = p.get("maximum_budget") or ""
                budget = f"${bmin}-${bmax}" if bmin or bmax else ""
                seo = p.get("seo_url") or ""
                url_job = f"https://www.freelancer.com/projects/{seo}" if seo else ""

                if not title:
                    continue

                all_jobs.append({
                    "title": title[:300],
                    "description": desc[:4000],
                    "budget": budget,
                    "url": url_job,
                    "source": f"freelancer/{skill}",
                    "skill_tag": skill,
                })

            logger.info("Skill '{}': {} jobs", skill, len(projects))
        except Exception as exc:
            logger.warning("Freelancer fetch failed for {}: {}", skill, exc)

    logger.info("Total fetched: {} jobs", len(all_jobs))
    return all_jobs


def ai_score(jobs: list[dict]) -> list[dict]:
    """AI se score karo — best jobs pehle."""
    if not settings.groq_ready or not jobs:
        for j in jobs:
            j["score"] = 55
            j["shortlisted"] = True
        return jobs

    from himan.llm import chat_json

    batch_size = 8
    scored = []

    for i in range(0, len(jobs), batch_size):
        batch = jobs[i: i + batch_size]
        items = [{"i": idx, "t": j["title"], "d": j["description"][:400]} for idx, j in enumerate(batch)]
        try:
            data = chat_json([
                {
                    "role": "system",
                    "content": (
                        "Score these freelance jobs 0-100 for this freelancer:\n"
                        "Skills: Python, automation, web scraping, data entry, "
                        "content writing, SEO, WordPress, virtual assistant, Excel, chatbot.\n"
                        "JSON: {\"scores\":[{\"i\":0,\"score\":80,\"ok\":true,\"why\":\"good match\"}]}\n"
                        "ok=true if score>=55. Scam/illegal = score 0."
                    ),
                },
                {"role": "user", "content": json.dumps(items)},
            ])
            for item in data.get("scores", []):
                idx = int(item.get("i", 0))
                if idx < len(batch):
                    batch[idx]["score"] = int(item.get("score", 50))
                    batch[idx]["shortlisted"] = bool(item.get("ok", False))
                    batch[idx]["ai_reason"] = str(item.get("why", ""))
                    scored.append(batch[idx])
            _delay(1.0, 2.0)
        except Exception as exc:
            logger.warning("AI scoring batch {} failed: {}", i, exc)
            for j in batch:
                j["score"] = 55
                j["shortlisted"] = True
                scored.append(j)

    scored.sort(key=lambda x: x.get("score", 0), reverse=True)
    return scored


def save_job(job: dict) -> bool:
    """Job ko safety check karke DB mein save karo + proposal banao."""
    title = job["title"]
    desc = job["description"]

    # Duplicate check
    title_key = title.lower().strip()
    if title_key in _seen_titles:
        return False
    _seen_titles.add(title_key)

    # Loop guard — ek hi job baar baar process mat ho
    if not loop_guard.check(f"job:{title_key[:60]}"):
        logger.warning("Loop guard blocked repeated job: {}", title[:50])
        sec_audit("LOOP_BLOCKED", title[:80])
        return False

    # Prompt injection check
    if is_injection(title) or is_injection(desc):
        logger.warning("Injection detected in job: {}", title[:50])
        sec_audit("INJECTION_BLOCKED", title[:80], "WARNING")
        return False

    # Input sanitize
    title = sanitize_input(title, 300)
    desc  = sanitize_input(desc, 8000)

    # Safety check
    verdict = assess_job(title, desc)
    if verdict.blocked:
        logger.info("Blocked: {}", title[:50])
        return False

    # Proposal banao
    proposal = ""
    try:
        from proposal_writer import write_proposal
        proposal = write_proposal(title, desc, job.get("budget", ""))
        logger.success("Proposal ready for: {}", title[:50])
    except Exception as exc:
        logger.warning("Proposal failed: {}", exc)

    # DB mein save
    try:
        memory.init_db()
        job_id = new_id("job")
        source_note = job.get("source", "auto") + (" | " + job["url"] if job.get("url") else "")

        db_job = {
            "id": job_id,
            "title": title,
            "description": desc,
            "budget": job.get("budget", ""),
            "source_note": source_note,
            "status": "ready",
            "safety_level": verdict.level,
            "safety": {"level": verdict.level, "category": verdict.category, "reasons": verdict.reasons},
            "agent_kind": _kind(title, desc),
            "draft": proposal,
            "retries": 0,
        }
        memory.insert_job(db_job)
        memory.audit("auto_fetcher", job_id, f"score={job.get('score',0)}")

        # Telegram alert
        if settings.telegram_ready and job.get("score", 0) >= 70:
            from himan.telegram_alerts import notify_new_job
            notify_new_job(title, job.get("score", 0), job.get("ai_reason", ""), job.get("url", ""))

        return True
    except Exception as exc:
        logger.error("Save failed: {}", exc)
        return False


def _kind(title: str, desc: str) -> str:
    b = (title + " " + desc).lower()
    if any(w in b for w in ["python","script","code","api","bot","automation","website","web app","backend","react","flask","django"]):
        return "dev"
    if any(w in b for w in ["write","article","blog","content","seo","copywriting","proofreading"]):
        return "writer"
    if any(w in b for w in ["data entry","excel","spreadsheet","copy paste","typing","research","virtual assistant"]):
        return "data"
    if any(w in b for w in ["design","logo","graphic","banner","ui","figma","photoshop"]):
        return "design"
    if any(w in b for w in ["marketing","social media","email","ads","campaign","facebook","instagram"]):
        return "marketing"
    return "writer"


def run_cycle() -> int:
    """Ek cycle: fetch → score → save. Returns saved count."""
    if emergency.is_stopped():
        logger.warning("Emergency stop active.")
        return 0

    # Loop guard — cycle baar baar na chale
    if not loop_guard.check("fetch_cycle"):
        logger.warning("Loop guard: too many cycles too fast. Waiting...")
        sec_audit("CYCLE_LOOP_BLOCKED", "fetch_cycle ran too fast")
        time.sleep(60)
        return 0

    logger.info("=" * 50)
    logger.info("HIMAN Fetch Cycle — {}", datetime.now().strftime("%H:%M:%S"))

    raw = fetch_freelancer_jobs(limit_per_skill=8)
    if not raw:
        logger.warning("Koi jobs nahi mili.")
        return 0

    # Deduplicate
    seen = set()
    unique = []
    for j in raw:
        k = j["title"].lower().strip()
        if k not in seen:
            seen.add(k)
            unique.append(j)

    logger.info("Unique jobs: {}", len(unique))

    # Score
    scored = ai_score(unique)
    shortlisted = [j for j in scored if j.get("shortlisted")]
    logger.info("Shortlisted: {}/{}", len(shortlisted), len(scored))

    # Save top 10
    saved = 0
    for job in shortlisted[:10]:
        if emergency.is_stopped():
            break
        if save_job(job):
            saved += 1
        _delay(2.0, 3.5)

    logger.info("Cycle done: {} jobs saved to DB", saved)

    if settings.telegram_ready and saved > 0:
        from himan.telegram_alerts import notify_search_summary
        notify_search_summary(len(raw), saved)

    return saved


def main():
    interval = int(os.getenv("SEARCH_INTERVAL_MINUTES", "30"))
    logger.info("HIMAN Auto Fetcher started! Interval: {} min", interval)

    run_cycle()  # Pehla cycle abhi

    while True:
        logger.info("Next cycle in {} minutes...", interval)
        time.sleep(interval * 60)
        run_cycle()


if __name__ == "__main__":
    main()
