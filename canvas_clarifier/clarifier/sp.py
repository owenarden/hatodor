"""Super Productivity Local REST API client (through hatodor's sp_proxy)."""

from __future__ import annotations

import json
import re
import urllib.error
import urllib.parse
import urllib.request

KEY_LINE = re.compile(r"^clarifier:key=(\S+)\s*$", re.M)


class SPError(Exception):
    pass


class SP:
    def __init__(self, base_url: str, dry_run: bool = True, timeout: int = 15):
        self.base = base_url.rstrip("/")
        self.dry_run = dry_run
        self.timeout = timeout
        self.log: list[str] = []      # planned/performed writes, for the status page
        self.deadline_ignored = False

    def _req(self, method: str, path: str, params: dict | None = None, body: dict | None = None):
        url = self.base + path
        if params:
            url += "?" + urllib.parse.urlencode(params)
        data = json.dumps(body).encode() if body is not None else None
        req = urllib.request.Request(url, data=data, method=method,
                                     headers={"Content-Type": "application/json"})
        try:
            with urllib.request.urlopen(req, timeout=self.timeout) as resp:
                payload = json.loads(resp.read().decode() or "{}")
        except urllib.error.HTTPError as e:
            try:
                detail = json.loads(e.read().decode()).get("error", {})
            except Exception:
                detail = {}
            raise SPError(f"{method} {path}: HTTP {e.code} {detail.get('code', '')}"
                          f" {detail.get('message', '')}".strip()) from e
        except (urllib.error.URLError, TimeoutError) as e:
            raise SPError(f"{method} {path}: {e}") from e
        if isinstance(payload, dict) and payload.get("ok") is False:
            raise SPError(f"{method} {path}: {payload.get('error')}")
        return payload.get("data", payload) if isinstance(payload, dict) else payload

    # reads ---------------------------------------------------------------
    def health(self) -> dict:
        return self._req("GET", "/health")

    def project_id(self, title: str) -> str | None:
        projects = self._req("GET", "/projects", {"query": title}) or []
        for p in projects:
            if (p.get("title") or "").strip().lower() == title.strip().lower():
                return p.get("id")
        return None

    def tasks(self, project_id: str) -> list[dict]:
        """Active and archived tasks, done or not, in the project. Archived ones
        are marked with `_archived` (the API's source=all does not say which)."""
        base = {"projectId": project_id, "includeDone": "true"}
        active = self._req("GET", "/tasks", dict(base, source="active")) or []
        archived = self._req("GET", "/tasks", dict(base, source="archived")) or []
        return active + [dict(t, _archived=True) for t in archived]

    # writes (skipped in dry run) -------------------------------------------
    def create(self, fields: dict) -> str | None:
        body = dict(fields, isIgnoreShortSyntax=True)
        self.log.append(f"create: {fields.get('title')}")
        if self.dry_run:
            return None
        created = self._req("POST", "/tasks", body=body) or {}
        self._check_deadline(fields, created)
        return created.get("id")

    def update(self, task_id: str, fields: dict, label: str) -> None:
        if not fields:
            return
        self.log.append(f"update {label}: {', '.join(sorted(fields))}")
        if self.dry_run:
            return
        body = dict(fields)
        if "title" in body:
            body["isIgnoreShortSyntax"] = True
        updated = self._req("PATCH", f"/tasks/{task_id}", body=body) or {}
        self._check_deadline(fields, updated)

    def _check_deadline(self, sent: dict, task: dict) -> None:
        """Super Productivity before v19 accepts deadline fields but drops them."""
        if not isinstance(task, dict) or "id" not in task:
            return
        wanted = sent.get("deadlineWithTime") or sent.get("deadlineDay")
        if wanted and not (task.get("deadlineWithTime") or task.get("deadlineDay")):
            self.deadline_ignored = True


def task_key(task: dict) -> str | None:
    m = KEY_LINE.search(task.get("notes") or "")
    return m.group(1) if m else None
