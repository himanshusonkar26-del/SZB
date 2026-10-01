"""
HIMAN Pro — Freelance Office Dashboard
=======================================
8 departments · 32 agents · 15+ sources
Bid aap khud karo — account safe rehta hai.
"""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import streamlit as st

from himan import emergency, memory, orchestrator
from himan.config import settings
from himan.security import setup_logging
from himan.telegram_alerts import (
    notify_earning,
    notify_emergency_stop,
    notify_system_started,
    notify_weekly_report,
)

# ---------------------------------------------------------------------------
# Init
# ---------------------------------------------------------------------------
setup_logging()
memory.init_db()

st.set_page_config(
    page_title="HIMAN Pro — Freelance Office",
    page_icon="🏢",
    layout="wide",
    initial_sidebar_state="expanded",
)

# ---------------------------------------------------------------------------
# Password gate
# ---------------------------------------------------------------------------
if settings.dashboard_password:
    if "ok" not in st.session_state:
        st.session_state.ok = False
    if not st.session_state.ok:
        st.title("🔒 HIMAN Pro")
        pw = st.text_input("Dashboard password", type="password")
        if st.button("Unlock") and pw == settings.dashboard_password:
            st.session_state.ok = True
            st.rerun()
        st.stop()

# ---------------------------------------------------------------------------
# Sidebar
# ---------------------------------------------------------------------------
with st.sidebar:
    st.title("🏢 HIMAN Pro")
    st.caption("AI Freelance Office")

    # Status
    stopped = emergency.is_stopped()
    if stopped:
        st.error("🛑 STOPPED")
    else:
        st.success("✅ RUNNING")

    if st.button("🛑 EMERGENCY STOP", type="primary", use_container_width=True):
        emergency.stop("dashboard")
        notify_emergency_stop("dashboard button")
        st.rerun()

    if stopped and st.button("▶️ Resume", use_container_width=True):
        emergency.resume()
        st.rerun()

    st.divider()

    # API status
    st.caption(f"⚙ groq · {settings.groq_model}")
    if settings.groq_ready:
        st.success("API key ✓")
    else:
        st.error("API key missing!")

    groq_key = st.text_input("Groq API key", type="password", value=settings.groq_api_key)
    if st.button("Key save karo", use_container_width=True):
        env_path = ROOT / ".env"
        lines = env_path.read_text(encoding="utf-8").splitlines()
        new_lines = []
        replaced = False
        for line in lines:
            if line.startswith("GROQ_API_KEY="):
                new_lines.append(f"GROQ_API_KEY={groq_key}")
                replaced = True
            else:
                new_lines.append(line)
        if not replaced:
            new_lines.append(f"GROQ_API_KEY={groq_key}")
        env_path.write_text("\n".join(new_lines) + "\n", encoding="utf-8")
        st.success("Saved! Restart karein.")

    st.caption("Telegram: " + ("on ✓" if settings.telegram_ready else "off (optional)"))

# ---------------------------------------------------------------------------
# Header
# ---------------------------------------------------------------------------
st.title("🏢 HIMAN Pro — Freelance Office")
st.caption(
    "8 departments · 32 agents · 15+ sources · "
    "Auto backup failover · **Bid aap khud karo** — account safe rehta hai."
)

# ---------------------------------------------------------------------------
# Tabs
# ---------------------------------------------------------------------------
tab_home, tab_office, tab_search, tab_paste, tab_jobs, tab_agents, tab_earn, tab_comms, tab_reports, tab_health = st.tabs([
    "🏠 Home", "🏢 Office", "🔍 Search", "📋 Job Paste",
    "💼 Jobs", "🤖 Agents", "💰 Earnings", "💬 Client Comms",
    "📊 Reports", "❤️ Health"
])

