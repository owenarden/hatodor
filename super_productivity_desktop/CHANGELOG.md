# Changelog

## 0.4.0

- Work around Ubuntu `systemd` package configuration inside
  `jlesage/baseimage-gui`.
- Temporarily replace the base image's `/var/log -> /config/log` symlink with
  a real directory while apt installs Super Productivity and dependencies.
- Restore `/var/log -> /config/log` immediately after package installation.
- Set a noninteractive apt frontend and `C.UTF-8` locale for cleaner builds.

## 0.3.0

- Add required Home Assistant image labels for Supervisor local builds.
- Use the official stable/latest Super Productivity amd64 DEB URL.
