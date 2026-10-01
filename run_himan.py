"""
HIMAN Auto Runner
=================
EK COMMAND SE POORA SYSTEM CHALO:
  python run_himan.py

Yeh kya karta hai:
1. Dashboard start karta hai (browser mein khulta hai)
2. Auto Fetcher background mein start hota hai
3. Har 30 min mein nayi jobs aati hain
4. Tum sirf BID karo!
"""

from __future__ import annotations

import sys
import subprocess
import threading
import time
import webbrowser
from pathlib import Path

ROOT = Path(__file__).resolve().parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

DASHBOARD_PORT = 8501


def start_fetcher_thread() -> None:
    """Auto fetcher background thread mein chalao."""
    def _run():
        print("[HIMAN] Auto Fetcher thread starting...")
        try:
            from auto_fetcher import main as fetcher_main
            fetcher_main()
        except Exception as exc:
            print(f"[HIMAN] Fetcher error: {exc}")

    t = threading.Thread(target=_run, daemon=True)
    t.start()
    print("[HIMAN] Auto Fetcher background mein chal raha hai ✅")


def start_dashboard() -> subprocess.Popen:
    """Streamlit dashboard start karo."""
    print(f"[HIMAN] Dashboard starting on http://localhost:{DASHBOARD_PORT}")
    proc = subprocess.Popen(
        [
            sys.executable, "-m", "streamlit", "run",
            str(ROOT / "dashboard" / "bid_dashboard.py"),
            "--server.port", str(DASHBOARD_PORT),
            "--server.headless", "false",
            "--browser.gatherUsageStats", "false",
            "--server.runOnSave", "false",
        ],
        cwd=str(ROOT),
    )
    return proc


def open_browser() -> None:
    """5 second baad browser mein kholo."""
    time.sleep(5)
    webbrowser.open(f"http://localhost:{DASHBOARD_PORT}")


def print_banner() -> None:
    print("""
╔══════════════════════════════════════════════╗
║         🏢 HIMAN Pro — AI Freelance Office  ║
║                                              ║
║  Kya ho raha hai:                            ║
║  ✅ Dashboard  → http://localhost:8501       ║
║  ✅ Auto Fetcher → background mein chalu    ║
║  ✅ Har 30 min → nayi jobs aayengi          ║
║                                              ║
║  Tumhara kaam:                               ║
║  1. Dashboard khulega browser mein          ║
║  2. "BID READY" tab dekho                   ║
║  3. Proposal copy karo                      ║
║  4. Job link pe jao → paste karo → BID!     ║
║                                              ║
║  Band karne ke liye: Ctrl+C                 ║
╚══════════════════════════════════════════════╝
""")


def main() -> None:
    print_banner()

    # 1. Auto fetcher background mein
    start_fetcher_thread()

    # 2. Browser thread
    browser_thread = threading.Thread(target=open_browser, daemon=True)
    browser_thread.start()

    # 3. Dashboard (blocking — yahi window open rakhti hai)
    try:
        dashboard_proc = start_dashboard()
        dashboard_proc.wait()
    except KeyboardInterrupt:
        print("\n[HIMAN] Stopping...")
        try:
            dashboard_proc.terminate()
        except Exception:
            pass
        print("[HIMAN] Goodbye! Paise kama liya hoga insha'Allah 💰")


if __name__ == "__main__":
    main()
