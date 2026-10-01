"""
HIMAN Search Agent
==================
Freelancer.com se jobs dhundta hai — AI filter karta hai best jobs.
Human-like behavior hai taaki platform detect na kare.
"""

from __future__ import annotations

import json
import random
import time
from dataclasses import dataclass
from typing import Any

import httpx
from loguru import logger

from himan.config import settings
from himan.llm import chat_json

# ---------------------------------------------------------------------------
# Job dataclass
# ---------------------------------------------------------------------------

@dataclass
class RawJob:
    title: str
    description: str
    budget: str
    source: str
    url: str = ""


# ---------------------------------------------------------------------------
# Human-like delay helper
# ---------------------------------------------------------------------------

def _delay(lo: float = 1.5, hi: float = 4.0) -> None:
    """Random sleep — human jaise."""
    time.sleep(random.uniform(lo, hi))


# ---------------------------------------------------------------------------
# Freelancer RSS / Public search  (no login needed)
# ---------------------------------------------------------------------------

FREELANCER_RSS = "https://www.freelancer.com/rss/job/jobs.xml"

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/124.0.0.0 Safari/537.36"
    ),
    "Accept-Language": "en-US,en;q=0.9",
    "Accept": "application/rss+xml,application/xml,*/*",
}


def _parse_rss(xml_text: str) -> list[RawJob]:
    """RSS XML se jobs parse karo."""
    try:
        import xml.etree.ElementTree as ET
        root = ET.fromstring(xml_text)
        channel = root.find("channel")
        if channel is None:
            return []
        jobs: list[RawJob] = []
        for item in channel.findall("item"):
            title = (item.findtext("title") or "").strip()
            desc = (item.findtext("description") or "").strip()
            link = (item.findtext("link") or "").strip()
            if not title:
                continue
            # Budget RSS me nahi hota — blank rakhenge
            jobs.append(RawJob(
                title=title[:300],
                description=desc[:3000],
                budget="",
                source="freelancer_rss",
                url=link,
            ))
        return jobs
    except Exception as exc:
        logger.warning("RSS parse error: {}", exc)
        return []


def fetch_freelancer_rss(limit: int = 30) -> list[RawJob]:
    """Freelancer RSS se latest jobs fetch karo."""
    _delay(1.0, 2.5)
    try:
        resp = httpx.get(
            FREELANCER_RSS,
            headers=HEADERS,
            timeout=20,
            follow_redirects=True,
        )
        resp.raise_for_status()
        jobs = _parse_rss(resp.text)
        logger.info("Freelancer RSS: {} jobs fetched", len(jobs))
        return jobs[:limit]
    except Exception as exc:
        logger.error("Freelancer RSS failed: {}", exc)
        return []


# ---------------------------------------------------------------------------
# Freelancer public search API (open endpoint)
# ---------------------------------------------------------------------------

FREELANCER_SEARCH_API = "https://www.freelancer.com/api/projects/0.1/projects/active/"

SEARCH_PARAMS = {
    "compact": "true",
    "full_description": "true",
    "job_details": "true",
    "limit": "50",
    "offset": "0",
    "sort_field": "time_updated",
    "or_jobs[]": [
        "python",
        "web-scraping",
        "data-entry",
        "content-writing",
        "automation",
        "web-development",
        "seo",
        "virtual-assistant",
    ],
}

def fetch_freelancer_api(limit: int = 40) -> list[RawJob]:
    """Freelancer public API se jobs fetch karo."""
    _delay(2.0, 4.0)
    try:
        resp = httpx.get(
            FREELANCER_SEARCH_API,
            params=SEARCH_PARAMS,
            headers={**HEADERS, "Accept": "application/json"},
            timeout=25,
            follow_redirects=True,
        )
        resp.raise_for_status()
        data = resp.json()
        projects = (
            data.get("result", {}).get("projects", [])
            or data.get("projects", [])
        )
        jobs: list[RawJob] = []
        for p in projects[:limit]:
            title = (p.get("title") or "").strip()
            desc = (p.get("description") or "").strip()
            bid_min = p.get("minimum_budget", "") or ""
            bid_max = p.get("maximum_budget", "") or ""
            budget = f"${bid_min}-${bid_max}" if bid_min or bid_max else ""
            seo_url = p.get("seo_url") or ""
            url = f"https://www.freelancer.com/projects/{seo_url}" if seo_url else ""
            if not title:
                continue
            jobs.append(RawJob(
                title=title[:300],
                description=desc[:3000],
                budget=budget,
                source="freelancer_api",
                url=url,
            ))
        logger.info("Freelancer API: {} jobs fetched", len(jobs))
        return jobs
    except Exception as exc:
        logger.warning("Freelancer API failed ({}), falling back to RSS", type(exc).__name__)
        return fetch_freelancer_rss(limit)


