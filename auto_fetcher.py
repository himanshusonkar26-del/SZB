"""
HIMAN Auto Fetcher — v2.0 UPGRADED
====================================
Multiple sources se jobs fetch karta hai:
  1. Freelancer.com API
  2. PeoplePerHour RSS
  3. Guru.com RSS
  4. Remotive.com API (remote jobs)

Zyada skills, better scoring, daily stats save, agent tracking.
"""

from __future__ import annotations

import sys, os, time, random, json
from pathlib import Path
from datetime import datetime, date, timezone
from typing import Optional

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
    "Accept": "application/json, text/html, application/xml",
    "Accept-Language": "en-US,en;q=0.9",
}

# ─── EXPANDED SKILLS — 25+ skills ────────────────────────────────────────────
FREELANCER_SKILLS = [
    "python",
    "data-entry",
    "content-writing",
    "web-scraping",
    "automation",
    "wordpress",
    "seo",
    "virtual-assistant",
    "excel",
    "chatbot",
    "api-integration",
    "social-media-marketing",
    "email-marketing",
    "copywriting",
    "proofreading",
    "research",
    "transcription",
    "translation",
    "lead-generation",
    "customer-support",
    "web-design",
    "javascript",
    "react",
    "flask",
    "data-analysis",
]

# PeoplePerHour RSS feeds
PPH_RSS_FEEDS = [
    "https://www.peopleperhour.com/hourlie-rss-feed.xml",
    "https://www.peopleperhour.com/project-rss-feed.xml",
]

# ─── Upwork RSS feeds (public, no login needed) ───────────────────────────────
UPWORK_RSS_FEEDS = [
    "https://www.upwork.com/ab/feed/jobs/rss?paging=0%3B10&q=python+automation&sort=recency",
    "https://www.upwork.com/ab/feed/jobs/rss?paging=0%3B10&q=data+entry&sort=recency",
    "https://www.upwork.com/ab/feed/jobs/rss?paging=0%3B10&q=content+writing&sort=recency",
    "https://www.upwork.com/ab/feed/jobs/rss?paging=0%3B10&q=web+scraping&sort=recency",
    "https://www.upwork.com/ab/feed/jobs/rss?paging=0%3B10&q=virtual+assistant&sort=recency",
    "https://www.upwork.com/ab/feed/jobs/rss?paging=0%3B10&q=wordpress&sort=recency",
    "https://www.upwork.com/ab/feed/jobs/rss?paging=0%3B10&q=seo&sort=recency",
    "https://www.upwork.com/ab/feed/jobs/rss?paging=0%3B10&q=social+media+marketing&sort=recency",
]

# ─── RemoteOK API (free, no auth) ─────────────────────────────────────────────
REMOTEOK_TAGS = [
    "python", "automation", "writing", "data-entry", "marketing",
    "dev", "backend", "wordpress", "seo",
]

# ─── WorkingNomads RSS (remote jobs) ──────────────────────────────────────────
WORKINGNOMADS_FEEDS = [
    "https://www.workingnomads.com/api/exposed_jobs/?category=development&format=json",
    "https://www.workingnomads.com/api/exposed_jobs/?category=writing&format=json",
    "https://www.workingnomads.com/api/exposed_jobs/?category=marketing&format=json",
]

# Guru RSS feeds
GURU_RSS_FEEDS = [
    "https://www.guru.com/d/jobs/rss/?keyword=python",
    "https://www.guru.com/d/jobs/rss/?keyword=data+entry",
    "https://www.guru.com/d/jobs/rss/?keyword=content+writing",
    "https://www.guru.com/d/jobs/rss/?keyword=web+scraping",
    "https://www.guru.com/d/jobs/rss/?keyword=virtual+assistant",
]


def _delay(lo=2.0, hi=4.5):
    time.sleep(random.uniform(lo, hi))


