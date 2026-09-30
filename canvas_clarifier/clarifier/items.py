"""Turn a Canvas snapshot into classified items with real due dates."""

from __future__ import annotations

import hashlib
import re
import unicodedata
from dataclasses import dataclass, field
from datetime import datetime, time, timedelta

from .canvas import Snapshot
from .config import VISIBLE, Course, Profile, Rule
from .dates import pick_date, strip_html

ONLINE_TYPES = {"online_upload", "online_text_entry", "online_url", "media_recording",
                "external_tool", "online_quiz", "discussion_topic", "student_annotation"}


@dataclass
class Item:
    key: str
    course: Course
    assignment_id: int | None
    title: str                 # Canvas title
    display: str               # cleaned, for SP / the dashboard
    category: str
    url: str = ""
    due: datetime | None = None
    due_note: str = ""
    canvas_due: datetime | None = None
    points: float | None = None
    online: bool = False
    status: str = ""           # human-readable Canvas status
    canvas_done: bool = False
    missing: bool = False
    submitted_at: str | None = None
    teacher_comment_after_submit: str | None = None
    planner_done: bool = False
    submittable: bool = True
    # Fingerprint of the Canvas fields a due date is derived from, so a changed
    # due date is only reported when Canvas changed, not when the profile did.
    source_sig: str = ""
    # Share of the course grade carried by this assignment's category, when the
    # course weights its assignment groups.
    weight: float | None = None
    weight_group: str | None = None
    submission: str | None = None      # "online" or "in_person"
    extra: dict = field(default_factory=dict)

    @property
    def visible(self) -> bool:
        return self.category in VISIBLE


def _dt(s: str | None, tz) -> datetime | None:
    if not s:
        return None
    return datetime.fromisoformat(s.replace("Z", "+00:00")).astimezone(tz)


_EMOJI = re.compile("[\U0001F000-\U0001FAFF☀-➿️]")


def clean_title(title: str) -> str:
    t = _EMOJI.sub("", title)
    t = "".join(ch for ch in t if unicodedata.category(ch) != "So")
    # Drop "- DUE: 10/6/2026 (Period 3) or …" and "- 10/20/2026 (ODD BLOCKS) or …" tails.
    t2 = re.sub(r"\s*[-–(]*\s*\bDUE\b.*$", "", t, flags=re.I)
    t2 = re.sub(r"\s*-\s*\d{1,2}/\d{1,2}(/\d{2,4})?\s*\(.*$", "", t2)
    t = t2 if len(t2.strip()) >= 4 else t
    return re.sub(r"\s+", " ", t).strip(" -–:")[:80]


def group_label(name: str | None) -> str:
    """'Quiz/ Preparedness ' -> 'Quiz/Preparedness', trimmed for small displays."""
    label = re.sub(r"\s*/\s*", "/", re.sub(r"\s+", " ", name or "")).strip()
    return label[:18].rstrip()


def _condition(when: str, a: dict, course: Course, profile: Profile) -> bool:
    tz = profile.tz
    due, created = _dt(a.get("due_at"), tz), _dt(a.get("created_at"), tz)
    if when == "created_after_due":
        return bool(due and created and (due - created) < timedelta(hours=6))
    if when == "due_before_term":
        start = profile.schedule.term_start
        return bool(due and start and due.date() < start - timedelta(days=30))
    if when == "external_tool_unlocks_during_school_day":
        unlock = _dt(a.get("unlock_at"), tz)
        return bool("external_tool" in (a.get("submission_types") or [])
                    and unlock and profile.schedule.day_type(unlock.date())
                    and time(7, 30) <= unlock.time() <= time(15, 45))
    return False


def _rule_hits(rule: Rule, a: dict, course: Course, profile: Profile) -> bool:
    if rule.match and not rule.match.search(a.get("name") or ""):
        return False
    if rule.when and not _condition(rule.when, a, course, profile):
        return False
    return bool(rule.match or rule.when)