# ---------------------------------------------------------------------------
# AI Filter — kaunsa job lene layak hai
# ---------------------------------------------------------------------------

SKILLS = [
    "python", "automation", "web scraping", "data entry", "content writing",
    "seo", "web development", "virtual assistant", "research", "excel",
    "wordpress", "chatbot", "api", "javascript", "html", "css",
]

def _ai_score_jobs(jobs: list[RawJob]) -> list[dict[str, Any]]:
    """AI se har job ko score karwao 0-100."""
    if not settings.groq_ready or not jobs:
        # No AI — simple keyword filter
        results = []
        for j in jobs:
            blob = (j.title + " " + j.description).lower()
            skill_hits = sum(1 for s in SKILLS if s in blob)
            results.append({
                "title": j.title,
                "description": j.description,
                "budget": j.budget,
                "source": j.source,
                "url": j.url,
                "score": skill_hits * 10,
                "reason": f"{skill_hits} skill match",
                "shortlisted": skill_hits >= 2,
            })
        return results

    # Batch scoring — 10 jobs ek baar mein
    batch_size = 10
    all_results: list[dict[str, Any]] = []

    for i in range(0, len(jobs), batch_size):
        batch = jobs[i : i + batch_size]
        items_json = json.dumps(
            [{"i": idx, "title": j.title, "desc": j.description[:800]} for idx, j in enumerate(batch)]
        )
        try:
            data = chat_json([
                {
                    "role": "system",
                    "content": (
                        "You are HIMAN Search Agent. Score freelance jobs 0-100 for this profile:\n"
                        f"Skills: {', '.join(SKILLS)}\n"
                        "Return JSON: {\"scores\": [{\"i\":0, \"score\":75, \"reason\":\"good match\", \"shortlisted\":true}, ...]}\n"
                        "shortlisted=true if score>=60. Be honest. No illegal/scam jobs."
                    ),
                },
                {"role": "user", "content": items_json},
            ])
            scores = data.get("scores", [])
            if not isinstance(scores, list):
                scores = []
            for item in scores:
                idx = int(item.get("i", 0))
                if idx >= len(batch):
                    continue
                j = batch[idx]
                all_results.append({
                    "title": j.title,
                    "description": j.description,
                    "budget": j.budget,
                    "source": j.source,
                    "url": j.url,
                    "score": int(item.get("score", 0)),
                    "reason": str(item.get("reason", "")),
                    "shortlisted": bool(item.get("shortlisted", False)),
                })
            _delay(0.5, 1.2)
        except Exception as exc:
            logger.warning("AI scoring failed for batch {}: {}", i, exc)
            for j in batch:
                all_results.append({
                    "title": j.title,
                    "description": j.description,
                    "budget": j.budget,
                    "source": j.source,
                    "url": j.url,
                    "score": 50,
                    "reason": "ai_unavailable",
                    "shortlisted": True,
                })

    return all_results


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def run_search(limit: int = 40, shortlist_only: bool = False) -> list[dict[str, Any]]:
    """
    Main function — search karo, AI filter karo, result return karo.

    Returns list of dicts with keys:
      title, description, budget, source, url, score, reason, shortlisted
    """
    logger.info("HIMAN Search Agent starting...")

    # 1. Fetch jobs
    raw = fetch_freelancer_api(limit=limit)
    if not raw:
        logger.warning("No jobs fetched.")
        return []

    # 2. Remove duplicates by title
    seen: set[str] = set()
    unique: list[RawJob] = []
    for j in raw:
        key = j.title.lower().strip()
        if key not in seen:
            seen.add(key)
            unique.append(j)

    # 3. AI scoring
    scored = _ai_score_jobs(unique)

    # 4. Sort by score
    scored.sort(key=lambda x: x["score"], reverse=True)

    if shortlist_only:
        return [j for j in scored if j["shortlisted"]]

    return scored


def get_top_jobs(n: int = 10) -> list[dict[str, Any]]:
    """Sirf top N shortlisted jobs do."""
    results = run_search(limit=60, shortlist_only=True)
    return results[:n]