# ─── SOURCE 1: Freelancer.com API ─────────────────────────────────────────────
def fetch_freelancer_jobs(limit_per_skill: int = 8) -> list[dict]:
    """Freelancer public API se jobs fetch karo."""
    all_jobs = []
    seen_ids = set()

    for skill in FREELANCER_SKILLS:
        _delay(1.5, 3.0)
        rate_limiter.wait("freelancer", min_gap_seconds=2.0)
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
                    "platform": "Freelancer",
                })

            logger.info("Freelancer '{}': {} jobs", skill, len(projects))
        except Exception as exc:
            logger.warning("Freelancer fetch failed for {}: {}", skill, exc)

    return all_jobs


# ─── SOURCE 2: PeoplePerHour RSS ──────────────────────────────────────────────
def fetch_pph_jobs() -> list[dict]:
    """PeoplePerHour RSS se jobs fetch karo."""
    jobs = []
    try:
        import xml.etree.ElementTree as ET
        for feed_url in PPH_RSS_FEEDS:
            _delay(2.0, 3.5)
            try:
                resp = httpx.get(feed_url, headers=HEADERS, timeout=15, follow_redirects=True)
                if resp.status_code != 200:
                    logger.warning("PPH RSS {} returned {}", feed_url, resp.status_code)
                    continue

                root = ET.fromstring(resp.text)
                items = root.findall(".//item")
                for item in items[:15]:
                    title = item.findtext("title") or ""
                    desc = item.findtext("description") or ""
                    link = item.findtext("link") or ""

                    title = title.strip()
                    desc = desc.strip()

                    if not title:
                        continue

                    jobs.append({
                        "title": title[:300],
                        "description": desc[:4000],
                        "budget": "",
                        "url": link,
                        "source": "peopleperhour/rss",
                        "platform": "PeoplePerHour",
                    })

                logger.info("PPH RSS: {} jobs from {}", len(items[:15]), feed_url)
            except Exception as exc:
                logger.warning("PPH feed {} failed: {}", feed_url, exc)
    except Exception as exc:
        logger.warning("PPH fetch error: {}", exc)

    return jobs


# ─── SOURCE 3: Guru.com RSS ───────────────────────────────────────────────────
def fetch_guru_jobs() -> list[dict]:
    """Guru.com RSS se jobs fetch karo."""
    jobs = []
    try:
        import xml.etree.ElementTree as ET
        for feed_url in GURU_RSS_FEEDS:
            _delay(2.0, 3.5)
            try:
                resp = httpx.get(feed_url, headers=HEADERS, timeout=15, follow_redirects=True)
                if resp.status_code != 200:
                    logger.warning("Guru RSS {} returned {}", feed_url, resp.status_code)
                    continue

                root = ET.fromstring(resp.text)
                items = root.findall(".//item")
                for item in items[:10]:
                    title = item.findtext("title") or ""
                    desc = item.findtext("description") or ""
                    link = item.findtext("link") or ""

                    # Clean HTML tags from description
                    import re
                    desc = re.sub(r'<[^>]+>', ' ', desc).strip()
                    title = title.strip()

                    if not title:
                        continue

                    jobs.append({
                        "title": title[:300],
                        "description": desc[:4000],
                        "budget": "",
                        "url": link,
                        "source": "guru/rss",
                        "platform": "Guru",
                    })

                logger.info("Guru RSS: {} jobs from {}", len(items[:10]), feed_url)
            except Exception as exc:
                logger.warning("Guru feed {} failed: {}", feed_url, exc)
    except Exception as exc:
        logger.warning("Guru fetch error: {}", exc)

    return jobs


