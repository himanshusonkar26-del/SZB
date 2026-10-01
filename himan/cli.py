from __future__ import annotations

import argparse
from pathlib import Path

from rich.console import Console
from rich.table import Table

from himan import emergency, memory, orchestrator
from himan.config import settings
from himan.security import setup_logging

console = Console()


def _print_job(job: dict) -> None:
    console.print(f"[bold]{job['id']}[/bold]  {job['status']}  safety={job.get('safety_level')}")
    console.print(f"  {job['title']}")
    if job.get("agent_kind"):
        console.print(f"  agent: {job['agent_kind']}")
    if job.get("draft"):
        console.print("\n[bold]Draft[/bold]\n")
        console.print(job["draft"][:8000])
    if job.get("qc_notes"):
        console.print("\n[bold]QC[/bold]")
        console.print(job["qc_notes"][:2000])


def cmd_ingest(args: argparse.Namespace) -> None:
    description = args.description
    if args.file:
        description = Path(args.file).read_text(encoding="utf-8")
    if not description:
        raise SystemExit("Provide --description or --file")
    job = orchestrator.ingest(args.title, description, args.budget or "", args.source or "manual")
    _print_job(job)


def cmd_list(_: argparse.Namespace) -> None:
    memory.init_db()
    table = Table(title="HIMAN jobs")
    table.add_column("id")
    table.add_column("status")
    table.add_column("safety")
    table.add_column("agent")
    table.add_column("title")
    for j in memory.list_jobs():
        table.add_row(j["id"], j["status"], j.get("safety_level") or "", j.get("agent_kind") or "", j["title"][:40])
    console.print(table)
    console.print(emergency.status())
    console.print(f"Goal ${settings.monthly_goal_usd:.0f} | logged ${memory.month_earnings():.2f}")


def cmd_show(args: argparse.Namespace) -> None:
    memory.init_db()
    job = memory.get_job(args.job_id)
    if not job:
        raise SystemExit("Job not found")
    _print_job(job)


def cmd_approve(args: argparse.Namespace) -> None:
    _print_job(orchestrator.approve(args.job_id))


def cmd_earn(args: argparse.Namespace) -> None:
    memory.init_db()
    memory.add_earning(args.amount, args.note or "")
    console.print(f"Logged ${args.amount:.2f}. Total ${memory.month_earnings():.2f}")


def cmd_stop(_: argparse.Namespace) -> None:
    emergency.stop("cli")
    console.print(emergency.status())


def cmd_resume(_: argparse.Namespace) -> None:
    emergency.resume()
    console.print("running")


def cmd_report(_: argparse.Namespace) -> None:
    memory.init_db()
    console.print(orchestrator.weekly_report())


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog="himan", description="HIMAN local work assistant")
    sub = p.add_subparsers(dest="cmd", required=True)

    ing = sub.add_parser("ingest", help="Paste a job for HIMAN to draft")
    ing.add_argument("--title", required=True)
    ing.add_argument("--description", default="")
    ing.add_argument("--file", default="")
    ing.add_argument("--budget", default="")
    ing.add_argument("--source", default="manual")
    ing.set_defaults(func=cmd_ingest)

    ls = sub.add_parser("list", help="Show jobs")
    ls.set_defaults(func=cmd_list)

    sh = sub.add_parser("show", help="Show one job draft")
    sh.add_argument("job_id")
    sh.set_defaults(func=cmd_show)

    ap = sub.add_parser("approve", help="Run a needs_review job")
    ap.add_argument("job_id")
    ap.set_defaults(func=cmd_approve)

    er = sub.add_parser("earn", help="Log a payment you already received")
    er.add_argument("amount", type=float)
    er.add_argument("--note", default="")
    er.set_defaults(func=cmd_earn)

    st = sub.add_parser("stop", help="Emergency stop")
    st.set_defaults(func=cmd_stop)

    rs = sub.add_parser("resume", help="Clear emergency stop")
    rs.set_defaults(func=cmd_resume)

    wr = sub.add_parser("report", help="Weekly self-report")
    wr.set_defaults(func=cmd_report)
    return p


def main(argv: list[str] | None = None) -> None:
    setup_logging()
    memory.init_db()
    args = build_parser().parse_args(argv)
    try:
        args.func(args)
    except orchestrator.StoppedError as exc:
        raise SystemExit(str(exc)) from exc
