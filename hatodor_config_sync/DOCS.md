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

After the sync App runs, reload/restart Home Assistant for package changes to
take effect. ESPHome source changes still require installing the firmware to the
device (normally OTA from the ESPHome UI).