# ─── SOURCE 4: Remotive (Remote Jobs API) ─────────────────────────────────────
def fetch_remotive_jobs() -> list[dict]:
    """Remotive.com se remote freelance jobs fetch karo."""
    jobs = []
    try:
        categories = ["software-dev", "writing-editing", "data", "marketing", "customer-support"]
        for cat in categories[:3]:
            _delay(1.5, 2.5)
            url = f"https://remotive.com/api/remote-jobs?category={cat}&limit=5"
            try:
                resp = httpx.get(url, headers=HEADERS, timeout=15, follow_redirects=True)
                if resp.status_code != 200:
                    continue
                data = resp.json()
                for job in data.get("jobs", [])[:5]:
                    title = (job.get("title") or "").strip()
                    desc = (job.get("description") or "").strip()
                    # Clean HTML
                    import re
                    desc = re.sub(r'<[^>]+>', ' ', desc).strip()[:4000]
                    link = job.get("url") or ""
                    salary = job.get("salary") or ""

                    if not title:
                        continue

                    jobs.append({
                        "title": title[:300],
                        "description": desc,
                        "budget": salary,
                        "url": link,
                        "source": f"remotive/{cat}",
                        "platform": "Remotive",
                    })

                logger.info("Remotive '{}': {} jobs", cat, len(data.get("jobs", [])[:5]))
            except Exception as exc:
                logger.warning("Remotive {} failed: {}", cat, exc)
    except Exception as exc:
        logger.warning("Remotive fetch error: {}", exc)

    return jobs


# ─── SOURCE 5: Upwork RSS ─────────────────────────────────────────────────────
def fetch_upwork_jobs() -> list[dict]:
    """Upwork public RSS feeds se jobs fetch karo (no login needed)."""
    jobs = []
    try:
        import xml.etree.ElementTree as ET
        import re as _re
        for feed_url in UPWORK_RSS_FEEDS:
            _delay(2.5, 4.0)
            try:
                resp = httpx.get(feed_url, headers=HEADERS, timeout=20, follow_redirects=True)
                if resp.status_code != 200:
                    logger.warning("Upwork RSS {} returned {}", feed_url, resp.status_code)
                    continue

                # Upwork RSS sometimes has encoding issues
                content = resp.text
                # Fix common XML issues
                content = content.replace("&", "&amp;").replace("&amp;amp;", "&amp;")

                try:
                    root = ET.fromstring(content)
                except ET.ParseError:
                    # Try stripping problematic chars
                    content = _re.sub(r'[^\x09\x0A\x0D\x20-\uD7FF\uE000-\uFFFD]', '', resp.text)
                    try:
                        root = ET.fromstring(content)
                    except Exception:
                        continue

                items = root.findall(".//item")
                for item in items[:8]:
                    title = item.findtext("title") or ""
                    desc = item.findtext("description") or ""
                    link = item.findtext("link") or ""
                    budget = ""

                    # Clean HTML tags
                    desc = _re.sub(r'<[^>]+>', ' ', desc).strip()
                    # Extract budget from description if present
                    budget_match = _re.search(r'Budget:\s*\$?([\d,]+(?:\.\d+)?)', desc, _re.IGNORECASE)
                    if budget_match:
                        budget = "$" + budget_match.group(1)
                    # Hourly rate
                    hourly_match = _re.search(r'Hourly Range:\s*\$?([\d\.]+)\s*[-–]\s*\$?([\d\.]+)', desc, _re.IGNORECASE)
                    if hourly_match:
                        budget = f"${hourly_match.group(1)}-${hourly_match.group(2)}/hr"

                    title = title.strip()
                    if not title or len(title) < 5:
                        continue

                    jobs.append({
                        "title": title[:300],
                        "description": desc[:4000],
                        "budget": budget,
                        "url": link,
                        "source": "upwork/rss",
                        "platform": "Upwork",
                    })

                logger.info("Upwork RSS: {} jobs from {}", len(items[:8]), feed_url[:70])
            except Exception as exc:
                logger.warning("Upwork feed {} failed: {}", feed_url[:60], exc)
    except Exception as exc:
        logger.warning("Upwork fetch error: {}", exc)

    return jobs


