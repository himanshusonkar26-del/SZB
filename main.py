"""
HIMAN Pro — Main Entry Point
=============================
Usage:
  python main.py           → Dashboard (browser mein khulega)
  python main.py cli       → CLI mode
  python main.py search    → Search jobs only
"""

from __future__ import annotations

import sys
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parent


def run_dashboard() -> None:
    """Streamlit dashboard start karo."""
    print("🚀 HIMAN Pro Dashboard start ho raha hai...")
    print("📌 Browser mein khulega: http://localhost:8501")
    print("🛑 Band karne ke liye: Ctrl+C")
    subprocess.run(
        [sys.executable, "-m", "streamlit", "run",
         str(ROOT / "dashboard" / "app.py"),
         "--server.port", "8501",
         "--server.headless", "false",
         "--browser.gatherUsageStats", "false"],
        cwd=str(ROOT),
    )


def run_cli() -> None:
    """CLI mode."""
    sys.path.insert(0, str(ROOT))
    from himan.cli import main
    main(sys.argv[2:])


def run_search() -> None:
    """Quick search aur print."""
    sys.path.insert(0, str(ROOT))
    from agents.search_agent import run_search as do_search
    print("🔍 Searching Freelancer.com...")
    results = do_search(limit=30, shortlist_only=True)
    print(f"\n✅ {len(results)} shortlisted jobs:\n")
    for i, r in enumerate(results[:10], 1):
        print(f"{i}. [{r['score']}] {r['title']}")
        print(f"   Budget: {r.get('budget') or 'N/A'} | {r.get('reason', '')}")
        if r.get("url"):
            print(f"   {r['url']}")
        print()


if __name__ == "__main__":
    mode = sys.argv[1] if len(sys.argv) > 1 else "dashboard"
    if mode == "cli":
        run_cli()
    elif mode == "search":
        run_search()
    else:
        run_dashboard()
