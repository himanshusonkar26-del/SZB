"""
HIMAN Pro — Bid Dashboard v2
Daily / Weekly / Monthly Goals + $15 min filter
"""

from __future__ import annotations
import sys, re
from pathlib import Path
from datetime import datetime, timezone, timedelta

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import streamlit as st
from himan import emergency, memory
from himan.config import settings
from himan.security import setup_logging

setup_logging()
memory.init_db()

st.set_page_config(page_title="HIMAN Pro", page_icon="🏢", layout="wide")

# ── helpers ──────────────────────────────────────────────────────────────────

def _budget_usd(raw: str) -> float:
    """Budget string se number nikalo. e.g. '$30-50' → 30.0"""
    if not raw:
        return 0.0
    nums = re.findall(r"\d+\.?\d*", raw)
    return float(nums[0]) if nums else 0.0

def _week_earnings() -> float:
    """Is hafte ki earnings."""
    now = datetime.now(timezone.utc)
    week_start = now - timedelta(days=now.weekday())
    with memory.connect() as conn:
        row = conn.execute(
            "SELECT COALESCE(SUM(amount_usd),0) AS t FROM earnings WHERE at >= ?",
            (week_start.isoformat(),),
        ).fetchone()
    return float(row["t"] if row else 0)

def _day_earnings() -> float:
    """Aaj ki earnings."""
    now = datetime.now(timezone.utc)
    today = now.replace(hour=0, minute=0, second=0, microsecond=0)
    with memory.connect() as conn:
        row = conn.execute(
            "SELECT COALESCE(SUM(amount_usd),0) AS t FROM earnings WHERE at >= ?",
            (today.isoformat(),),
        ).fetchone()
    return float(row["t"] if row else 0)

# ── sidebar ───────────────────────────────────────────────────────────────────
with st.sidebar:
    st.markdown("## 🏢 HIMAN Pro")
    st.caption("AI Freelance Office")

    stopped = emergency.is_stopped()
    if stopped:
        st.error("🛑 STOPPED")
        if st.button("▶️ Resume", use_container_width=True):
            emergency.resume(); st.rerun()
    else:
        st.success("✅ RUNNING")
        if st.button("🛑 Emergency Stop", type="primary", use_container_width=True):
            emergency.stop("dashboard"); st.rerun()

    st.divider()

    # ── Goals sidebar ──
    st.markdown("### 🎯 Goals")

    # Daily goal
    day_goal  = st.number_input("📅 Daily Goal ($)",   min_value=1.0, value=15.0,  step=1.0)
    week_goal = st.number_input("📆 Weekly Goal ($)",  min_value=1.0, value=75.0,  step=5.0)
    mon_goal  = st.number_input("📊 Monthly Goal ($)", min_value=1.0, value=300.0, step=10.0)

    day_earned  = _day_earnings()
    week_earned = _week_earnings()
    mon_earned  = memory.month_earnings()

    # Daily
    day_pct = min(100, day_earned / day_goal * 100) if day_goal else 0
    day_icon = "✅" if day_earned >= day_goal else "🔄"
    st.markdown(f"**{day_icon} Aaj:** ${day_earned:.2f} / ${day_goal:.0f}")
    st.progress(day_pct / 100)

    # Weekly
    wk_pct = min(100, week_earned / week_goal * 100) if week_goal else 0
    wk_icon = "✅" if week_earned >= week_goal else "🔄"
    st.markdown(f"**{wk_icon} Is Hafte:** ${week_earned:.2f} / ${week_goal:.0f}")
    st.progress(wk_pct / 100)

    # Monthly
    mn_pct = min(100, mon_earned / mon_goal * 100) if mon_goal else 0
    mn_icon = "✅" if mon_earned >= mon_goal else "🔄"
    st.markdown(f"**{mn_icon} Is Mahine:** ${mon_earned:.2f} / ${mon_goal:.0f}")
    st.progress(mn_pct / 100)

    st.divider()

    # ── Min budget filter ──
    st.markdown("### 💵 Min Budget Filter")
    min_budget = st.number_input(
        "Itne se kam ki jobs mat dikhao ($)",
        min_value=0.0, value=15.0, step=5.0,
        help="$15 se kam budget wali jobs skip ho jayengi"
    )
    show_no_budget = st.checkbox("Budget nahi likha — phir bhi dikhao?", value=True)

    st.divider()
    st.markdown("### 🔍 Search")
    if st.button("🔍 Abhi Search Karo", use_container_width=True, type="primary"):
        with st.spinner("Searching Freelancer..."):
            try:
                from auto_fetcher import run_cycle
                count = run_cycle()
                st.success(f"✅ {count} nayi jobs!")
                st.rerun()
            except Exception as exc:
                st.error(str(exc))

    st.divider()
    st.caption(f"⚙ {settings.groq_model}")
    st.caption("Groq: " + ("✅" if settings.groq_ready else "❌ key missing"))