# ─── SOURCE 6: RemoteOK API ────────────────────────────────────────────────────
def fetch_remoteok_jobs() -> list[dict]:
    """RemoteOK.com free API se remote jobs fetch karo."""
    jobs = []
    try:
        _delay(2.0, 3.0)
        url = "https://remoteok.com/api"
        resp = httpx.get(url, headers={**HEADERS, "Accept": "application/json"}, timeout=20, follow_redirects=True)
        if resp.status_code != 200:
            logger.warning("RemoteOK returned {}", resp.status_code)
            return jobs

        data = resp.json()
        # First item is a note/legal, skip it
        listings = [j for j in data if isinstance(j, dict) and j.get("id") and j.get("position")]

        # Filter relevant ones
        relevant_tags = {"python", "automation", "content", "writing", "data", "marketing",
                         "seo", "wordpress", "virtual", "excel", "copywriting", "research",
                         "javascript", "react", "django", "flask", "backend", "frontend"}

        for listing in listings[:30]:
            tags = set(t.lower() for t in (listing.get("tags") or []))
            if not (tags & relevant_tags):
                continue  # skip irrelevant jobs

            title = (listing.get("position") or "").strip()
            desc = (listing.get("description") or "").strip()
            import re as _re
            desc = _re.sub(r'<[^>]+>', ' ', desc).strip()
            link = listing.get("url") or f"https://remoteok.com/remote-jobs/{listing.get('id','')}"
            salary = listing.get("salary") or ""

            if not title:
                continue

            jobs.append({
                "title": title[:300],
                "description": desc[:4000],
                "budget": salary,
                "url": link,
                "source": "remoteok/api",
                "platform": "RemoteOK",
            })

        logger.info("RemoteOK: {} relevant jobs", len(jobs))
    except Exception as exc:
        logger.warning("RemoteOK fetch error: {}", exc)

    return jobs


# ─── FETCH ALL SOURCES ─────────────────────────────────────────────────────────
def fetch_all_jobs() -> list[dict]:
    """Sabhi sources se jobs fetch karo."""
    all_jobs = []

    logger.info("--- Fetching Freelancer.com ---")
    freelancer_jobs = fetch_freelancer_jobs(limit_per_skill=6)
    all_jobs.extend(freelancer_jobs)
    logger.info("Freelancer total: {}", len(freelancer_jobs))

    logger.info("--- Fetching PeoplePerHour ---")
    pph_jobs = fetch_pph_jobs()
    all_jobs.extend(pph_jobs)
    logger.info("PPH total: {}", len(pph_jobs))

    logger.info("--- Fetching Guru.com ---")
    guru_jobs = fetch_guru_jobs()
    all_jobs.extend(guru_jobs)
    logger.info("Guru total: {}", len(guru_jobs))

    logger.info("--- Fetching Remotive ---")
    remotive_jobs = fetch_remotive_jobs()
    all_jobs.extend(remotive_jobs)
    logger.info("Remotive total: {}", len(remotive_jobs))

    logger.info("--- Fetching Upwork RSS ---")
    upwork_jobs = fetch_upwork_jobs()
    all_jobs.extend(upwork_jobs)
    logger.info("Upwork total: {}", len(upwork_jobs))

    logger.info("--- Fetching RemoteOK ---")
    remoteok_jobs = fetch_remoteok_jobs()
    all_jobs.extend(remoteok_jobs)
    logger.info("RemoteOK total: {}", len(remoteok_jobs))

    logger.info("ALL SOURCES TOTAL: {} raw jobs", len(all_jobs))
    return all_jobs


# ─── AI SCORING ───────────────────────────────────────────────────────────────
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
                        "content writing, SEO, WordPress, virtual assistant, Excel, "
                        "chatbot, API integration, social media, email marketing, "
                        "copywriting, transcription, research, lead generation.\n"
                        "Score 80+ if great match, 55-79 if ok match, <55 skip.\n"
                        "JSON: {\"scores\":[{\"i\":0,\"score\":80,\"ok\":true,\"why\":\"good match\"}]}\n"
                        "ok=true if score>=55. Scam/adult/illegal = score 0 ok=false."
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


