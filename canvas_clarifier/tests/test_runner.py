"""End-to-end runs over a synthetic Canvas snapshot and a fake Super Productivity."""

import copy
import tempfile
import unittest
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

from clarifier.canvas import Snapshot
from clarifier.config import Options, Profile
from clarifier.runner import run_once
from clarifier.store import Store

TZ = ZoneInfo("America/Los_Angeles")
NOW = datetime(2026, 9, 29, 12, 0, tzinfo=TZ)          # a Tuesday
PROFILE = Profile.from_yaml(
    (Path(__file__).resolve().parents[1] / "courses.example.yaml").read_text())


def assignment(aid, name, due_at, types, sub=None, created="2026-09-01T16:00:00Z",
               description="", points=10, group=None):
    return {"id": aid, "name": name, "due_at": due_at, "created_at": created,
            "assignment_group_id": group,
            "submission_types": types, "points_possible": points, "published": True,
            "description": description,
            "html_url": f"https://canvas.example/courses/1/assignments/{aid}",
            "submission": sub or {"workflow_state": "unsubmitted"}}


def snapshot():
    return Snapshot(
        user_id=42,
        courses=[{"id": c, "name": f"Course {c}", "apply_assignment_group_weights": c == 1002}
                 for c in (1001, 1002, 1003, 1004, 1005)],
        groups={1002: [{"id": 50, "name": "Homework", "group_weight": 25.0},
                       {"id": 51, "name": "Tests", "group_weight": 40.0}],
                1001: [{"id": 60, "name": "Everything", "group_weight": 100.0}]},
        assignments={
            1002: [
                assignment(1, "HOMEWORK - Reading - DUE: 10/6/2026 (Period 3) or 10/7/2026 (Period 2)",
                           "2026-10-08T06:59:59Z", ["on_paper"], group=50),
                assignment(10, "Name card", "2026-10-02T06:59:59Z", ["on_paper"], points=0),
                assignment(2, "HOMEWORK - Old reading - DUE: 9/24/2026", "2026-09-25T06:59:59Z",
                           ["on_paper"], {"workflow_state": "graded", "score": 9}),
                assignment(3, "Extra Credit Poster", "2026-09-19T06:59:59Z", ["online_upload"],
                           {"workflow_state": "graded", "score": 0, "missing": True}, points=5),
            ],
            1003: [
                assignment(9, "Science fair project", "2026-12-10T06:59:59Z", ["online_upload"]),
                assignment(4, "Lab notes", "2026-09-26T06:59:59Z", ["on_paper"]),
                assignment(5, "Online summary", "2026-09-26T06:59:59Z", ["online_text_entry"]),
            ],
            1001: [
                assignment(6, "Class Participation Week of 9/21", "2026-09-26T06:59:59Z", ["none"],
                           created="2026-09-28T16:00:00Z"),
                assignment(7, "Study Guide for Roots Quiz 10/6 and 10/7", "2026-10-08T06:59:59Z",
                           ["none"], description="Quiz Tues 10/6 (Block 3) and Weds 10/7 "
                                                 "(Blocks 2, 4 and 6).", points=0, group=60),
            ],
            1004: [assignment(8, "Club dues", "2026-10-01T06:59:59Z", ["none"])],
        },
        planner=[{"plannable_id": 3, "planner_override": {"marked_complete": True}},
                 {"plannable_id": 4, "planner_override": {"marked_complete": True}},
                 {"plannable_id": 5, "planner_override": {"marked_complete": True}}],
        announcements={1001: [
            {"id": 900, "title": "Old import", "posted_at": None,
             "created_at": "2026-08-03T21:30:00Z"},
            {"id": 901, "title": "Bring a pen", "posted_at": "2026-09-20T16:00:00Z",
             "created_at": "2026-09-20T16:00:00Z"},
        ]},
    )


class FakeSP:
    def __init__(self, tasks):
        self._tasks = tasks
        self.created, self.updated, self.log = [], [], []

    def project_id(self, title):
        return "p1"

    def tasks(self, project_id):
        return copy.deepcopy(self._tasks)

    def create(self, fields):
        self.created.append(fields)
        self.log.append(f"create: {fields['title']}")
        return f"new-{len(self.created)}"

    def update(self, task_id, fields, label):
        self.updated.append((task_id, fields))
        self.log.append(f"update {label}")


def existing_tasks():
    return [
        {"id": "t2", "isDone": False, "notes": "clarifier:key=canvas:assignment:2"},
        {"id": "t999", "isDone": False, "notes": "clarifier:key=canvas:assignment:999"},
        {"id": "t5", "isDone": True, "notes": "clarifier:key=canvas:assignment:5",
         "_archived": True, "title": "stale title"},
    ]


class RunnerTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.store = Store(Path(self.tmp.name) / "state.sqlite")
        # A vanished item that once had a task.
        self.store.upsert_item("canvas:assignment:999", now="2026-09-01", due=None,
                               title="Deleted worksheet", category="homework", sp_task_id="t999")
        self.opts = Options(dry_run=False, lookback_days=21, lookahead_days=35)

    def tearDown(self):
        self.tmp.cleanup()

    def run_once(self, snap=None, sp=None, now=NOW):
        sp = sp or FakeSP(existing_tasks())
        return run_once(snap or snapshot(), PROFILE, self.opts, self.store, sp, now), sp

    def test_first_run(self):
        result, sp = self.run_once()
        titles = {c["title"]: c for c in sp.created}
        by_key = {r["key"]: r for r in result["items"]}

        # Real date from the title, at the start of period 3 on Tuesday.
        hw = by_key["canvas:assignment:1"]
        self.assertEqual(hw["due"], "2026-10-06T11:20-07:00")
        # Weighted course: the category's share of the grade is in the title.
        self.assertIn("History: HOMEWORK - Reading (25%)", titles)
        created = titles["History: HOMEWORK - Reading (25%)"]
        self.assertEqual(created["projectId"], "p1")
        self.assertTrue(created["notes"].startswith("Canvas: not submitted\n"))
        self.assertIn("clarifier:key=canvas:assignment:1", created["notes"])

        # 0-point study guide is skipped, but its quiz is created on the even-block day.
        self.assertNotIn("canvas:assignment:7", by_key)
        self.assertEqual(by_key["canvas:assignment:7#test"]["due"], "2026-10-07T08:30-07:00")
        self.assertEqual(by_key["canvas:assignment:7#test"]["category"], "test")
        # 0-point assignments are skipped; unweighted courses show no percentage.
        self.assertNotIn("canvas:assignment:10", by_key)
        self.assertIsNone(by_key["canvas:assignment:7#test"]["weight"])

        # Projects appear long before the look-ahead window.
        self.assertIn("Science: Science fair project", titles)

        # Hidden and ignored items never reach SP.
        self.assertNotIn("canvas:assignment:6", by_key)
        self.assertNotIn("canvas:assignment:8", by_key)

        # Graded in Canvas -> auto-completed in SP.
        self.assertIn(("t2", True), [(tid, f.get("isDone")) for tid, f in sp.updated])
        # Archived tasks are never edited.
        self.assertNotIn("t5", [tid for tid, _ in sp.updated])
        # Past paper work marked done in the planner is not re-created.
        self.assertNotIn("Science: Lab notes", titles)

        alerts = "\n".join(result["new_alerts"])
        self.assertIn("Marked done, but Canvas says missing: History: Extra Credit Poster", alerts)
        self.assertIn("nothing is submitted in Canvas: Science: Online summary", alerts)
        self.assertIn("No longer in Canvas", alerts)
        # Paper work awaiting grading is not an alert.
        self.assertNotIn("Lab notes", alerts)
        # Canvas courses the profile doesn't know are reported.
        self.assertEqual(result["profile"]["canvas_courses_without_entry"], ["1005 Course 1005"])

        # First run records announcements silently; imports are dropped.
        self.assertEqual(result["notices"], [])

    def test_alerts_fire_on_transitions_only(self):
        self.run_once()
        again, _ = self.run_once()
        self.assertEqual(again["new_alerts"], [])
        self.assertTrue(any("Extra Credit Poster" in a["message"] for a in again["active_alerts"]))

    def test_due_date_change_and_new_announcement(self):
        self.run_once()
        snap = snapshot()
        snap.assignments[1002][0]["name"] = \
            "HOMEWORK - Reading - DUE: 10/8/2026 (Period 3) or 10/9/2026 (Period 2)"
        snap.announcements[1001].append(
            {"id": 902, "title": "Quiz moved", "posted_at": "2026-09-29T17:00:00Z",
             "created_at": "2026-09-29T17:00:00Z"})
        result, sp = self.run_once(snap)
        self.assertIn("Due date changed: History: HOMEWORK - Reading is now due Thu 10/8 11:20 AM",
                      result["new_alerts"])
        self.assertEqual(result["notices"], ["New announcement — English: Quiz moved"])

    def test_profile_change_is_not_a_due_date_change(self):
        self.run_once()
        other = Profile.from_yaml(
            (Path(__file__).resolve().parents[1] / "courses.example.yaml").read_text()
            .replace("    period: 3\n", "    period: 2\n"))
        result = run_once(snapshot(), other, self.opts, self.store,
                          FakeSP(existing_tasks()), NOW)
        by_key = {r["key"]: r for r in result["items"]}
        self.assertEqual(by_key["canvas:assignment:1"]["due"], "2026-10-07T08:30-07:00")
        self.assertFalse([a for a in result["new_alerts"] if a.startswith("Due date changed")])

    def test_alerts_from_dry_run_are_sent_on_first_live_run(self):
        dry = Options(dry_run=True, lookback_days=21, lookahead_days=35)
        first = run_once(snapshot(), PROFILE, dry, self.store, FakeSP(existing_tasks()), NOW)
        self.assertTrue(any("Extra Credit Poster" in a for a in first["new_alerts"]))
        again = run_once(snapshot(), PROFILE, dry, self.store, FakeSP(existing_tasks()), NOW)
        self.assertEqual(again["new_alerts"], [])
        live, _ = self.run_once()
        self.assertTrue(any("Extra Credit Poster" in a for a in live["new_alerts"]))
        later, _ = self.run_once()
        self.assertEqual(later["new_alerts"], [])

    def test_dry_run_writes_nothing(self):
        from clarifier.sp import SP
        sp = SP("http://127.0.0.1:9", dry_run=True)
        sp.project_id = lambda title: "p1"
        sp.tasks = lambda pid: []
        result = run_once(snapshot(), PROFILE, Options(dry_run=True), self.store, sp, NOW)
        self.assertTrue(any(c.startswith("create: History: HOMEWORK") for c in result["sp_changes"]))


if __name__ == "__main__":
    unittest.main()
