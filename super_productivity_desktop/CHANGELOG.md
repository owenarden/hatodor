# Changelog

## 0.6.0

- Install Ubuntu `libasound2t64`, which provides `libasound.so.2` required by Electron at runtime.
- Extend GitHub Actions from a build-only check to a container startup smoke test.
- Require the built container to remain running and the noVNC HTTP endpoint on port 5800 to become reachable.
- Dump container logs automatically when the smoke test fails.

## 0.5.0

- Install Ubuntu `libgbm1`, which provides `libgbm.so.1` required by the
  Super Productivity Electron binary at startup.
- Add a build-time `ldd` check so unresolved ELF shared libraries cause an
  explicit image-build failure instead of a runtime crash.
- Start Electron with `--disable-gpu` for predictable software rendering in
  the virtual X/VNC environment.

## 0.4.0

- Work around Ubuntu `systemd` package configuration inside
  `jlesage/baseimage-gui` by temporarily making `/var/log` a real directory.