# ============================================================
# TAB 1 — HOME
# ============================================================
with tab_home:
    jobs = memory.list_jobs(500)
    agents = memory.list_agents()

    c1, c2, c3, c4, c5, c6 = st.columns(6)
    c1.metric("📋 Total Jobs", len(jobs))
    c2.metric("✅ Shortlisted", sum(1 for j in jobs if j.get("status") == "ready"))
    c3.metric("📝 Proposals", 0)
    c4.metric("🏆 Won", 0)
    c5.metric("🚫 Rejected", sum(1 for j in jobs if j.get("status") == "blocked"))
    earned = memory.month_earnings()
    c6.metric("💵 Earned", f"${earned:.2f}")

    goal = settings.monthly_goal_usd
    pct = min(100, (earned / goal * 100)) if goal > 0 else 0
    st.write(f"**Goal:** ${earned:.2f} / {goal:.0f} ({pct:.0f}%)")
    st.progress(pct / 100)

    # Quick actions
    queued = [j for j in jobs if j["status"] == "queued"]
    review = [j for j in jobs if j["status"] == "needs_review"]

    if queued:
        col1, col2 = st.columns([3, 1])
        col1.warning(f"⚠️ {len(queued)} nayi jobs pending")
        if col2.button(f"⚡ Process ({len(queued)})", type="primary"):
            with st.spinner("Processing..."):
                for j in queued[:5]:
                    try:
                        orchestrator.run_job(j["id"])
                    except Exception as exc:
                        st.error(str(exc))
            st.rerun()

    if review:
        st.info(f"🔄 {len(review)} skipped jobs — re-triage hogi")

    # Live Activity Log
    st.subheader("📋 Live Activity Log")
    audit = memory.recent_audit(20)
    if audit:
        st.dataframe(
            [{"time": a["at"][:19], "action": a["action"], "job": a.get("job_id") or "", "detail": (a.get("detail") or "")[:80]} for a in audit],
            use_container_width=True,
            hide_index=True,
        )
    else:
        st.info("Koi activity nahi abhi tak.")

# ============================================================
# TAB 2 — OFFICE
# ============================================================
with tab_office:
    st.subheader("🏢 HIMAN Office Overview")

    col1, col2 = st.columns(2)
    with col1:
        st.info("**Boss Agent** — Kaam assign karta hai, QC karta hai")
        st.info("**Search Agents** — Freelancer.com se jobs dhundhen")
        st.info("**Dev Agent** — Coding, Scripts, APIs")
        st.info("**Writer Agent** — Articles, Blogs, SEO")

    with col2:
        st.info("**Data Agent** — Excel, Research, Reports")
        st.info("**Design Agent** — Briefs, Layout, Prompts")
        st.info("**Marketing Agent** — Ads, Social, Email")
        st.info("**Safety Agent** — Scam detect, Block kare")

    st.divider()
    st.subheader("⚙️ Settings")

    col1, col2 = st.columns(2)
    with col1:
        st.metric("Max Agents", settings.max_agents)
        st.metric("Max Retries", settings.max_retries)
        st.metric("Monthly Goal", f"${settings.monthly_goal_usd:.0f}")
    with col2:
        st.metric("Safety System", "ON ✓" if settings.safety_enabled else "OFF")
        st.metric("Groq Model", settings.groq_model)
        st.metric("Log Level", settings.log_level)

    if st.button("🔔 Test Telegram", use_container_width=False):
        from himan.telegram_alerts import notify
        notify("Test message from HIMAN Pro dashboard!")
        st.success("Telegram test bheja!")

