# Hatodor Home Assistant Apps

Home Assistant App repository for the Hatodor morning-dashboard stack.

## Apps

### Super Productivity Desktop

Runs the Super Productivity Electron desktop application inside
`jlesage/baseimage-gui` and exposes the authenticated local REST proxy used by
the Home Assistant Super Productivity integration.

See `super_productivity_desktop/DOCS.md`.

### Hatodor Config Sync

A one-shot App that deploys the repository-managed configuration files into the
Home Assistant configuration directory:

- `packages/morning_dashboard.yaml`
- `esphome/reterminal-e1001-morning.yaml`

It also applies a small idempotent patch to the installed HACS Super
Productivity integration so project task fetches use `include_done=True`. This
keeps completed routine/reminder tasks visible to the dashboard until Hatodor's
rollover logic resets or removes them. A later HACS update can overwrite that
one-line patch; rerun Config Sync after updating the Super Productivity
integration.

The source copies live under `hatodor_config_sync/managed/`. They are the source
of truth; local edits to the deployed YAML copies are overwritten when Config
Sync runs.

For Home Assistant to load the package, perform this bootstrap once in
`/config/configuration.yaml`:

```yaml
homeassistant:
  packages: !include_dir_named packages
```

If a `homeassistant:` block already exists, add the `packages:` entry to that
block rather than creating a duplicate.

When managed configuration changes, bump `hatodor_config_sync/config.yaml`'s
version so Home Assistant offers the normal App update. Installing/updating the
Config Sync App deploys the new files and reapplies the integration patch.
Package or Python integration changes require a Home Assistant restart; ESPHome
changes still require an Install/OTA to the device.