# ── Header ───────────────────────────────────────────────────────────────────
st.markdown("# 🏢 HIMAN Pro — Freelance Office")
st.caption("Proposal copy karo → Job kholo → Paste karo → BID KARO → Paise aate hain 💰")

# ── Stats bar ────────────────────────────────────────────────────────────────
jobs_all   = memory.list_jobs(500)
ready_all  = [j for j in jobs_all if j["status"] == "ready"]
queued_all = [j for j in jobs_all if j["status"] == "queued"]
blocked_all= [j for j in jobs_all if j["status"] == "blocked"]
submitted_all = [j for j in jobs_all if j["status"] == "submitted"]

# Apply min budget filter
def _passes_budget(j: dict) -> bool:
    raw = j.get("budget", "") or ""
    amt = _budget_usd(raw)
    if amt == 0:
        return show_no_budget  # budget nahi likha
    return amt >= min_budget

ready_jobs = [j for j in ready_all if _passes_budget(j)]

c1,c2,c3,c4,c5,c6 = st.columns(6)
c1.metric("📋 Total",     len(jobs_all))
c2.metric("⚡ Bid Ready", len(ready_jobs))
c3.metric("🏆 Submit",    len(submitted_all))
c4.metric("🚫 Blocked",   len(blocked_all))
c5.metric("📅 Aaj",       f"${day_earned:.2f}")
c6.metric("📊 Mahina",    f"${mon_earned:.2f}")

# ── Tabs ─────────────────────────────────────────────────────────────────────
tab1, tab2, tab3, tab4, tab5, tab6 = st.tabs([
    "⚡ BID READY", "🔍 Search", "✍️ Job Paste", "📋 Sab Jobs", "💰 Kamaai", "🛡️ Security"
])

