# Super Productivity Desktop — HAOS App

## Version 0.5 runtime fix

Version 0.5 installs Ubuntu `libgbm1` because the Super Productivity Electron binary directly requires `libgbm.so.1`. It also performs an `ldd` check during the image build and uses software rendering in the virtual X/VNC session.


## Version 0.4 install fix

The jlesage base image deliberately maps `/var/log` to `/config/log`. Ubuntu's `systemd` package post-install script expects `/var/log` to be a normal directory when it is configured as a dependency of the Super Productivity DEB. Version 0.4 temporarily restores a real `/var/log` during the apt transaction and reinstates the jlesage symlink afterward.


## Version 0.3 install fixes

This revision fixes two install-time problems in the earlier experimental build:

1. It adds the `io.hass.version`, `io.hass.type`, and `io.hass.arch` labels
   required for Supervisor-built Apps.
2. It downloads the Linux package using Super Productivity's official
   `releases/latest/download/superProductivity-amd64.deb` URL instead of a
   version-specific URL that returned 404.

## Install

Put this repository on GitHub, then add its repository URL to the Home
Assistant App store.

After changing a custom App repository, use the App store menu's
**Check for updates** action so Supervisor reloads the repository metadata.

Install **Super Productivity Desktop**, start it, then open its Web UI.

## First run

In the Super Productivity GUI:

1. Enable the Local REST API.
2. If Super Productivity shows an API access token, copy it.
3. In Home Assistant, put it in the App's `sp_access_token` setting.
4. Restart this App.

Configure `jloops412/ha-super-productivity` with the HAOS host's LAN IP and
port 3877.

## Debugging an install failure

Home Assistant documents Supervisor logs as the place to inspect App
validation/build failures:

**Settings → System → Logs → Supervisor**

If installation still fails, copy the bottom of the Supervisor log beginning
with the line mentioning `super_productivity_desktop`; that should identify
the remaining build problem directly.

## Notes

- Architecture: amd64 only.
- noVNC Web UI: host port 5800 by default.
- REST proxy: host port 3877 by default.
- `/config` is the persistent HA App data volume.
- Do not expose port 3877 to the public Internet.
