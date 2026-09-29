# Canvas Clarifier

Canvas Clarifier reads a student's Canvas courses every few minutes, works out
which assignments are real homework, tests and deadlines, and keeps them as
tasks in a Super Productivity project. It then compares what is marked done
locally with what Canvas says and alerts you when they disagree, such as
work marked done that Canvas lists as missing.

It only reads from Canvas. It writes only to the one Super Productivity
project you name, and never deletes tasks.

## Setup

1. **Canvas token.** Sign in to Canvas as the student, open **Account →
   Settings → Approved Integrations → New Access Token**, and paste the token
   into the App's **Canvas access token** option. Set **Canvas URL** to your
   school's Canvas address.
2. **Super Productivity project.** In Super Productivity, create a project
   named **School** (or whatever you set in **Super Productivity project**).
   The Local REST API cannot create projects.
3. **Super Productivity address.** The default `http://172.30.32.1:3877`
   reaches the Super Productivity Desktop App's REST proxy on the Home
   Assistant host. If that fails, use the host's LAN address and port 3877.
4. **Course profile.** On first start the App installs an example at
   `/addon_configs/<id>_canvas_clarifier/courses.yaml`. Replace it with your
   courses (IDs from Canvas course URLs), bell schedule and per-teacher rules.
   The App re-reads it every run.
5. **Dry run.** The App starts in dry run: it logs the Super Productivity
   changes and alerts it would make without making them. Check the App log
   and the status page, then turn **Dry run** off.

## Status

`http://<home-assistant-host>:3878/status` returns the latest run as JSON:
every item in the window with its category, resolved due date and where that
date came from, Canvas status, planner and SP completion, the SP changes
made or planned, errors, and active alerts. Keep port 3878 on your LAN or
tailnet; it shows school data.

## What becomes a task

Assignments worth 0 points are skipped. Every other Canvas assignment is
classified by the rules in `courses.yaml`, in order: `global_rules`, then the
course's `rules`, then its `default_category`, else `unclassified`. Homework, tests, prep, projects,
extra credit and unclassified items (titled `? …`) become tasks; exit
tickets, participation and other gradebook-only entries are hidden.

In courses that weight their assignment groups, a task's title ends with the
Canvas category and its share of the course grade, such as `· kind: HW (25%)`. Courses graded by
total points show no percentage.

Due dates come from Canvas unless the course or rule sets `due_from`
(`title`, `description` or `title_or_description`). Then the date for the
student's period is read from text such as `DUE: 10/6 (Period 3) or 10/7
(Period 2)` or `(ODD BLOCKS)`. Paper work due at Canvas's placeholder time
(11:59pm) is shown as due at the start of that day's class, using the bell
schedule. If the class doesn't meet that day, Canvas's deadline is kept.

## Task notes

The first line of each task's notes is the Canvas status (`Canvas: not
submitted`, `Canvas: graded`, `Canvas: missing`, …), followed by the due
date and its source, the Canvas link, and a `clarifier:key=` line that ties
the task to its Canvas item. Leave the key line in place.

## Reconciliation and alerts

"Done locally" means the Super Productivity task is checked off, or the
student marked the item complete in the Canvas planner.

| Local | Canvas | Result |
|---|---|---|
| done | missing, or graded 0 | alert |
| not done | missing (not extra credit) | alert |
| any | new teacher comment asking for a resubmission | alert |
| done | online submission, nothing submitted, past due | alert |
| done | paper, ungraded more than `grading_grace_days` after due | alert |
| done | paper, awaiting grading | nothing (normal) |
| not done | submitted / graded / excused | task checked off automatically |
| any | due date changed | alert |
| any | item deleted from Canvas | alert |

Alerts are sent once, when a condition first appears or comes back, as a
single Home Assistant notification per run. Set **Notify service** to a
notify service (for example `mobile_app_phone`) or leave it empty for a
persistent notification. New course announcements are included in the same
notification. Announcements imported from an earlier year's course copy are
skipped.

## Offline testing

The App can run once against the output of the survey script instead of
live Canvas:

```
CLARIFIER_OPTIONS=/dev/null python3 -m clarifier \
  --survey survey/<timestamp> --profile courses.yaml --db /tmp/state.sqlite \
  --now 2026-09-29T12:00:00-07:00
```

Super Productivity is untouched unless `CLARIFIER_SP_URL` is set.