# ════════════════════════════════════════════════════════════════════════
# TAB 1 — BID READY
# ════════════════════════════════════════════════════════════════════════
with tab1:
    if not ready_jobs:
        st.warning("😴 Abhi koi bid-ready job nahi hai.")
        st.info("👈 Sidebar mein **'Abhi Search Karo'** dabao — nayi jobs aayengi!")
    else:
        st.success(f"🔥 **{len(ready_jobs)} jobs bid ke liye ready hain! Abhi bid karo!**")
        if min_budget > 0:
            st.caption(f"💵 Filter ON: ${min_budget:.0f} se kam budget wali jobs hide hain")
        st.divider()

        for i, job in enumerate(ready_jobs):
            agent = job.get("agent_kind", "writer")
            agent_icon = {"dev":"💻","writer":"✍️","data":"📊","design":"🎨","marketing":"📣"}.get(agent,"🤖")

            # URL nikalo
            source_url = ""
            src = job.get("source_note","")
            if "http" in src:
                for p in src.split("|"):
                    if "http" in p.strip():
                        source_url = p.strip()
                        break

            # Budget badge
            bgt = job.get("budget","") or ""
            bgt_val = _budget_usd(bgt)
            if bgt_val >= 50:
                bgt_badge = f"🟢 {bgt}"
            elif bgt_val >= 15:
                bgt_badge = f"🟡 {bgt}"
            elif bgt:
                bgt_badge = f"🔴 {bgt}"
            else:
                bgt_badge = "⚪ Budget nahi likha"

            # Card header
            st.markdown(f"### {agent_icon} Job #{i+1} — {job['title'][:65]}")

            col1, col2, col3 = st.columns([3,1,1])
            with col1:
                st.write(f"**Budget:** {bgt_badge}")
                st.write(f"**Type:** {agent.title()} Agent")
            with col2:
                if source_url:
                    st.link_button("🔗 Job Kholo", source_url, use_container_width=True)
            with col3:
                if st.button("✅ Bid Ho Gaya", key=f"done_{job['id']}", use_container_width=True, type="primary"):
                    memory.update_job(job["id"], status="submitted")
                    st.success("✅ Marked!")
                    st.rerun()

            # Proposal box
            draft = job.get("draft","")
            if draft:
                st.markdown("**📋 Proposal — Copy karo (Ctrl+A → Ctrl+C) → Job pe paste karo → BID!**")
                st.text_area("", value=draft, height=180, key=f"prop_{job['id']}")

                c1, c2, c3 = st.columns(3)
                with c1:
                    fb = st.text_input("Improve karna hai?", key=f"fb_{job['id']}", placeholder="e.g. shorter, add Python")
                    if st.button("✨ Improve", key=f"imp_{job['id']}"):
                        if fb:
                            with st.spinner("Improving..."):
                                try:
                                    from proposal_writer import improve_proposal
                                    new = improve_proposal(draft, job["title"], fb)
                                    memory.update_job(job["id"], draft=new)
                                    st.rerun()
                                except Exception as ex:
                                    st.error(str(ex))
                with c2:
                    if st.button("🔄 Naya Proposal", key=f"regen_{job['id']}"):
                        with st.spinner("Writing..."):
                            try:
                                from proposal_writer import write_proposal
                                new = write_proposal(job["title"], job["description"], bgt, agent)
                                memory.update_job(job["id"], draft=new)
                                st.rerun()
                            except Exception as ex:
                                st.error(str(ex))
                with c3:
                    if st.button("⏭️ Skip", key=f"skip_{job['id']}"):
                        memory.update_job(job["id"], status="skipped")
                        st.rerun()
            else:
                if st.button("📝 Proposal Banao", key=f"gen_{job['id']}", type="primary"):
                    with st.spinner("Writing proposal..."):
                        try:
                            from proposal_writer import write_proposal
                            p = write_proposal(job["title"], job["description"], bgt, agent)
                            memory.update_job(job["id"], draft=p)
                            st.rerun()
                        except Exception as ex:
                            st.error(str(ex))

            with st.expander("📄 Job Description"):
                st.write(job.get("description","")[:800])

            st.divider()

# ════════════════════════════════════════════════════════════════════════
# TAB 2 — SEARCH
# ════════════════════════════════════════════════════════════════════════
with tab2:
    st.subheader("🔍 Freelancer.com se Jobs Dhundho")
    st.info("Button dabao — HIMAN khud jaayega, best jobs filter karega, proposals banayega.")

    if st.button("🚀 Search Shuru Karo", type="primary", use_container_width=True):
        pb = st.progress(0, text="Shuru ho raha hai...")
        try:
            from auto_fetcher import fetch_freelancer_jobs, ai_score, save_job
            pb.progress(20, text="Freelancer.com se jobs aa rahi hain...")
            raw = fetch_freelancer_jobs(limit_per_skill=8)
            pb.progress(50, text=f"{len(raw)} jobs mile, AI filter kar raha hoon...")
            scored = ai_score(raw)
            shortlisted = [j for j in scored if j.get("shortlisted")]
            pb.progress(70, text=f"{len(shortlisted)} shortlisted, proposals bana raha hoon...")
            saved = 0
            for j in shortlisted[:10]:
                if save_job(j):
                    saved += 1
            pb.progress(100, text="Ho gaya!")
            st.success(f"✅ {saved} nayi jobs BID READY tab mein hain!")
            st.rerun()
        except Exception as exc:
            st.error(f"Error: {exc}")
            pb.empty()