# ============================================================
# TAB 3 — SEARCH
# ============================================================
with tab_search:
    st.subheader("🔍 Job Search Agent")
    st.caption("Freelancer.com se AI-filtered jobs dhundho")

    col1, col2, col3 = st.columns(3)
    limit = col1.slider("Kitne jobs fetch karein", 10, 80, 40)
    shortlist_only = col2.checkbox("Sirf shortlisted dikhao", value=True)
    auto_ingest = col3.checkbox("Shortlisted jobs auto-queue karein", value=False)

    if st.button("🔍 Search Now", type="primary", use_container_width=True):
        with st.spinner("Freelancer.com se jobs dhundh raha hoon..."):
            try:
                sys.path.insert(0, str(ROOT))
                from agents.search_agent import run_search
                results = run_search(limit=limit, shortlist_only=shortlist_only)
                st.session_state["search_results"] = results
                shortlisted_count = sum(1 for r in results if r.get("shortlisted"))

                # Telegram alert
                from himan.telegram_alerts import notify_search_summary
                notify_search_summary(len(results), shortlisted_count)

                st.success(f"✅ {len(results)} jobs mile | {shortlisted_count} shortlisted")

                # Auto ingest
                if auto_ingest:
                    ingested = 0
                    for r in results:
                        if r.get("shortlisted"):
                            try:
                                memory.init_db()
                                from himan.security import safe_job_text, new_id
                                from himan.safety import assess_job
                                verdict = assess_job(r["title"], r["description"])
                                job = {
                                    "id": new_id("job"),
                                    "title": r["title"][:300],
                                    "description": r["description"][:10000],
                                    "budget": r.get("budget", ""),
                                    "source_note": r.get("source", "search_agent"),
                                    "status": "blocked" if verdict.blocked else "queued",
                                    "safety_level": verdict.level,
                                    "safety": {"level": verdict.level, "category": verdict.category, "reasons": verdict.reasons},
                                    "agent_kind": None,
                                    "draft": "",
                                    "retries": 0,
                                }
                                memory.insert_job(job)
                                ingested += 1
                            except Exception:
                                pass
                    if ingested:
                        st.info(f"✅ {ingested} jobs queue mein add ho gaye.")
            except Exception as exc:
                st.error(f"Search failed: {exc}")

    # Show results
    if "search_results" in st.session_state:
        results = st.session_state["search_results"]
        if results:
            st.divider()
            st.write(f"**{len(results)} jobs mile:**")
            for i, job in enumerate(results[:30]):
                score = job.get("score", 0)
                sl = job.get("shortlisted", False)
                icon = "✅" if sl else "⬜"
                color = "🟢" if score >= 70 else "🟡" if score >= 50 else "🔴"

                with st.expander(f"{icon} {color} [{score}] {job['title'][:80]}"):
                    col1, col2 = st.columns([3, 1])
                    with col1:
                        st.write(f"**Budget:** {job.get('budget') or 'N/A'}")
                        st.write(f"**Source:** {job.get('source', '')}")
                        st.write(f"**AI Reason:** {job.get('reason', '')}")
                        if job.get("url"):
                            st.markdown(f"[🔗 View Job]({job['url']})")
                        st.write(job.get("description", "")[:500])
                    with col2:
                        if st.button("➕ Queue Karo", key=f"q_{i}"):
                            try:
                                from himan.security import new_id
                                from himan.safety import assess_job
                                verdict = assess_job(job["title"], job["description"])
                                j = {
                                    "id": new_id("job"),
                                    "title": job["title"][:300],
                                    "description": job["description"][:10000],
                                    "budget": job.get("budget", ""),
                                    "source_note": job.get("source", "search"),
                                    "status": "blocked" if verdict.blocked else "queued",
                                    "safety_level": verdict.level,
                                    "safety": {"level": verdict.level, "category": verdict.category, "reasons": verdict.reasons},
                                    "agent_kind": None, "draft": "", "retries": 0,
                                }
                                memory.insert_job(j)
                                st.success("Queued!")
                            except Exception as ex:
                                st.error(str(ex))
        else:
            st.warning("Koi jobs nahi mili.")

# ============================================================
# TAB 4 — JOB PASTE
# ============================================================
with tab_paste:
    st.subheader("📋 Job Manually Paste Karo")
    st.caption("Koi bhi job copy karke yahan paste karo — HIMAN draft banayega")

    with st.form("ingest_form"):
        title = st.text_input("Job Title *", placeholder="e.g. Python automation script needed")
        col1, col2 = st.columns(2)
        budget = col1.text_input("Budget (optional)", placeholder="e.g. $50-100")
        source = col2.selectbox("Source", ["freelancer", "fiverr", "upwork", "linkedin", "direct", "other"])
        description = st.text_area("Job Description *", height=200, placeholder="Yahan job description paste karo...")
        submitted = st.form_submit_button("🚀 HIMAN ko do", type="primary", use_container_width=True)

        if submitted:
            if not title or not description:
                st.error("Title aur description dono zaroori hain!")
            else:
                with st.spinner("HIMAN kaam kar raha hai..."):
                    try:
                        job = orchestrator.ingest(title, description, budget, source)
                        st.session_state["last_job"] = job["id"]
                        status = job["status"]
                        if status == "ready":
                            st.success(f"✅ Draft ready! Job ID: {job['id']}")
                        elif status == "blocked":
                            st.error(f"🚫 Job blocked: {job.get('safety', {}).get('category', 'unsafe')}")
                        elif status == "needs_review":
                            st.warning(f"⚠️ Review needed: {job['id']}")
                        else:
                            st.info(f"Status: {status} | ID: {job['id']}")
                    except orchestrator.StoppedError as exc:
                        st.error(str(exc))
                    except Exception as exc:
                        st.error(f"Error: {exc}")

    # Show last job result
    if "last_job" in st.session_state:
        job_id = st.session_state["last_job"]
        job = memory.get_job(job_id)
        if job and job.get("draft"):
            st.divider()
            st.subheader(f"📝 Draft: {job['title'][:60]}")
            st.text_area("HIMAN ka draft (copy karo, khud submit karo):", job["draft"], height=400)
            if job.get("qc_notes"):
                with st.expander("QC Notes"):
                    st.code(job["qc_notes"])

