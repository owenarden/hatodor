"""Read-only Canvas client and the per-run snapshot it produces."""

from __future__ import annotations

import json
import re
import urllib.error
import urllib.parse
import urllib.request
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from pathlib import Path

_LINK_NEXT = re.compile(r'<([^>]+)>;\s*rel="next"')


class CanvasError(Exception):
    pass


@dataclass
class Snapshot:
    user_id: int | None = None
    courses: list[dict] = field(default_factory=list)
    assignments: dict[int, list[dict]] = field(default_factory=dict)
    planner: list[dict] = field(default_factory=list)
    # assignment id -> submission (with submission_comments)
    submissions: dict[int, dict] = field(default_factory=dict)
    announcements: dict[int, list[dict]] = field(default_factory=dict)
    errors: list[str] = field(default_factory=list)


class Canvas:
    def __init__(self, base_url: str, token: str, timeout: int = 30):
        self.base = base_url.rstrip("/") + "/api/v1"
        self.token = token
        self.timeout = timeout

    def _open(self, url: str):
        req = urllib.request.Request(url, headers={
            "Authorization": f"Bearer {self.token}", "Accept": "application/json"})
        return urllib.request.urlopen(req, timeout=self.timeout)

    def get(self, path: str, params: list[tuple[str, str]] | None = None):
        """GET with full Link-header pagination."""
        url = self.base + path
        if params:
            url += "?" + urllib.parse.urlencode(params)
        out: list = []
        while url:
            try:
                with self._open(url) as resp:
                    data = json.loads(resp.read().decode())
                    link = resp.headers.get("Link", "")
            except urllib.error.HTTPError as e:
                raise CanvasError(f"GET {path}: HTTP {e.code}") from e
            except (urllib.error.URLError, TimeoutError) as e:
                raise CanvasError(f"GET {path}: {e}") from e
            if not isinstance(data, list):
                return data
            out.extend(data)
            m = _LINK_NEXT.search(link)
            url = m.group(1) if m else None
        return out

    def snapshot(self, now: datetime, lookback_days: int, lookahead_days: int) -> Snapshot:
        snap = Snapshot()
        me = self.get("/users/self/profile")
        snap.user_id = me.get("id")
        snap.courses = [c for c in self.get("/courses", [
            ("enrollment_state", "active"), ("include[]", "term"), ("per_page", "100")])
            if isinstance(c, dict) and "id" in c]
        start = (now - timedelta(days=lookback_days)).astimezone(timezone.utc)
        end = (now + timedelta(days=lookahead_days)).astimezone(timezone.utc)
        try:
            snap.planner = self.get("/planner/items", [
                ("start_date", start.isoformat()), ("end_date", end.isoformat()),
                ("per_page", "100")])
        except CanvasError as e:
            snap.errors.append(str(e))
        for c in snap.courses:
            cid = c["id"]
            for name, path, params, target in [
                ("assignments", f"/courses/{cid}/assignments",
                 [("include[]", "submission"), ("per_page", "100")], "assignments"),
                ("announcements", f"/courses/{cid}/discussion_topics",
                 [("only_announcements", "true"), ("per_page", "100")], "announcements"),
            ]:
                try:
                    getattr(snap, target)[cid] = self.get(path, params)
                except CanvasError as e:
                    snap.errors.append(f"{c.get('name')}: {e}")
            if snap.user_id:
                try:
                    for s in self.get(f"/courses/{cid}/students/submissions", [
                            ("student_ids[]", str(snap.user_id)),
                            ("include[]", "submission_comments"), ("per_page", "100")]):
                        if isinstance(s, dict) and s.get("assignment_id"):
                            snap.submissions[s["assignment_id"]] = s
                except CanvasError as e:
                    snap.errors.append(f"{c.get('name')} comments: {e}")
        return snap


def load_survey(root: Path, announcements_dir: Path | None = None) -> Snapshot:
    """Build a Snapshot from clarifier_survey.py output (for offline testing)."""
    snap = Snapshot()
    snap.courses = json.loads((root / "courses.json").read_text())
    planner = root / "planner.json"
    snap.planner = json.loads(planner.read_text()) if planner.exists() else []
    for d in root.iterdir():
        if d.is_dir() and d.name.split("_")[0].isdigit():
            cid = int(d.name.split("_")[0])
            a = d / "assignments.json"
            if a.exists():
                snap.assignments[cid] = json.loads(a.read_text())
    stream = root / "activity_stream.json"
    if stream.exists():
        for s in json.loads(stream.read_text()):
            if s.get("type") == "Submission" and s.get("assignment_id"):
                snap.submissions[s["assignment_id"]] = s
                snap.user_id = snap.user_id or s.get("user_id")
    if announcements_dir:
        topics = announcements_dir / "announcements_via_topics.json"
        if topics.exists():
            snap.announcements = {int(k): v for k, v in json.loads(topics.read_text()).items()}
    return snap
