# Hatodor Config Sync

This one-shot Home Assistant App installs the configuration files managed by
this repository into Home Assistant's `/config` directory.

On install, start, or update it writes exactly these files:

- `/config/packages/morning_dashboard.yaml`
- `/config/esphome/reterminal-e1001-morning.yaml`

The repository copies are authoritative; local edits to those two files will be
overwritten the next time this App runs.

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

After the sync App runs, reload/restart Home Assistant for package changes to
take effect. ESPHome source changes still require installing the firmware to the
device (normally OTA from the ESPHome UI).
