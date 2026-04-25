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

Schedule commands::

    python -m shadow schedule list
    python -m shadow schedule add --pattern-id 1 --cron "0 9 * * 1-5"
    python -m shadow schedule add --pattern-id 2 --trigger "app_focus:Slack"
    python -m shadow schedule history
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
from .scheduler import Scheduler
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
    scheduler = Scheduler(db, config)

    capture.start()
    scheduler.start()

    def _shutdown(*_args):
        print("\n→ stopping scheduler…")
        scheduler.stop()
        print("→ stopping capture…")
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


def cmd_schedule_list() -> None:
    db = Database(config.db_path)
    scheduler = Scheduler(db, config)
    rules = scheduler.list_rules()
    if not rules:
        print("No schedule rules configured.")
        return
    print(f"Found {len(rules)} schedule rules:\n")
    for rule in rules:
        trigger = rule.cron_expr or rule.event_trigger
        status = "enabled" if rule.enabled else "disabled"
        print(f"  [{rule.id}] Pattern {rule.pattern_id}: {trigger} ({status})")


def cmd_schedule_add(pattern_id: int, cron: str | None = None, trigger: str | None = None) -> None:
    if not cron and not trigger:
        print("Error: must provide either --cron or --trigger")
        sys.exit(1)

    db = Database(config.db_path)
    scheduler = Scheduler(db, config)

    try:
        rule = scheduler.add_rule(
            pattern_id=pattern_id,
            cron_expr=cron,
            event_trigger=trigger,
        )
        print(f"Added rule {rule.id}: Pattern {pattern_id}")
        if cron:
            print(f"  Cron: {cron}")
        if trigger:
            print(f"  Event trigger: {trigger}")
    except Exception as e:
        print(f"Error adding rule: {e}")
        sys.exit(1)


def cmd_schedule_history(limit: int = 50) -> None:
    db = Database(config.db_path)
    scheduler = Scheduler(db, config)
    runs = scheduler.run_history(limit=limit)
    if not runs:
        print("No scheduled runs yet.")
        return
    print(f"Recent scheduled runs (showing {len(runs)} of most recent {limit}):\n")
    for run in runs:
        duration = f"{run.ended_at - run.started_at:.2f}s" if run.ended_at else "still running"
        print(f"  [Rule {run.rule_id}] {run.status} ({duration})")


def main(argv: list[str] | None = None) -> None:
    _print_banner()
    parser = argparse.ArgumentParser(prog="shadow", description="Shadow — desktop agent forge")
    sub = parser.add_subparsers(dest="cmd")

    sub.add_parser("capture", help="Run the capture daemon only")
    sub.add_parser("dashboard", help="Run the dashboard only")
    sub.add_parser("detect", help="Detect patterns over existing data")
    sub.add_parser("all", help="Run capture + dashboard (default)")

    schedule_parser = sub.add_parser("schedule", help="Manage schedule rules")
    schedule_sub = schedule_parser.add_subparsers(dest="schedule_cmd")

    schedule_sub.add_parser("list", help="List all schedule rules")

    schedule_add = schedule_sub.add_parser("add", help="Add a new schedule rule")
    schedule_add.add_argument("--pattern-id", type=int, required=True, help="Pattern ID to schedule")
    schedule_add.add_argument("--cron", help='Cron expression (e.g., "0 9 * * 1-5")')
    schedule_add.add_argument("--trigger", help='Event trigger (e.g., "app_focus:Slack")')

    schedule_sub.add_parser("history", help="Show recent scheduled runs")

    args = parser.parse_args(argv)

    cmd = args.cmd or "all"

    if cmd == "capture":
        cmd_capture()
    elif cmd == "dashboard":
        cmd_dashboard()
    elif cmd == "detect":
        cmd_detect()
    elif cmd == "schedule":
        if args.schedule_cmd == "list":
            cmd_schedule_list()
        elif args.schedule_cmd == "add":
            cmd_schedule_add(args.pattern_id, args.cron, args.trigger)
        elif args.schedule_cmd == "history":
            cmd_schedule_history()
        else:
            cmd_schedule_list()
    else:
        cmd_all()


if __name__ == "__main__":
    main()