# ════════════════════════════════════════════════════════════════════════
# TAB 3 — MANUAL JOB
# ════════════════════════════════════════════════════════════════════════
with tab3:
    st.subheader("✍️ Khud Job Paste Karo")
    st.caption("Upwork, Fiverr, ya kisi bhi site se job copy karke yahan do — HIMAN proposal banayega")

    with st.form("manual"):
        title = st.text_input("Job Title *", placeholder="Python script for price scraping")
        col1, col2 = st.columns(2)
        budget = col1.text_input("Budget", placeholder="$50")
        url    = col2.text_input("Job URL", placeholder="https://freelancer.com/...")
        desc   = st.text_area("Job Description *", height=180, placeholder="Yahan description paste karo...")
        go     = st.form_submit_button("🤖 HIMAN ko do", type="primary", use_container_width=True)

        if go:
            if not title or not desc:
                st.error("Title aur description dono zaroori hain!")
            else:
                with st.spinner("Proposal bana raha hoon..."):
                    try:
                        from proposal_writer import write_proposal, _detect_kind
                        from himan.safety import assess_job
                        from himan.security import new_id
                        verdict = assess_job(title, desc)
                        if verdict.blocked:
                            st.error(f"🚫 Blocked: {verdict.category}")
                        else:
                            kind = _detect_kind(title, desc)
                            prop = write_proposal(title, desc, budget, kind)
                            jid  = new_id("job")
                            memory.insert_job({
                                "id": jid, "title": title[:300],
                                "description": desc[:8000], "budget": budget,
                                "source_note": f"manual | {url}",
                                "status": "ready", "safety_level": verdict.level,
                                "safety": {"level": verdict.level, "category": verdict.category, "reasons": verdict.reasons},
                                "agent_kind": kind, "draft": prop, "retries": 0,
                            })
                            st.success("✅ Proposal ready!")
                            st.session_state["last_prop"] = prop
                            st.session_state["last_url"]  = url
                    except Exception as ex:
                        st.error(str(ex))

    if "last_prop" in st.session_state:
        st.divider()
        st.markdown("**📋 Proposal — Copy karo → Bid karo:**")
        st.text_area("", value=st.session_state["last_prop"], height=220)
        if st.session_state.get("last_url"):
            st.link_button("🔗 Job Kholo", st.session_state["last_url"])

# ════════════════════════════════════════════════════════════════════════
# TAB 4 — SAB JOBS
# ════════════════════════════════════════════════════════════════════════
with tab4:
    st.subheader("📋 Sab Jobs")
    col1, col2 = st.columns(2)
    sf = col1.selectbox("Status", ["all","ready","submitted","skipped","blocked","failed","queued"])
    kf = col2.selectbox("Type",   ["all","dev","writer","data","design","marketing"])

    jlist = memory.list_jobs(300)
    if sf != "all": jlist = [j for j in jlist if j.get("status") == sf]
    if kf != "all": jlist = [j for j in jlist if j.get("agent_kind") == kf]

    icons = {"ready":"✅","submitted":"🏆","skipped":"⏭️","blocked":"🚫","failed":"❌","queued":"⏳"}
    st.write(f"**{len(jlist)} jobs**")
    for j in jlist[:60]:
        ico = icons.get(j.get("status",""),"📋")
        with st.expander(f"{ico}  {j['title'][:60]}  — {j.get('status','')}"):
            st.write(f"**Budget:** {j.get('budget') or 'N/A'}  |  **Type:** {j.get('agent_kind','N/A')}")
            if j.get("draft"):
                st.text_area("Proposal:", j["draft"][:1200], height=100, key=f"jl_{j['id']}")
            c1, c2 = st.columns(2)
            if j.get("status") == "ready":
                if c1.button("✅ Bid Done", key=f"bd_{j['id']}"):
                    memory.update_job(j["id"], status="submitted"); st.rerun()
                if c2.button("⏭️ Skip", key=f"sk_{j['id']}"):
                    memory.update_job(j["id"], status="skipped"); st.rerun()

