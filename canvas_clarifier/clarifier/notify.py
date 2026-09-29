"""Deliver alerts through Home Assistant (Supervisor API)."""

from __future__ import annotations

import json
import os
import urllib.request

SUPERVISOR = os.environ.get("CLARIFIER_HA_URL", "http://supervisor/core/api")


def send(title: str, lines: list[str], service: str = "", dry_run: bool = False) -> str:
    message = "\n".join(f"• {l}" for l in lines)
    if dry_run:
        return f"[dry run] would notify: {title}\n{message}"
    token = os.environ.get("SUPERVISOR_TOKEN")
    if not token:
        return f"(no Home Assistant token) {title}\n{message}"
    if service:
        domain, svc = "notify", service.removeprefix("notify.")
        body = {"title": title, "message": message}
    else:
        domain, svc = "persistent_notification", "create"
        body = {"title": title, "message": message, "notification_id": "canvas_clarifier"}
    req = urllib.request.Request(
        f"{SUPERVISOR}/services/{domain}/{svc}", data=json.dumps(body).encode(), method="POST",
        headers={"Authorization": f"Bearer {token}", "Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=15):
        pass
    return f"notified via {domain}.{svc}: {title}"
