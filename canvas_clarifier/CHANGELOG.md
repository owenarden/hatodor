# Changelog

## 0.1.5

- Tag each task in Super Productivity with its course, its Canvas category,
  and how it is turned in (`Online` or `IRL`); tests and quizzes get
  `In class`. Tag names are configurable under `tags:` in `courses.yaml`, and
  a rule can override the submission kind (`submission: online`).
- Super Productivity's API cannot create tags, so the App assigns tags that
  already exist and logs the names it is waiting for. Tags added by hand are
  kept.

## 0.1.4

- Report an error when Super Productivity accepts a task but drops its
  deadline, which is what versions before v19 do. Update the Super
  Productivity Desktop App (0.7.0 installs v19.1.0); existing tasks get their
  deadlines on the next run.

## 0.1.3

- Skip assignments worth 0 points (study-guide announcements, empty
  extra-credit columns, attendance). A quiz announced by a 0-point study guide
  still gets its own task.
- In courses that weight their assignment groups, end each task title with
  the assignment's category and its share of the course grade, e.g.
  `Science: HW2 · kind: HW (25%)`.

## 0.1.2

- Log where the course profile belongs on the Home Assistant host
  (`/addon_configs/<id>_canvas_clarifier/courses.yaml`), warn while it is
  still the installed example, and list Canvas courses it has no entry for.
  The same information is in the status page under `profile`.
- Report a changed due date only when Canvas changed the assignment's due
  date, title or description; changes to `courses.yaml` no longer look like
  due-date changes.
- Send every still-active alert on the first run after dry run is turned off,
  since alerts raised during dry run were only logged.

## 0.1.1

- Show log output in Home Assistant: run Python unbuffered, since the base
  image's init can start the App without its environment settings.
- Find the Home Assistant token in s6's saved container environment when it
  is not in the process environment, so alerts can be delivered.

## 0.1.0

- First release: read Canvas assignments, planner completion, submission
  comments and course announcements with a student token.
- Classify assignments with per-course rules from `courses.yaml` and resolve
  real due dates from per-period text in titles and descriptions, placing
  paper work at the start of that day's class from the bell schedule.
- Keep homework, tests, prep, projects and extra credit as tasks in a Super
  Productivity project; check tasks off when Canvas shows them submitted or
  graded; never delete or edit archived tasks.
- Alert once per transition on local/Canvas mismatches, missing work, teacher
  resubmission comments, due-date changes and deleted items; include new
  announcements; skip announcements left over from course copies.
- Dry run by default; JSON status on port 3878.
