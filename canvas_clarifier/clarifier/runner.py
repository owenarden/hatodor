"""One polling run: Canvas → items → SP sync → reconciliation → alerts."""

from __future__ import annotations

from datetime import datetime, timedelta

from .canvas import Snapshot
from .config import Options, Profile
from .items import Item, build_items
from .sp import SP, SPError, task_key
from .store import Store

LABELS = {"homework": "Homework", "test": "Test/quiz", "prep": "Prepare",
          "project": "Project", "extra_credit": "Extra credit (optional)",
          "unclassified": "Unsorted"}


def fmt(dt: datetime | None) -> str:
    return dt.strftime("%a %-m/%-d %-I:%M %p") if dt else "no due date"


def sp_title(item: Item) -> str:
    prefix = "? " if item.category == "unclassified" else ""
    return f"{prefix}{item.course.short}: {item.display}"


def sp_notes(item: Item) -> str:
    status = item.status if item.submittable else "in class"
    lines = [f"Canvas: {status}",
             f"{LABELS.get(item.category, item.category)} · due {fmt(item.due)} ({item.due_note})"]
    if item.url:
        lines.append(item.url)
    lines.append(f"clarifier:key={item.key}")
    return "\n".join(lines)


def sp_deadline(item: Item) -> dict:
    if not item.due:
        return {}
    return {"deadlineWithTime": int(item.due.timestamp() * 1000)}


def in_window(item: Item, now: datetime, opts: Options) -> bool:
    if item.due is None:
        return item.visible and not item.canvas_done and item.submittable
    if item.category == "project" and item.due >= now:
        return True          # long-horizon work should appear well before the window
    return now - timedelta(days=opts.lookback_days) <= item.due <= now + timedelta(
        days=opts.lookahead_days)


def run_once(snap: Snapshot, profile: Profile, opts: Options, store: Store, sp: SP | None,
             now: datetime) -> dict:
    iso = now.isoformat(timespec="seconds")
    first_run = store.get_meta("initialized") is None
    items = build_items(snap, profile, now)
    all_keys = {i.key for i in items}
    window = [i for i in items if i.visible and in_window(i, now, opts)]
    errors = list(snap.errors)

    # --- Super Productivity -----------------------------------------------------
    tasks_by_key: dict[str, dict] = {}
    project_id = None
    if sp is not None:
        try:
            project_id = sp.project_id(opts.sp_project)
            if not project_id:
                errors.append(f'Super Productivity project "{opts.sp_project}" not found; '
                              "create it in Super Productivity")
            else:
                for t in sp.tasks(project_id):
                    k = task_key(t)
                    if k:
                        tasks_by_key[k] = t
        except SPError as e:
            errors.append(str(e))
            project_id = None

    current: dict[tuple[str, str], str] = {}
    rows = []
    for item in sorted(window, key=lambda i: (i.due is None, i.due or now)):
        task = tasks_by_key.get(item.key)
        stored = store.item(item.key)
        past = item.due is not None and item.due < now
        local_done = bool((task and task.get("isDone")) or item.planner_done)
        action = ""

        if project_id:
            fields = {"title": sp_title(item), "notes": sp_notes(item), **sp_deadline(item)}
            if task is None:
                wanted = (not item.canvas_done and not (past and not item.submittable)
                          and not (past and item.planner_done))
                if wanted:
                    new_id = sp.create(dict(fields, projectId=project_id,
                                            isDone=item.planner_done))
                    store.upsert_item(item.key, now=iso, due=_iso(item.due),
                                      title=item.display, category=item.category,
                                      sp_task_id=new_id)
                    action = "create"
            elif not task.get("_archived"):
                changes = {k: v for k, v in fields.items() if task.get(k) != v}
                if "deadlineWithTime" in changes and task.get("deadlineDay"):
                    changes["deadlineDay"] = None
                if item.canvas_done and not task.get("isDone"):
                    changes["isDone"] = True
                    action = "auto-complete"
                if changes:
                    sp.update(task["id"], changes, sp_title(item))
                    action = action or "update"

        # --- reconciliation (Canvas assignments that are turned in) -------------
        name = f"{item.course.short}: {item.display}"
        if item.submittable:
            if item.missing and local_done:
                current[(item.key, "done_but_missing")] = \
                    f"Marked done, but Canvas says {item.status}: {name}"
            elif item.missing and item.category != "extra_credit":
                current[(item.key, "missing")] = f"Missing in Canvas: {name}"
            if item.teacher_comment_after_submit:
                current[(item.key, "teacher_comment")] = \
                    f"Teacher comment on {name}: {item.teacher_comment_after_submit}"
            if local_done and past and item.status.startswith("not submitted"):
                if item.online:
                    current[(item.key, "done_not_submitted")] = \
                        f"Marked done, but nothing is submitted in Canvas: {name}"
                elif item.due < now - timedelta(days=profile.grace_days):
                    current[(item.key, "still_ungraded")] = \
                        f"Still ungraded {profile.grace_days}+ days after it was due: {name}"
        if stored is not None and stored["due"] and item.due and not past:
            if abs((datetime.fromisoformat(stored["due"]) - item.due).total_seconds()) > 60:
                current[(item.key, f"due_changed:{_iso(item.due)}")] = \
                    f"Due date changed: {name} is now due {fmt(item.due)}"

        store.upsert_item(item.key, now=iso, due=_iso(item.due), title=item.display,
                          category=item.category,
                          sp_task_id=task.get("id") if task else None)
        rows.append({"key": item.key, "course": item.course.short, "title": item.display,
                     "category": item.category, "due": _iso(item.due), "due_note": item.due_note,
                     "canvas": item.status, "planner_done": item.planner_done,
                     "sp_done": bool(task and task.get("isDone")), "sp_action": action,
                     "url": item.url})

    # Items that had an SP task but vanished from Canvas.
    for row in store.items_with_tasks():
        if row["key"] not in all_keys and "#" not in row["key"]:
            current[(row["key"], "gone")] = \
                f"No longer in Canvas (deleted or unpublished): {row['title']}"

    # Course announcements: notify about new real ones (skip imported leftovers).
    notices = []
    term_start = profile.schedule.term_start
    for cid, topics in snap.announcements.items():
        course = profile.courses.get(cid)
        if course and course.ignore:
            continue
        for t in topics or []:
            posted = t.get("posted_at")
            if not posted:
                continue
            if term_start and posted[:10] < term_start.isoformat():
                continue
            if store.new_announcement(t["id"], iso) and not first_run:
                label = course.short if course else str(cid)
                notices.append(f"New announcement — {label}: {t.get('title')}")

    fresh = store.sync_alerts(current, iso)
    store.set_meta("initialized", iso)
    store.set_meta("last_run", iso)
    store.commit()
    return {
        "last_run": iso, "dry_run": opts.dry_run, "first_run": first_run,
        "errors": errors, "sp_project_found": bool(project_id),
        "sp_changes": sp.log if sp else [],
        "new_alerts": [m for _, _, m in fresh], "notices": notices,
        "active_alerts": store.active_alerts(), "items": rows,
    }


def _iso(dt: datetime | None) -> str | None:
    return dt.isoformat(timespec="minutes") if dt else None