# ─── DETECT AGENT KIND ────────────────────────────────────────────────────────
def _kind(title: str, desc: str) -> str:
    b = (title + " " + desc).lower()
    if any(w in b for w in ["python", "script", "code", "api", "bot", "automation", "website", "web app",
                             "backend", "react", "flask", "django", "javascript", "developer", "programmer"]):
        return "dev"
    if any(w in b for w in ["write", "article", "blog", "content", "seo", "copywriting", "proofreading",
                             "editing", "translation", "transcription"]):
        return "writer"
    if any(w in b for w in ["data entry", "excel", "spreadsheet", "copy paste", "typing", "research",
                             "virtual assistant", "lead generation", "customer support"]):
        return "data"
    if any(w in b for w in ["design", "logo", "graphic", "banner", "ui", "figma", "photoshop", "illustrator"]):
        return "design"
    if any(w in b for w in ["marketing", "social media", "email", "ads", "campaign", "facebook",
                             "instagram", "linkedin", "twitter"]):
        return "marketing"
    return "writer"


# ─── SAVE JOB ─────────────────────────────────────────────────────────────────
def save_job(job: dict) -> bool:
    """Job ko safety check karke DB mein save karo + proposal banao."""
    title = job["title"]
    desc = job["description"]

    # Duplicate check
    title_key = title.lower().strip()
    if title_key in _seen_titles:
        return False
    _seen_titles.add(title_key)

    # Loop guard
    if not loop_guard.check(f"job:{title_key[:60]}"):
        logger.warning("Loop guard blocked repeated job: {}", title[:50])
        sec_audit("LOOP_BLOCKED", title[:80])
        return False

    # Injection check
    if is_injection(title) or is_injection(desc):
        logger.warning("Injection detected in job: {}", title[:50])
        sec_audit("INJECTION_BLOCKED", title[:80], "WARNING")
        return False

    # Sanitize
    title = sanitize_input(title, 300)
    desc = sanitize_input(desc, 8000)

    # Safety check
    verdict = assess_job(title, desc)
    if verdict.blocked:
        logger.info("Blocked (safety): {}", title[:50])
        return False

    # Detect agent kind
    agent_kind = _kind(title, desc)

    # Proposal banao
    proposal = ""
    try:
        from proposal_writer import write_proposal
        proposal = write_proposal(title, desc, job.get("budget", ""), agent_kind)
        logger.success("Proposal ready for: {}", title[:50])
        # Agent bump — success
        memory.bump_agent(agent_kind, success=True)
    except Exception as exc:
        logger.warning("Proposal failed: {}", exc)
        memory.bump_agent(agent_kind, success=False)

    # DB mein save
    try:
        memory.init_db()
        job_id = new_id("job")
        platform = job.get("platform", "auto")
        url_part = " | " + job["url"] if job.get("url") else ""
        source_note = f"{platform}{url_part}"

        db_job = {
            "id": job_id,
            "title": title,
            "description": desc,
            "budget": job.get("budget", ""),
            "source_note": source_note,
            "status": "ready",
            "safety_level": verdict.level,
            "safety": {"level": verdict.level, "category": verdict.category, "reasons": verdict.reasons},
            "agent_kind": agent_kind,
            "draft": proposal,
            "retries": 0,
        }
        memory.insert_job(db_job)
        memory.audit("auto_fetcher", job_id, f"score={job.get('score', 0)} | platform={platform}")

        # Telegram alert for high score jobs
        if settings.telegram_ready and job.get("score", 0) >= 70:
            try:
                from himan.telegram_alerts import notify_new_job
                notify_new_job(title, job.get("score", 0), job.get("ai_reason", ""), job.get("url", ""))
            except Exception:
                pass

        return True
    except Exception as exc:
        logger.error("Save failed: {}", exc)
        return False


