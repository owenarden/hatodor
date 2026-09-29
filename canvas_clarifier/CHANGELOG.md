# Changelog

## 0.1.2

- Log where the course profile belongs on the Home Assistant host
  (`/addon_configs/<id>_canvas_clarifier/courses.yaml`), warn while it is
  still the installed example, and list Canvas courses it has no entry for.
  The same information is in the status page under `profile`.

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