# ============================================================
# TAB 5 — JOBS
# ============================================================
with tab_jobs:
    st.subheader("💼 All Jobs")

    # Filter
    status_filter = st.selectbox(
        "Status filter",
        ["all", "queued", "ready", "blocked", "needs_review", "failed", "working"],
    )

    jobs = memory.list_jobs(200)
    if status_filter != "all":
        jobs = [j for j in jobs if j.get("status") == status_filter]

    if not jobs:
        st.info("Koi jobs nahi is filter mein.")
    else:
        st.write(f"**{len(jobs)} jobs:**")
        for j in jobs:
            status = j.get("status", "")
            icon = {"ready": "✅", "blocked": "🚫", "failed": "❌", "working": "⚙️", "queued": "⏳"}.get(status, "📋")
            with st.expander(f"{icon} [{status}] {j['title'][:70]}"):
                col1, col2 = st.columns([3, 1])
                with col1:
                    st.write(f"**ID:** `{j['id']}`")
                    st.write(f"**Safety:** {j.get('safety_level', 'N/A')} | **Agent:** {j.get('agent_kind', 'N/A')}")
                    st.write(f"**Created:** {j.get('created_at', '')[:19]}")
                    if j.get("draft"):
                        st.text_area("Draft:", j["draft"][:2000], height=150, key=f"d_{j['id']}")
                with col2:
                    if status == "needs_review":
                        if st.button("✅ Approve", key=f"ap_{j['id']}"):
                            try:
                                orchestrator.approve(j["id"])
                                st.rerun()
                            except Exception as ex:
                                st.error(str(ex))

# ============================================================
# TAB 6 — AGENTS
# ============================================================
with tab_agents:
    st.subheader("🤖 Agent Performance")

    agents = memory.list_agents()
    if agents:
        # Score bars
        for a in agents:
            score = a.get("score", 50)
            done = a.get("jobs_done", 0)
            failed = a.get("jobs_failed", 0)
            col1, col2, col3 = st.columns([2, 3, 1])
            col1.write(f"**{a['label']}**")
            col2.progress(score / 100, text=f"Score: {score:.0f}/100")
            col3.write(f"✅{done} ❌{failed}")
        st.divider()
        st.dataframe(agents, use_container_width=True, hide_index=True)
    else:
        st.info("Koi agents nahi abhi tak.")

    st.subheader("🤖 Dynamic Agent Pool")
    st.info(
        "HIMAN automatically kaam ke type ke hisab se agent assign karta hai.\n"
        "• Dev kaam → Dev Agent\n"
        "• Writing → Writer Agent\n"
        "• Data → Data Agent\n"
        "• Design → Design Agent\n"
        "• Marketing → Marketing Agent"
    )

# ============================================================
# TAB 7 — EARNINGS
# ============================================================
with tab_earn:
    st.subheader("💰 Earnings Tracker")

    earned = memory.month_earnings()
    goal = settings.monthly_goal_usd
    pct = min(100, (earned / goal * 100)) if goal > 0 else 0

    col1, col2, col3 = st.columns(3)
    col1.metric("💵 Total Earned", f"${earned:.2f}")
    col2.metric("🎯 Monthly Goal", f"${goal:.0f}")
    col3.metric("📈 Progress", f"{pct:.0f}%")

    st.progress(pct / 100)

    if pct >= 100:
        st.balloons()
        st.success("🎉 Monthly goal poora ho gaya! Mubarak ho!")

    st.divider()
    st.subheader("Log a Payment")
    with st.form("earn_form"):
        col1, col2 = st.columns(2)
        amt = col1.number_input("Amount (USD) *", min_value=0.01, step=1.0)
        note = col2.text_input("Note (optional)", placeholder="e.g. Freelancer project #123")
        if st.form_submit_button("💾 Save Earning", type="primary"):
            memory.add_earning(float(amt), note)
            notify_earning(float(amt), note)
            st.success(f"✅ ${amt:.2f} logged! Total: ${memory.month_earnings():.2f}")
            st.rerun()

