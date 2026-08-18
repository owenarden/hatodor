# Changelog

## 0.2.0

- Pin Super Productivity 18.19.0.
- Inject the SP 18.19+ REST Bearer token in the port-3877 proxy.
- Add `sp_access_token` as an optional HA App password field for first-run setup.
- Correct architecture declaration to amd64 only because the current upstream
  Linux release does not publish an arm64 `.deb`.

## 0.1.0

- Initial experimental HAOS App.
