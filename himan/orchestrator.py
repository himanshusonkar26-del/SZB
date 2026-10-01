from __future__ import annotations

from loguru import logger

from himan import emergency, memory
from himan.agents import classify_kind, produce_draft, qc_round, revise_draft
from himan.config import settings
from himan.safety import assess_job
from himan.security import new_id, safe_job_text
from himan.telegram_alerts import notify


class StoppedError(RuntimeError):
    pass


def _guard() -> None:
    if emergency.is_stopped():
        raise StoppedError(emergency.status())


def ingest(title: str, description: str, budget: str = "", source_note: str = "") -> dict:
    memory.init_db()
    _guard()
    title = safe_job_text(title)
    description = safe_job_text(description)
    job_id = new_id("job")
    verdict = assess_job(title, description)
    job = {
        "id": job_id,
        "title": title,
        "description": description,
        "budget": budget,
        "source_note": source_note,
        "status": "blocked" if verdict.blocked else ("needs_review" if verdict.level == "review" else "queued"),
        "safety_level": verdict.level,
        "safety": {
            "level": verdict.level,
            "category": verdict.category,
            "reasons": verdict.reasons,
        },
        "agent_kind": None,
        "draft": "",
        "retries": 0,
    }
    memory.insert_job(job)
    memory.audit("ingest", job_id, verdict.level)
    if verdict.blocked:
        notify(f"HIMAN blocked a job ({job_id}): {verdict.category}")
        return memory.get_job(job_id) or job
    if verdict.level == "review":
        notify(f"HIMAN needs your review ({job_id}): {title[:80]}")
        return memory.get_job(job_id) or job
    return run_job(job_id)


def approve(job_id: str) -> dict:
    _guard()
    job = memory.get_job(job_id)
    if not job:
        raise ValueError("Unknown job")
    if job["safety_level"] == "block" or job["status"] == "blocked":
        raise ValueError("Blocked jobs cannot be approved")
    memory.update_job(job_id, status="queued")
    memory.audit("approve", job_id)
    return run_job(job_id)


def run_job(job_id: str) -> dict:
    _guard()
    job = memory.get_job(job_id)
    if not job:
        raise ValueError("Unknown job")
    if job["status"] == "blocked":
        return job
    if not settings.groq_ready:
        memory.update_job(job_id, status="needs_groq")
        memory.audit("needs_groq", job_id)
        return memory.get_job(job_id) or job

    kind = job.get("agent_kind") or classify_kind(job["title"], job["description"])
    memory.update_job(job_id, agent_kind=kind, status="working")
    memory.audit("assign", job_id, kind)

    draft = produce_draft(kind, job["title"], job["description"], job.get("budget") or "")
    memory.update_job(job_id, draft=draft, status="qc1")

    retries = int(job.get("retries") or 0)
    while True:
        _guard()
        q1 = qc_round("specialist", job["title"], job["description"], draft)
        q2 = qc_round("boss", job["title"], job["description"], draft)
        notes = f"QC1: {q1['notes']}\nQC2: {q2['notes']}"
        passed = bool(q1["pass"] and q2["pass"] and q1["score"] >= 60 and q2["score"] >= 60)
        if passed:
            memory.update_job(job_id, draft=draft, qc_notes=notes, status="ready", retries=retries)
            memory.bump_agent(kind, True)
            memory.audit("ready", job_id)
            notify(f"HIMAN draft ready ({job_id}) — review before you submit it.")
            return memory.get_job(job_id) or job
        retries += 1
        if retries >= settings.max_retries:
            memory.update_job(job_id, draft=draft, qc_notes=notes, status="failed", retries=retries)
            memory.bump_agent(kind, False)
            memory.audit("failed", job_id, notes[:500])
            notify(f"HIMAN failed QC 3 times ({job_id}). Your review needed.")
            return memory.get_job(job_id) or job
        logger.info("QC failed, revising {}", job_id)
        draft = revise_draft(kind, job["title"], job["description"], draft, notes)
        memory.update_job(job_id, draft=draft, qc_notes=notes, retries=retries, status="revising")


def weekly_report() -> str:
    jobs = memory.list_jobs(100)
    agents = memory.list_agents()
    ready = sum(1 for j in jobs if j["status"] == "ready")
    failed = sum(1 for j in jobs if j["status"] == "failed")
    blocked = sum(1 for j in jobs if j["status"] == "blocked")
    earned = memory.month_earnings()
    goal = settings.monthly_goal_usd
    lines = [
        "HIMAN weekly self-report",
        f"Jobs in log: {len(jobs)} | ready: {ready} | failed: {failed} | blocked: {blocked}",
        f"Earnings logged: ${earned:.2f} / goal ${goal:.2f}",
        "Agents:",
    ]
    for a in agents:
        lines.append(f"  {a['label']}: done={a['jobs_done']} fail={a['jobs_failed']} score={a['score']}")
    lines.append("Next: only take jobs that match high-score agents; keep blocked categories off.")
    text = "\n".join(lines)
    memory.audit("weekly_report", None, text[:1500])
    notify(text)
    return text
