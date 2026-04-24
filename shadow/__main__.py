"""Shadow CLI.

Usage
-----
Run the capture daemon + dashboard (default — the "app" experience)::

    python -m shadow

Just the dashboard over whatever's already in the DB::

    python -m shadow dashboard

Just the capture daemon (headless)::

    python -m shadow capture

Detect patterns over existing data and print them::

    python -m shadow detect
"""

from __future__ import annotations

import argparse
import signal
import sys
import threading
import time
import webbrowser

from .capture import Capture, default_backend
from .config import config
from .dashboard import run as run_dashboard
from .patterns import PatternDetector
from .storage import Database


def _print_banner() -> None:
    print(rf"""
   _____ _               _
  / ____| |             | |
 | (___ | |__   __ _  __| | _____      __
  \___ \| '_ \ / _` |/ _` |/ _ \ \ /\ / /
  ____) | | | | (_| | (_| | (_) \ V  V /
 |_____/|_| |_|\__,_|\__,_|\___/ \_/\_/
 Watch your desktop · Learn your patterns · Forge them into agents
 Storage: {config.db_path}
""")


def cmd_all(open_browser: bool = True) -> None:
    db = Database(config.db_path)
    capture = Capture(default_backend(), db, config)
    capture.start()

    def _shutdown(*_args):
        print("\n→ stopping capture…")
        capture.stop()
        sys.exit(0)

    signal.signal(signal.SIGINT, _shutdown)
    signal.signal(signal.SIGTERM, _shutdown)

    url = f"http://{config.dashboard_host}:{config.dashboard_port}"
    if open_browser:
        threading.Timer(1.0, lambda: webbrowser.open(url)).start()

    run_dashboard(db, config)


def cmd_capture() -> None:
    db = Database(config.db_path)
    capture = Capture(default_backend(), db, config)
    capture.start()
    print(f"Capturing to {config.db_path}. Ctrl-C to stop.")
    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        capture.stop()


def cmd_dashboard() -> None:
    db = Database(config.db_path)
    run_dashboard(db, config)


def cmd_detect() -> None:
    db = Database(config.db_path)
    det = PatternDetector(db, config)
    patterns = det.detect()
    if not patterns:
        print("No patterns found. Use your computer for a while and try again.")
        return
    print(f"Found {len(patterns)} patterns:\n")
    for i, p in enumerate(patterns[:20], 1):
        print(f"  {i:>2}. ({p.occurrences}×) {p.describe()}")


def main(argv: list[str] | None = None) -> None:
    _print_banner()
    parser = argparse.ArgumentParser(prog="shadow", description="Shadow — desktop agent forge")
    sub = parser.add_subparsers(dest="cmd")
    sub.add_parser("capture", help="Run the capture daemon only")
    sub.add_parser("dashboard", help="Run the dashboard only")
    sub.add_parser("detect", help="Detect patterns over existing data")
    sub.add_parser("all", help="Run capture + dashboard (default)")
    args = parser.parse_args(argv)

    cmd = args.cmd or "all"
    if cmd == "capture":
        cmd_capture()
    elif cmd == "dashboard":
        cmd_dashboard()
    elif cmd == "detect":
        cmd_detect()
    else:
        cmd_all()


if __name__ == "__main__":
    main()