def classify(a: dict, course: Course, profile: Profile) -> tuple[str, Rule | None]:
    if course.ignore:
        return "ignore", None
    if not (a.get("points_possible") or 0) > 0:
        return "no_points", None
    for rule in profile.global_rules:
        if _rule_hits(rule, a, course, profile):
            return rule.category or "unclassified", rule
    for rule in course.rules:
        if _rule_hits(rule, a, course, profile):
            return rule.category or "unclassified", rule
    return course.default_category or "unclassified", None


def resolve_due(a: dict, course: Course, category: str, rule: Rule | None,
                profile: Profile, today) -> tuple[datetime | None, str]:
    tz, sched = profile.tz, profile.schedule
    canvas_due = _dt(a.get("due_at"), tz)
    source = (rule.due_from if rule and rule.due_from else None) or course.due_from
    found, where = None, ""
    texts = {"title": a.get("name") or "", "description": a.get("description") or ""}
    order = {"title": ["title"], "description": ["description"],
             "title_or_description": ["title", "description"]}.get(source or "", [])
    if not canvas_due and not order:
        order = ["description"]          # undated: look for "due …" in the text
    for part in order:
        found = pick_date(texts[part], course.period, sched.term_start, sched.term_end, today)
        if found:
            where = part
            break
    if not found and not canvas_due:
        return None, "no due date"

    day = found.day if found else canvas_due.date()
    placeholder = time.fromisoformat(profile.placeholder_due_time)
    types = set(a.get("submission_types") or [])
    online = bool(types & ONLINE_TYPES)
    note = f"from {where}" + (f" (period {course.period})" if course.period else "") if found \
        else "Canvas"

    if found and found.at:
        return datetime.combine(day, found.at, tz), note
    if canvas_due and canvas_due.date() == day and canvas_due.time().replace(
            second=0, microsecond=0) != placeholder:
        return canvas_due, note          # a real time set by the teacher
    if online and category not in ("test",):
        return datetime.combine(day, placeholder, tz), note
    meeting = sched.meeting(course.period, day)
    if meeting:
        return meeting[0], note + ", start of class"
    # No class that day: keep the (earlier) Canvas deadline rather than
    # pushing it to the next meeting.
    return datetime.combine(day, placeholder, tz), note + ", no class that day"


def canvas_status(a: dict, sub: dict) -> dict:
    ws = sub.get("workflow_state") or "unsubmitted"
    points = a.get("points_possible") or 0
    score = sub.get("score")
    missing = bool(sub.get("missing")) or sub.get("late_policy_status") == "missing"
    graded_zero = ws == "graded" and score is not None and score == 0 and points > 0
    excused = bool(sub.get("excused"))
    if excused:
        status = "excused"
    elif missing:
        status = "missing"
    elif graded_zero:
        status = "graded 0"
    elif ws == "graded":
        status = "graded"
    elif ws in ("submitted", "pending_review"):
        status = "submitted"
    else:
        status = "not submitted"
    if sub.get("late") and status not in ("missing", "excused"):
        status += ", late"
    done = excused or (ws in ("submitted", "pending_review", "graded")
                       and not missing and not graded_zero)
    return {"status": status, "done": done, "missing": missing or graded_zero,
            "submitted_at": sub.get("submitted_at")}


def _comment_after_submit(sub: dict, user_id) -> str | None:
    comments = [c for c in sub.get("submission_comments") or []
                if c.get("author_id") != user_id]
    if not comments:
        return None
    last = max(comments, key=lambda c: c.get("created_at") or "")
    submitted = sub.get("submitted_at") or ""
    if submitted and (last.get("created_at") or "") <= submitted:
        return None
    text = strip_html(last.get("comment"))
    if not re.search(r"resubmit|re-submit|redo|unable to (view|open)|can.?t (view|open)|"
                     r"missing|please (turn|submit)|incomplete", text, re.I):
        return None
    return text[:200]


