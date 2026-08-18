# Super Productivity Desktop — HAOS App

## What this does

This App runs the real Super Productivity **Electron desktop application** on
Home Assistant OS using `jlesage/baseimage-gui`. It provides:

- the Super Productivity GUI through a browser/noVNC on port 5800;
- persistent desktop/profile data in the HA App data volume;
- a proxy on port 3877 to SP's loopback-only REST API;
- automatic Bearer-token injection so the current `ha-super-productivity`
  integration can work with Super Productivity 18.19+.

## First installation

1. Put this repository on GitHub, or copy the `super_productivity_desktop`
   folder into Home Assistant's local Apps directory.
2. In Home Assistant open **Settings → Apps → App store → Repositories**.
3. Add the GitHub repository URL.
4. Install **Super Productivity Desktop**.
5. Start the App.
6. Click **Open Web UI**.

The first build downloads the pinned Super Productivity Linux package, so HAOS
needs Internet access during the build.

## First-run Super Productivity setup

In the Super Productivity desktop shown through the Web UI:

1. Open **Settings → Misc**.
2. Enable the **Local REST API**.
3. Find the REST API **Access Token** and copy it.
4. Return to Home Assistant → **Settings → Apps → Super Productivity Desktop
   → Configuration**.
5. Paste it into **sp_access_token**.
6. Save and restart the App.

Super Productivity 18.19.0 requires `Authorization: Bearer <token>` for all
Local REST API calls except `GET /health`.

The HA integration currently does not send this token itself, so this App's
port-3877 proxy injects it before forwarding requests to `127.0.0.1:3876`.

## Configure `ha-super-productivity`

Install `jloops412/ha-super-productivity` through HACS, restart Home Assistant,
and add the integration.

Use:

- **Host:** the LAN IP address of the HAOS machine
- **Port:** `3877`

The integration should then expose Super Productivity projects as Home
Assistant `todo` entities.

## Quick test

From another machine on your trusted LAN:

    curl http://HOME_ASSISTANT_IP:3877/health

should reach the SP health endpoint without requiring a token.

A normal protected endpoint should also work through the proxy after
`sp_access_token` is configured:

    curl http://HOME_ASSISTANT_IP:3877/status

## Persistence and backups

The HA App data volume is mounted at `/config`, matching
`jlesage/baseimage-gui`'s persistent HOME/XDG layout.

The App is configured for a **cold backup**, so Supervisor stops the Electron
process before its persistent profile is captured.

## Architecture and pinned versions

Supported:

- `amd64`

Pinned versions:

- Super Productivity: `18.19.0`
- jlesage/baseimage-gui: `ubuntu-24.04-v4.13.2`

The jlesage base image itself supports arm64, but Super Productivity 18.19.0
does not currently publish a Linux arm64 `.deb`, so this App intentionally does
not claim `aarch64` support.

## Security

Port 3877 is reachable on the HAOS host and becomes an authenticated bridge to
Super Productivity because the proxy injects your configured token.

Do **not** port-forward 3877 or expose it to the public Internet. The access
token is stored in Home Assistant App configuration and is not logged by the
proxy.

Electron is started with `--no-sandbox` because Chromium sandbox namespace
features are often unavailable in application containers. The process remains
inside the HAOS-managed Docker/App isolation boundary.

## Troubleshooting

### `/health` works, but other requests return 401

Copy the Access Token again from Super Productivity, paste it into the App's
`sp_access_token` configuration field, then restart the App.

### The proxy returns 502

The proxy is alive but SP's REST API is not accepting connections yet. Check:

- Super Productivity is actually running in the Web UI;
- the Local REST API has been enabled;
- App logs for an Electron startup failure.

### Port conflict

If 5800 or 3877 is already used, change its **host-side** mapping in the App's
Network settings. If you change 3877, use the new mapped port when configuring
the Home Assistant integration.
