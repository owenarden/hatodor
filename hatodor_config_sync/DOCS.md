# Hatodor Config Sync

This one-shot Home Assistant App installs the configuration managed by this
repository into Home Assistant's `/config` directory.

On install, start, or update it writes these repository-managed files:

- `/config/packages/morning_dashboard.yaml`
- `/config/esphome/reterminal-e1001-morning.yaml`

It also applies one small idempotent patch to the installed HACS Super
Productivity integration, when present:

- `/config/custom_components/super_productivity/coordinator.py`

The patch changes the integration's main task fetch from
`async_get_tasks()` to `async_get_tasks(include_done=True)`. Without that,
completed project tasks disappear from Home Assistant immediately after the
integration refreshes, which conflicts with Hatodor's dashboard semantics.

The repository copies of the package and ESPHome YAML are authoritative; local
edits to those two files will be overwritten the next time this App runs. The
Super Productivity patch is deliberately a one-line in-place modification
rather than a vendored fork. A later HACS update may overwrite it; rerun Hatodor
Config Sync after updating that integration to reapply the patch.

## One-time Home Assistant setup

Ensure `/config/configuration.yaml` contains:

```yaml
homeassistant:
  packages: !include_dir_named packages
```

If `homeassistant:` already exists, add only the `packages:` line beneath the
existing key rather than creating a second `homeassistant:` block.

## Super Productivity projects

Create these three Super Productivity projects:

- `Morning Routine`
- `Reminders`
- `Evening Routine`

The package expects the Home Assistant todo entities generated from those names:

- `todo.super_productivity_sp_morning_routine`
- `todo.super_productivity_sp_reminders`
- `todo.super_productivity_sp_evening_routine`

By default the dashboard uses Morning Routine from 04:00 to 10:00, Reminders
from 10:00 to 18:00, and Evening Routine from 18:00 through the 04:00 rollover.
The three times are YAML-defined Home Assistant helpers. They are initialized to
those defaults only once and then restore the user's last values after restarts.

At rollover, completed Morning and Evening tasks are set back to
`needs_action`. Incomplete routine tasks are already in that state, so no new
task is created and there is no catch-up duplication. Completed Reminders stay
visible until rollover, when they are removed; incomplete Reminders remain until
they are eventually completed.

If Home Assistant is offline at rollover, the lifecycle automation detects the
missed dashboard day on startup and performs the rollover then.

## Applying updates

After Config Sync changes the Home Assistant package or the Super Productivity
Python integration, restart Home Assistant so both YAML and Python changes are
loaded. ESPHome source changes still require installing the firmware to the
device, normally OTA from ESPHome Builder.

For a release that changes only the ESPHome YAML, a Home Assistant restart is
not otherwise required.
