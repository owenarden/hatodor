# Hatodor Config Sync

This one-shot Home Assistant App installs the configuration managed by this
repository into Home Assistant's `/config` directory.

On install, start, or update it writes these repository-managed files:

- `/config/packages/morning_dashboard.yaml`
- `/config/esphome/reterminal-e1001-morning.yaml`
- `/config/hatodor/render_cat_motd.py`

On its first run only, it also creates the user-editable file
`/config/hatodor/cat_sayings.json`. Later Config Sync runs preserve that file.

It also applies small idempotent patches to the installed HACS Super
Productivity integration, when present:

- `/config/custom_components/super_productivity/coordinator.py`
- `/config/custom_components/super_productivity/todo.py`

The coordinator patch changes the integration's main task fetch from
`async_get_tasks()` to `async_get_tasks(include_done=True)`. Without that,
completed project tasks disappear from Home Assistant immediately after the
integration refreshes, which conflicts with Hatodor's dashboard semantics.

The Todo platform patch maps Home Assistant's generic TodoItem `due` value to
Super Productivity's actual `deadlineWithTime` / `deadlineDay` fields. Super
Productivity separately stores planned/scheduled time in `dueWithTime` /
`dueDay`; Hatodor deliberately leaves those scheduling fields untouched.

## Message of the Day

Config Sync creates these Home Assistant helpers:

- `input_boolean.dashboard_motd_enabled`
- `input_select.dashboard_motd_type`
- `input_text.dashboard_motd_text`
- `input_text.dashboard_motd_image_url`
- `input_text.dashboard_motd_id`

The easiest way to publish a message is to run
`script.dashboard_show_motd` from Home Assistant. Choose **Text** or **Image**,
enter the message (or optional image caption), and provide an image path when
needed. The script enables the overlay and creates a fresh revision, so even an
identical message is shown again after it was dismissed. Run
`script.dashboard_hide_motd` to remove it remotely.

You can also edit the helpers directly. Changing the revision, type, text, or
image URL re-shows a dismissed MOTD. Turning the enabled helper off returns the
display to its current checklist. The E1001 continues its normal 30-second data
sync while the overlay is visible, and pressing the green button dismisses only
the current revision. That dismissal survives an E1001 reboot; changed content,
a new revision, or disabling and re-enabling the MOTD makes it visible again.

### Local images

Use a PNG file. Put a locally managed image under Home Assistant's
`/config/www` directory; for example:

```text
/config/www/hatodor/motd.png
```

Then enter this helper/script value:

```text
/local/hatodor/motd.png
```

The E1001 resolves `/local` paths through
`http://homeassistant.local:8123`. If that name is not reachable from the
device, use Home Assistant's full LAN URL in the image helper instead, such as
`http://192.168.1.10:8123/local/hatodor/motd.png`.

The device fits the PNG inside the 800x480 screen and converts it to the
panel's black-and-white pixel format. For the best photographic result, crop
and dither the source to exactly 800x480 before placing it in `/config/www`.
For example, with ImageMagick:

```sh
magick input.jpg -resize '800x480^' -gravity center -extent 800x480 \
  -colorspace Gray -ordered-dither o8x8,2 motd.png
```

The image must be reachable without an interactive login from the E1001's
network. A `/local` Home Assistant file normally satisfies that requirement.

### Cat of the day

Run `script.dashboard_show_cat_motd` (friendly name **Dashboard - show cat of
the day**) to create a cat-photo MOTD. Select a tone and provide a CATAAS random
image endpoint. The default is:

```text
https://cataas.com/cat
```

A tagged endpoint such as `https://cataas.com/cat/cute` also works. Each run
chooses a saying deterministically for the current calendar day, asks CATAAS
for a fresh cat with that saying, and creates a unique local image URL. Running
the action twice on the same day therefore keeps the saying but changes the
cat. The generated source request is not cached.

The renderer uses the Pillow installation included with Home Assistant to
auto-rotate and center-crop the response to 800x480, increase grayscale
contrast, and apply Floyd-Steinberg dithering. It writes the final PNG under
`/config/www/hatodor/motd-cache`; only the 20 newest generated images are kept.
The rendering command has a 20-second download timeout and rejects responses
larger than 10 MiB.

The bundled tone choices are **Mixed**, **Dry**, **Chaotic**, **Encouraging**,
and **Tiny dictator**. To customize them, edit:

```text
/config/hatodor/cat_sayings.json
```

Keep the file as a JSON object whose keys are tone names and whose values are
lists of sayings. Config Sync deliberately does not overwrite this file after
creating it. Delete it and rerun Config Sync if you want to restore the bundled
sayings.

The repository copies of the package and ESPHome YAML are authoritative; local
edits to those two files will be overwritten the next time this App runs. The
Super Productivity patches are deliberately small in-place modifications rather
than a vendored fork. A later HACS update may overwrite them; rerun Hatodor
Config Sync after updating that integration to reapply the patches.

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

## Daily deadlines

Set task deadlines normally in Super Productivity. Timed deadlines are shown on
the right side of the E1001 row in local time.

At daily rollover, Hatodor preserves the clock time of every timed deadline but
moves its date into the new dashboard day. With a 04:00 rollover, for example,
a deadline of 07:30 remains 07:30 on the new calendar day, while a deadline of
02:00 belongs to the following calendar date so it still falls in that same
Evening dashboard period.

This rollover changes only Super Productivity deadline fields. It does not move
or otherwise alter SP's separate planned/scheduled task time.

## Completion lifecycle

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

Version 0.7.1 changes only the ESPHome source to avoid an intermediate loading
refresh before a photo appears. Update and run Config Sync, then install the
E1001 firmware wirelessly from ESPHome Builder. A Home Assistant restart is not
required when upgrading from 0.7.0.
