"""Bell schedule: when does a course (by period) meet on a given date?"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date, datetime, time, timedelta
from zoneinfo import ZoneInfo

WEEKDAYS = ["mon", "tue", "wed", "thu", "fri", "sat", "sun"]


def _parse_span(span: str) -> tuple[time, time]:
    start, end = (s.strip() for s in span.split("-"))
    return time.fromisoformat(start), time.fromisoformat(end)


@dataclass
class Schedule:
    tz: ZoneInfo
    term_start: date | None = None
    term_end: date | None = None
    # day type name -> {period: (start, end)}
    day_types: dict[str, dict[int, tuple[time, time]]] = field(default_factory=dict)
    # weekday name -> day type name
    weekday_types: dict[str, str] = field(default_factory=dict)
    # date -> day type name, or None for no school
    overrides: dict[date, str | None] = field(default_factory=dict)

    @classmethod
    def from_config(cls, cfg: dict, tz: ZoneInfo) -> "Schedule":
        sched = cfg or {}
        term = sched.get("term") or {}
        s = cls(tz=tz,
                term_start=_as_date(term.get("start")),
                term_end=_as_date(term.get("end")))
        for name, spec in (sched.get("day_types") or {}).items():
            s.day_types[name] = {int(p): _parse_span(v)
                                 for p, v in (spec.get("periods") or {}).items()}
            for wd in spec.get("weekdays") or []:
                s.weekday_types[wd.lower()[:3]] = name
        for d, name in (sched.get("overrides") or {}).items():
            s.overrides[_as_date(d)] = name if name not in ("none", "", None) else None
        return s

    def day_type(self, d: date) -> str | None:
        if d in self.overrides:
            return self.overrides[d]
        if self.term_start and d < self.term_start:
            return None
        if self.term_end and d > self.term_end:
            return None
        return self.weekday_types.get(WEEKDAYS[d.weekday()])

    def meeting(self, period: int | None, d: date) -> tuple[datetime, datetime] | None:
        """(start, end) of the course's meeting on date d, if it meets."""
        if period is None:
            return None
        name = self.day_type(d)
        if not name:
            return None
        span = self.day_types.get(name, {}).get(int(period))
        if not span:
            return None
        return (datetime.combine(d, span[0], self.tz),
                datetime.combine(d, span[1], self.tz))

    def meeting_on_or_after(self, period: int | None, d: date,
                            max_days: int = 14) -> tuple[datetime, datetime] | None:
        for i in range(max_days + 1):
            m = self.meeting(period, d + timedelta(days=i))
            if m:
                return m
        return None

    def parity(self, period: int | None) -> str | None:
        if period is None:
            return None
        return "odd" if int(period) % 2 else "even"


def _as_date(v) -> date | None:
    if v is None or v == "":
        return None
    if isinstance(v, datetime):
        return v.date()
    if isinstance(v, date):
        return v
    return date.fromisoformat(str(v))
