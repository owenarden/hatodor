"""App options (from Home Assistant) and course profiles (courses.yaml)."""

from __future__ import annotations

import json
import os
import re
import shutil
import socket
from dataclasses import dataclass, field
from pathlib import Path
from zoneinfo import ZoneInfo

import yaml

from .schedule import Schedule

OPTIONS_FILE = Path(os.environ.get("CLARIFIER_OPTIONS", "/data/options.json"))
CONFIG_DIR = Path(os.environ.get("CLARIFIER_CONFIG_DIR", "/config"))
EXAMPLE_PROFILE = Path(os.environ.get("CLARIFIER_EXAMPLE", "/app/courses.example.yaml"))

VISIBLE = {"homework", "test", "prep", "project", "extra_credit", "unclassified"}
HIDDEN = {"in_class", "gradebook", "ignore", "no_points"}


@dataclass
class Options:
    canvas_base_url: str = ""
    canvas_token: str = ""
    sp_url: str = "http://172.30.32.1:3877"
    sp_project: str = "School"
    poll_minutes: int = 15
    dry_run: bool = True
    notify_service: str = ""
    lookback_days: int = 21
    lookahead_days: int = 35

    @classmethod
    def load(cls, path: Path = OPTIONS_FILE) -> "Options":
        data = json.loads(path.read_text()) if path.exists() else {}
        known = {k: v for k, v in data.items() if k in cls.__dataclass_fields__}
        opts = cls(**known)
        # Environment overrides make local runs possible outside Home Assistant.
        for name in cls.__dataclass_fields__:
            env = os.environ.get(f"CLARIFIER_{name.upper()}")
            if env is not None:
                cur = getattr(opts, name)
                if isinstance(cur, bool):
                    env = env.lower() in ("1", "true", "yes")
                elif isinstance(cur, int):
                    env = int(env)
                setattr(opts, name, env)
        return opts


@dataclass
class Rule:
    category: str | None = None
    match: re.Pattern | None = None
    when: str | None = None
    completion: str | None = None
    due_from: str | None = None
    also_create: str | None = None

    @classmethod
    def from_dict(cls, d: dict) -> "Rule":
        pat = d.get("match")
        if pat:
            # Allow inline flags anywhere ("^(?i)…") by hoisting them.
            flags = re.IGNORECASE if "(?i)" in pat else 0
            pat = re.compile(pat.replace("(?i)", ""), flags | re.IGNORECASE)
        return cls(category=d.get("category"), match=pat, when=d.get("when"),
                   completion=d.get("completion"), due_from=d.get("due_from"),
                   also_create=d.get("also_create"))


@dataclass
class Course:
    id: int
    name: str
    short: str
    period: int | None = None
    teacher: str | None = None
    ignore: bool = False
    default_category: str | None = None
    due_from: str | None = None
    rules: list[Rule] = field(default_factory=list)
    notes: str = ""


@dataclass
class Profile:
    tz: ZoneInfo
    schedule: Schedule
    placeholder_due_time: str
    global_rules: list[Rule]
    courses: dict[int, Course]
    grace_days: int = 14
    drop_announcement_if: list[str] = field(default_factory=list)
    source: str = ""
    is_example: bool = False

    @classmethod
    def from_yaml(cls, text: str) -> "Profile":
        raw = yaml.safe_load(text) or {}
        student = raw.get("student") or {}
        tz = ZoneInfo(student.get("timezone", "America/Los_Angeles"))
        courses = {}
        for cid, c in (raw.get("courses") or {}).items():
            c = c or {}
            name = c.get("name") or f"Course {cid}"
            courses[int(cid)] = Course(
                id=int(cid), name=name,
                short=c.get("short") or _short_name(name),
                period=c.get("period"), teacher=c.get("teacher"),
                ignore=bool(c.get("ignore")),
                default_category=c.get("default_category"),
                due_from=c.get("due_from"),
                rules=[Rule.from_dict(r) for r in c.get("rules") or []],
                notes=c.get("notes") or "")
        ann = raw.get("announcements") or {}
        return cls(tz=tz,
                   schedule=Schedule.from_config(raw.get("schedule") or {}, tz),
                   placeholder_due_time=str(student.get("placeholder_due_time", "23:59")),
                   global_rules=[Rule.from_dict(r) for r in raw.get("global_rules") or []],
                   courses=courses,
                   grace_days=int(student.get("grading_grace_days", 14)),
                   drop_announcement_if=list(ann.get("drop_if") or []))

    @classmethod
    def load(cls, config_dir: Path = CONFIG_DIR) -> "Profile":
        path = config_dir / "courses.yaml"
        if not path.exists() and EXAMPLE_PROFILE.exists():
            config_dir.mkdir(parents=True, exist_ok=True)
            shutil.copy(EXAMPLE_PROFILE, path)
            print(f"Installed the example course profile; replace it with yours at "
                  f"{host_config_hint()}/courses.yaml")
        text = path.read_text()
        profile = cls.from_yaml(text)
        profile.source = str(path)
        profile.is_example = (EXAMPLE_PROFILE.exists()
                              and text.strip() == EXAMPLE_PROFILE.read_text().strip())
        return profile


def host_config_hint() -> str:
    """Where /config appears on the Home Assistant host (Samba, File editor, SSH).

    An App's hostname is "<repo-prefix>-<slug with dashes>"; its config folder
    is /addon_configs/<repo-prefix>_<slug>."""
    host = os.environ.get("HOSTNAME") or socket.gethostname()
    prefix = host.split("-", 1)[0] if "-" in host else ""
    return f"/addon_configs/{prefix}_canvas_clarifier" if prefix else \
        "/addon_configs/<id>_canvas_clarifier"


def _short_name(name: str) -> str:
    # "US History 7 (Teacher)" -> "US History"; "English 7" -> "English"
    base = re.sub(r"\s*\(.*?\)\s*", " ", name)
    base = re.sub(r"\b\d+\b", "", base)
    return re.sub(r"\s+", " ", base).strip()[:18] or name[:18]