# ════════════════════════════════════════════════════════════════════════
# TAB 5 — KAMAAI (EARNINGS)
# ════════════════════════════════════════════════════════════════════════
with tab5:
    st.subheader("💰 Kamaai Tracker")

    # 3 goal cards
    c1, c2, c3 = st.columns(3)
    with c1:
        st.markdown("### 📅 Aaj")
        dp = min(100, day_earned / day_goal * 100) if day_goal else 0
        st.metric("Kamaya", f"${day_earned:.2f}", delta=f"Goal ${day_goal:.0f}")
        st.progress(dp / 100)
        if day_earned >= day_goal:
            st.success("✅ Daily goal poora!")
        else:
            rem = day_goal - day_earned
            st.info(f"${rem:.2f} aur chahiye")

    with c2:
        st.markdown("### 📆 Is Hafte")
        wp = min(100, week_earned / week_goal * 100) if week_goal else 0
        st.metric("Kamaya", f"${week_earned:.2f}", delta=f"Goal ${week_goal:.0f}")
        st.progress(wp / 100)
        if week_earned >= week_goal:
            st.success("✅ Weekly goal poora!")
        else:
            st.info(f"${week_goal - week_earned:.2f} aur chahiye")

    with c3:
        st.markdown("### 📊 Is Mahine")
        mp = min(100, mon_earned / mon_goal * 100) if mon_goal else 0
        st.metric("Kamaya", f"${mon_earned:.2f}", delta=f"Goal ${mon_goal:.0f}")
        st.progress(mp / 100)
        if mon_earned >= mon_goal:
            st.balloons()
            st.success("🎉 Monthly goal poora!")
        else:
            st.info(f"${mon_goal - mon_earned:.2f} aur chahiye")

    st.divider()
    st.subheader("💵 Payment Mili — Log Karo")
    with st.form("earn"):
        col1, col2 = st.columns(2)
        amt  = col1.number_input("Amount (USD) *", min_value=0.01, step=1.0)
        note = col2.text_input("Note", placeholder="Job ka naam ya Freelancer project")
        if st.form_submit_button("💾 Save Karo", type="primary", use_container_width=True):
            memory.add_earning(float(amt), note)
            if settings.telegram_ready:
                from himan.telegram_alerts import notify_earning
                notify_earning(float(amt), note)
            st.success(f"✅ ${amt:.2f} log ho gaya!")
            st.rerun()


# ════════════════════════════════════════════════════════════════════════
# TAB 6 — SECURITY
# ════════════════════════════════════════════════════════════════════════
with tab6:
    st.subheader("🛡️ HIMAN Security Shield")
    st.caption("Hack, loop, injection, aur leak se bachao")

    col1, col2 = st.columns(2)

    with col1:
        st.markdown("### ✅ Active Protections")
        st.success("🔄 **Loop Protection** — Ek kaam baar baar repeat nahi hoga")
        st.success("⏱️ **Rate Limiter** — Freelancer/Groq ko spam nahi karega")
        st.success("💉 **Injection Blocker** — Koi AI ko manipulate nahi kar sakta")
        st.success("🔒 **Key Encryption** — API keys encrypted hain (Fernet)")
        st.success("📝 **Secret Masker** — Logs mein keys nahi dikhti")
        st.success("🚫 **Scam Blocker** — Fraud jobs automatically block hoti hain")
        st.success("🛑 **Emergency Stop** — Ek click mein sab band")
        st.success("💥 **Crash Guard** — Error aaye toh auto retry")

    with col2:
        st.markdown("### 🔍 Security Check")
        if st.button("🔍 Abhi Check Karo", type="primary", use_container_width=True):
            with st.spinner("Checking..."):
                try:
                    from himan.shield import full_security_check
                    results = full_security_check()
                    score = results.pop("score", "?/?")
                    safe  = results.pop("safe", False)

                    if safe:
                        st.success(f"✅ System SAFE — Score: {score}")
                    else:
                        st.warning(f"⚠️ Kuch issues hain — Score: {score}")

                    for check, passed in results.items():
                        name = check.replace("_", " ").title()
                        if passed:
                            st.write(f"✅ {name}")
                        else:
                            st.write(f"❌ {name}")
                except Exception as exc:
                    st.error(f"Check failed: {exc}")

    st.divider()

    st.markdown("### 📋 Security Log")
    sec_log = ROOT / "logs" / "security.log"
    if sec_log.exists():
        lines = sec_log.read_text(encoding="utf-8", errors="ignore").strip().split("\n")
        last_20 = lines[-20:] if len(lines) > 20 else lines
        st.code("\n".join(reversed(last_20)))
    else:
        st.info("Abhi tak koi security event nahi hua. System clean hai ✅")

    st.divider()
    st.markdown("### ⚠️ Kya Protect NAHI Karta")
    st.warning(
        "HIMAN ek LOCAL tool hai — internet pe publicly accessible nahi hai. "
        "Lekin yeh dhyan rakho:\n"
        "- `.env` file kisi ko mat dikhao (API keys hain)\n"
        "- `data/himan.db` file share mat karo (proposals hain)\n"
        "- `data/master.key` file SECRET hai — delete mat karo\n"
        "- Public WiFi pe kaam karo toh VPN use karo"
    )
