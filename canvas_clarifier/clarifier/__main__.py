"""Entry point: poll forever (App) or run once against a saved survey (--survey)."""

from __future__ import annotations

import argparse
import json
import os
import sys
import threading
import time
import traceback
from datetime import datetime
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

from . import notify
from .canvas import Canvas, CanvasError, load_survey
from .config import CONFIG_DIR, Options, Profile, host_config_hint
from .runner import run_once
from .sp import SP
from .store import Store

STATUS: dict = {"state": "starting"}


class Handler(BaseHTTPRequestHandler):
    def do_GET(self):  # noqa: N802
        if self.path.rstrip("/") not in ("", "/status"):
            self.send_error(404)
            return
        body = json.dumps(STATUS, indent=2, default=str).encode()
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, *args):
        pass


def one_run(opts: Options, profile: Profile, store: Store, snap=None, now=None) -> dict:
    now = now or datetime.now(profile.tz)
    if snap is None:
        snap = Canvas(opts.canvas_base_url, opts.canvas_token).snapshot(
            now, opts.lookback_days, opts.lookahead_days)
    sp = SP(opts.sp_url, dry_run=opts.dry_run) if opts.sp_url else None
    result = run_once(snap, profile, opts, store, sp, now)
    lines = result["new_alerts"] + result["notices"]
    if lines:
        result["notify"] = notify.send("Canvas Clarifier", lines, opts.notify_service,
                                       dry_run=opts.dry_run)
    return result


def main() -> int:
    ap = argparse.ArgumentParser(prog="clarifier")
    ap.add_argument("--survey", type=Path, help="run once against clarifier_survey.py output")
    ap.add_argument("--announcements", type=Path, help="announcements_probe.py output")
    ap.add_argument("--now", help="ISO timestamp to treat as now (with --survey)")
    ap.add_argument("--profile", type=Path, help="courses.yaml (default: config dir)")
    ap.add_argument("--db", type=Path, help="state database (default: config dir)")
    args = ap.parse_args()

    opts = Options.load()
    if not args.survey and not (opts.canvas_base_url and opts.canvas_token):
        print("Set the Canvas URL and access token in the App configuration.", file=sys.stderr)
        return 1
    profile = (Profile.from_yaml(args.profile.read_text()) if args.profile
               else Profile.load())
    store = Store(args.db or CONFIG_DIR / "clarifier.sqlite")

    if args.survey:
        snap = load_survey(args.survey, args.announcements)
        now = (datetime.fromisoformat(args.now).astimezone(profile.tz) if args.now
               else datetime.now(profile.tz))
        # Offline runs only touch SP when an SP address is given explicitly.
        if "CLARIFIER_SP_URL" not in os.environ:
            opts.sp_url = ""
        print(json.dumps(one_run(opts, profile, store, snap, now), indent=2, default=str))
        return 0

    server = ThreadingHTTPServer(("0.0.0.0", 3878), Handler)
    threading.Thread(target=server.serve_forever, daemon=True).start()
    print(f"Canvas Clarifier started (dry run: {opts.dry_run}); status on port 3878")
    print(f"Course profile: {host_config_hint()}/courses.yaml")
    while True:
        try:
            profile = Profile.load()          # pick up edits to courses.yaml
            result = one_run(opts, profile, store)
            STATUS.clear()
            STATUS.update(result)
            print(f"{result['last_run']}: {len(result['items'])} items, "
                  f"{len(result['sp_changes'])} SP changes, "
                  f"{len(result['new_alerts'])} new alerts, errors: {result['errors'] or 'none'}")
            prof = result["profile"]
            if prof["example"]:
                print(f"  WARNING: courses.yaml is still the example; put your profile at "
                      f"{host_config_hint()}/courses.yaml")
            elif prof["canvas_courses_without_entry"]:
                print("  Canvas courses missing from courses.yaml (default rules): "
                      + "; ".join(prof["canvas_courses_without_entry"]))
            for line in result["sp_changes"]:
                print(("  [dry run] " if opts.dry_run else "  ") + line)
            if result.get("notify"):
                print("  " + result["notify"].replace("\n", "\n  "))
        except (CanvasError, OSError, ValueError) as e:
            STATUS.update({"state": "error", "error": str(e)})
            print(f"Run failed: {e}", file=sys.stderr)
        except Exception:
            STATUS.update({"state": "error", "error": traceback.format_exc()})
            traceback.print_exc()
        time.sleep(opts.poll_minutes * 60)


if __name__ == "__main__":
    sys.exit(main())