def build_items(snap: Snapshot, profile: Profile, now: datetime) -> list[Item]:
    tz = profile.tz
    today = now.astimezone(tz).date()
    planner_done = {p.get("plannable_id") for p in snap.planner
                    if (p.get("planner_override") or {}).get("marked_complete")}
    weighted = {c.get("id") for c in snap.courses if c.get("apply_assignment_group_weights")}
    items: list[Item] = []
    for cid, assignments in snap.assignments.items():
        # group id -> (share of the grade if the course weights groups, label)
        group_weight = {g.get("id"): (g.get("group_weight") if cid in weighted
                                      and (g.get("group_weight") or 0) > 0 else None,
                                      group_label(g.get("name")) or None)
                        for g in snap.groups.get(cid) or []}
        course = profile.courses.get(cid)
        if course is None:
            name = next((c.get("name") for c in snap.courses if c.get("id") == cid), str(cid))
            course = Course(id=cid, name=name, short=name[:18])
        for a in assignments:
            if not a.get("published", True):
                continue
            category, rule = classify(a, course, profile)
            due, note = resolve_due(a, course, category, rule, profile, today)
            sub = dict(a.get("submission") or {})
            extra_sub = snap.submissions.get(a["id"]) or {}
            if extra_sub.get("submission_comments"):
                sub["submission_comments"] = extra_sub["submission_comments"]
            st = canvas_status(a, sub)
            sig = hashlib.sha1("\x1f".join(
                str(a.get(k) or "") for k in ("due_at", "name", "description")).encode()
            ).hexdigest()
            types = set(a.get("submission_types") or [])
            item = Item(
                key=f"canvas:assignment:{a['id']}", course=course, assignment_id=a["id"],
                title=a.get("name") or "", display=clean_title(a.get("name") or ""),
                category=category, url=a.get("html_url") or "", due=due, due_note=note,
                canvas_due=_dt(a.get("due_at"), tz), points=a.get("points_possible"),
                online=bool(types & ONLINE_TYPES), status=st["status"],
                canvas_done=st["done"], missing=st["missing"],
                submitted_at=st["submitted_at"],
                teacher_comment_after_submit=_comment_after_submit(sub, snap.user_id),
                planner_done=a["id"] in planner_done,
                submittable=category not in ("test",), source_sig=sig,
                weight=(group_weight.get(a.get("assignment_group_id")) or (None, None))[0],
                weight_group=(group_weight.get(a.get("assignment_group_id")) or (None, None))[1],
                submission=(rule.submission if rule and rule.submission
                            else "online" if types & ONLINE_TYPES else "in_person"))
            items.append(item)
            if category == "no_points":
                rule = next((r for r in course.rules if r.also_create
                             and _rule_hits(r, a, course, profile)), None)
            if rule and rule.also_create == "test":
                found = pick_date(a.get("description") or "", course.period,
                                  profile.schedule.term_start, profile.schedule.term_end, today) \
                    or pick_date(a.get("name") or "", course.period,
                                 profile.schedule.term_start, profile.schedule.term_end, today)
                if found:
                    meet = profile.schedule.meeting_on_or_after(course.period, found.day)
                    when = meet[0] if meet else datetime.combine(found.day, time(8, 0), tz)
                    name = re.sub(r"^study guide for\s*", "", item.display, flags=re.I)
                    name = re.sub(r"\s*(\bquiz\b)?\s*(mon|tue|wed|thu|fri)?[a-z.]*\s*"
                                  r"\d{1,2}/\d{1,2}.*$", r" \1", name, flags=re.I).strip()
                    items.append(Item(
                        key=f"canvas:assignment:{a['id']}#test", course=course,
                        assignment_id=a["id"], title=a.get("name") or "",
                        display=f"Quiz: {name}" if "quiz" not in name.lower() else name,
                        category="test", url=item.url, due=when,
                        due_note=f"from description (period {course.period}), start of class",
                        status="in class", submittable=False, source_sig=sig))
    return items