# ─── SAVE DAILY STATS ─────────────────────────────────────────────────────────
def save_daily_stats(fetched: int, saved: int) -> None:
    """Aaj ke stats DB mein save karo."""
    try:
        today = date.today().isoformat()
        with memory.connect() as conn:
            existing = conn.execute(
                "SELECT date FROM daily_stats WHERE date=?", (today,)
            ).fetchone()

            if existing:
                # Update karo
                conn.execute(
                    """UPDATE daily_stats SET
                       jobs_fetched = jobs_fetched + ?,
                       bids_placed = bids_placed + 0,
                       notes = ?
                       WHERE date = ?""",
                    (fetched, f"last_saved={saved}", today)
                )
            else:
                # Naya insert
                conn.execute(
                    """INSERT INTO daily_stats(date, jobs_fetched, bids_placed, bids_won, earnings, best_agent, notes)
                       VALUES (?, ?, 0, 0, 0.0, '', ?)""",
                    (today, fetched, f"first_cycle, saved={saved}")
                )
        logger.info("Daily stats saved for {}", today)
    except Exception as exc:
        logger.warning("Daily stats save failed: {}", exc)


# ─── MAIN CYCLE ───────────────────────────────────────────────────────────────
def run_cycle() -> int:
    """Ek cycle: fetch → score → save. Returns saved count."""
    if emergency.is_stopped():
        logger.warning("Emergency stop active.")
        return 0

    if not loop_guard.check("fetch_cycle"):
        logger.warning("Loop guard: too many cycles too fast. Waiting...")
        sec_audit("CYCLE_LOOP_BLOCKED", "fetch_cycle ran too fast")
        time.sleep(60)
        return 0

    logger.info("=" * 50)
    logger.info("HIMAN Fetch Cycle v2.0 — {}", datetime.now().strftime("%Y-%m-%d %H:%M:%S"))

    # Sabhi sources se jobs fetch karo
    raw = fetch_all_jobs()
    if not raw:
        logger.warning("Koi jobs nahi mili kisi bhi source se.")
        return 0

    # Deduplicate by title
    seen = set()
    unique = []
    for j in raw:
        k = j["title"].lower().strip()
        if k not in seen:
            seen.add(k)
            unique.append(j)

    logger.info("Unique jobs after dedup: {}", len(unique))

    # AI Score
    scored = ai_score(unique)
    shortlisted = [j for j in scored if j.get("shortlisted")]
    logger.info("Shortlisted: {}/{}", len(shortlisted), len(scored))

    # Save top 12 (zyada jobs = zyada bids)
    saved = 0
    for job in shortlisted[:12]:
        if emergency.is_stopped():
            break
        if save_job(job):
            saved += 1
        _delay(2.0, 3.5)

    logger.info("Cycle done: {} jobs saved to DB", saved)

    # Daily stats save karo
    save_daily_stats(fetched=len(raw), saved=saved)

    # Telegram summary
    if settings.telegram_ready and saved > 0:
        try:
            from himan.telegram_alerts import notify_search_summary
            notify_search_summary(len(raw), saved)
        except Exception:
            pass

    return saved


def main():
    interval = int(os.getenv("SEARCH_INTERVAL_MINUTES", "30"))
    logger.info("HIMAN Auto Fetcher v2.0 started! Interval: {} min", interval)
    logger.info("Sources: Freelancer + PeoplePerHour + Guru + Remotive")
    logger.info("Skills: {} categories", len(FREELANCER_SKILLS))

    run_cycle()  # Pehla cycle abhi

    while True:
        logger.info("Next cycle in {} minutes...", interval)
        time.sleep(interval * 60)
        run_cycle()


if __name__ == "__main__":
    main()