# ============================================================
# TAB 8 — CLIENT COMMS
# ============================================================
with tab_comms:
    st.subheader("💬 Client Communications")
    st.caption("Client se baatcheet ke liye AI help lo — tum khud bhejo")

    with st.form("comms_form"):
        scenario = st.selectbox("Situation kya hai?", [
            "Client ko proposal bhejni hai",
            "Client ke sawal ka jawab dena hai",
            "Revision maang raha hai client",
            "Payment follow-up karna hai",
            "Project complete karne ka message",
            "Negative review handle karna hai",
        ])
        context = st.text_area("Details do (job, client, kya hua):", height=120)
        if st.form_submit_button("✍️ Message Draft Karo", type="primary"):
            if not context:
                st.error("Context dena zaroori hai!")
            else:
                with st.spinner("Draft bana raha hoon..."):
                    try:
                        from himan.llm import chat_text
                        msg = chat_text([
                            {
                                "role": "system",
                                "content": (
                                    "You are HIMAN Client Comms. Write professional freelancer messages. "
                                    "Be polite, confident, clear. Keep it short. "
                                    "The human will review and send it themselves."
                                ),
                            },
                            {
                                "role": "user",
                                "content": f"Scenario: {scenario}\n\nContext: {context}",
                            },
                        ], temperature=0.5)
                        st.text_area("📝 Draft (copy karke khud bhejo):", msg, height=200)
                    except Exception as exc:
                        st.error(f"Error: {exc}")

# ============================================================
# TAB 9 — REPORTS
# ============================================================
with tab_reports:
    st.subheader("📊 Reports")

    col1, col2 = st.columns(2)
    with col1:
        if st.button("📊 Weekly Report Banao", type="primary", use_container_width=True):
            with st.spinner("Report bana raha hoon..."):
                report = orchestrator.weekly_report()
                notify_weekly_report(report)
                st.code(report)

    with col2:
        if st.button("📋 Full Audit Log", use_container_width=True):
            audit = memory.recent_audit(100)
            st.dataframe(
                [{"time": a["at"][:19], "action": a["action"], "job": a.get("job_id") or "", "detail": (a.get("detail") or "")[:100]} for a in audit],
                use_container_width=True, hide_index=True,
            )

    st.divider()
    st.subheader("📈 Job Stats")
    jobs = memory.list_jobs(500)
    if jobs:
        from collections import Counter
        status_counts = Counter(j.get("status") for j in jobs)
        kind_counts = Counter(j.get("agent_kind") for j in jobs if j.get("agent_kind"))

        col1, col2 = st.columns(2)
        with col1:
            st.write("**Status breakdown:**")
            for status, count in status_counts.most_common():
                st.write(f"- {status}: {count}")
        with col2:
            if kind_counts:
                st.write("**Agent usage:**")
                for kind, count in kind_counts.most_common():
                    st.write(f"- {kind}: {count}")

# ============================================================
# TAB 10 — HEALTH
# ============================================================
with tab_health:
    st.subheader("❤️ System Health")

    checks = {
        "Groq API": settings.groq_ready,
        "Telegram": settings.telegram_ready,
        "Safety System": settings.safety_enabled,
        "Database": True,
        "Emergency Stop": not emergency.is_stopped(),
    }

    for name, ok in checks.items():
        icon = "✅" if ok else "❌"
        color = "green" if ok else "red"
        st.write(f"{icon} **{name}**")

    st.divider()

    # Quick test
    if st.button("🧪 Test Groq API"):
        if not settings.groq_ready:
            st.error("Groq API key nahi hai!")
        else:
            with st.spinner("Testing..."):
                try:
                    from himan.llm import chat_text
                    resp = chat_text([{"role": "user", "content": "Say OK"}])
                    st.success(f"✅ Groq working! Response: {resp[:100]}")
                except Exception as exc:
                    st.error(f"❌ Failed: {exc}")

    if st.button("🧪 Test Telegram"):
        from himan.telegram_alerts import notify
        notify("✅ HIMAN Health Check OK!")
        st.success("Telegram test bheja! Check karo.")

    if st.button("🗑️ Clear Emergency Stop"):
        emergency.resume()
        st.success("Emergency stop cleared!")
        st.rerun()
