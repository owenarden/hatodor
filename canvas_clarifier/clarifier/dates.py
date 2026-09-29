"""Find the student's real date in text like
"DUE: 10/6/2026 (Period 3) or 10/7/2026 (Period 2)",
"10/20/2026 (ODD BLOCKS) or 10/21/2026 (EVEN BLOCKS)",
"Tues 10/6 (Block 3) and Weds 10/7 (Blocks 2, 4 and 6)", or
"First semester due December 14th, 3:30PM".

Only dates with a block/period qualifier, or dates introduced by "due", are
trusted; bare fractions like rubric scores ("4/5") are ignored.
"""

from __future__ import annotations

import html
import re
from dataclasses import dataclass
from datetime import date, time

MONTHS = {m: i for i, m in enumerate(
    ["jan", "feb", "mar", "apr", "may", "jun", "jul", "aug", "sep", "oct", "nov", "dec"], 1)}

_WEEKDAY = r"(?:mon|tue|tues|wed|weds|thu|thur|thurs|fri|sat|sun)[a-z]*\.?,?\s+"
_NUMERIC = r"(?P<m>\d{1,2})/(?P<d>\d{1,2})(?:/(?P<y>\d{2,4}))?"
_NAMED = (r"(?P<mon>jan|feb|mar|apr|may|jun|jul|aug|sept?|oct|nov|dec)[a-z]*\.?\s+"
          r"(?P<nd>\d{1,2})(?:st|nd|rd|th)?(?:,?\s+(?P<ny>\d{4}))?")
_DATE = re.compile(rf"(?P<wd>{_WEEKDAY})?(?:{_NUMERIC}|{_NAMED})(?![\d/])", re.I)
_TIME = re.compile(r"^\s*,?\s*(?:at\s+|@\s*)?(?P<h>\d{1,2})(?::(?P<mi>\d{2}))?\s*(?P<ap>[ap])\.?m\.?", re.I)
_QUAL = re.compile(r"^\s*\((?P<q>[^)]{1,60})\)")
_DUE_BEFORE = re.compile(r"\bdue\b[^.\n]{0,25}$", re.I)
_TAG = re.compile(r"<[^>]+>")


@dataclass
class Found:
    day: date
    at: time | None
    qualifier: str | None
    start: int


def strip_html(s: str | None) -> str:
    return re.sub(r"\s+", " ", html.unescape(_TAG.sub(" ", s or ""))).strip()


def _year_for(m: int, d: int, y: int | None, term_start: date | None,
              term_end: date | None, today: date) -> date | None:
    if y is not None and y < 100:
        y += 2000
    candidates = []
    years = {today.year - 1, today.year, today.year + 1}
    if term_start:
        years |= {term_start.year}
    if term_end:
        years |= {term_end.year}
    for cy in sorted(years):
        try:
            candidates.append(date(cy, m, d))
        except ValueError:
            continue
    if not candidates:
        return None
    in_term = [c for c in candidates
               if (not term_start or c >= term_start) and (not term_end or c <= term_end)]
    if y is not None:
        try:
            stated = date(y, m, d)
        except ValueError:
            stated = None
        # Trust the stated year if it is in the term; otherwise treat it as a
        # typo ("10/7/2027") and fall back to the in-term candidate.
        if stated and (not in_term or stated in in_term):
            return stated
    if in_term:
        return in_term[0]
    return min(candidates, key=lambda c: abs((c - today).days))


def find_dates(text: str, term_start: date | None = None, term_end: date | None = None,
               today: date | None = None) -> list[Found]:
    today = today or date.today()
    out: list[Found] = []
    for mt in _DATE.finditer(text):
        if mt.group("m"):
            m, d = int(mt.group("m")), int(mt.group("d"))
            y = int(mt.group("y")) if mt.group("y") else None
        else:
            m = MONTHS[mt.group("mon").lower()[:3]]
            d = int(mt.group("nd"))
            y = int(mt.group("ny")) if mt.group("ny") else None
        if not (1 <= m <= 12 and 1 <= d <= 31):
            continue
        day = _year_for(m, d, y, term_start, term_end, today)
        if not day:
            continue
        rest = text[mt.end():]
        at = None
        tm = _TIME.match(rest)
        if tm:
            h = int(tm.group("h")) % 12 + (12 if tm.group("ap").lower() == "p" else 0)
            at = time(h, int(tm.group("mi") or 0))
            rest = rest[tm.end():]
        qm = _QUAL.match(rest)
        qualifier = qm.group("q") if qm else None
        before = text[max(0, mt.start() - 30):mt.start()]
        trusted = bool(qualifier and _qualifier_periods(qualifier)) or bool(
            _DUE_BEFORE.search(before)) or bool(mt.group("wd")) or bool(
            mt.group("mon")) or y is not None
        if not trusted:
            continue
        out.append(Found(day=day, at=at, qualifier=qualifier, start=mt.start()))
    return out


def _qualifier_periods(q: str) -> tuple[set[int], str | None, bool] | None:
    ql = q.lower()
    if not re.search(r"\b(period|per|block|blocks|odd|even|all)\b", ql):
        return None
    nums = {int(n) for n in re.findall(r"\b(\d)\b", ql)} if re.search(
        r"\b(period|per|block|blocks)\b", ql) else set()
    parity = "odd" if re.search(r"\bodd\b", ql) else "even" if re.search(r"\beven\b", ql) else None
    everyone = bool(re.search(r"\ball\b", ql))
    if not nums and not parity and not everyone:
        return None
    return nums, parity, everyone


def _matches(q: str | None, period: int | None) -> bool | None:
    """True/False if the qualifier says whether it applies; None if no qualifier."""
    if not q:
        return None
    parsed = _qualifier_periods(q)
    if not parsed:
        return None
    nums, parity, everyone = parsed
    if everyone:
        return True
    if period is None:
        return False
    if nums:
        return int(period) in nums
    return parity == ("odd" if int(period) % 2 else "even")


def pick_date(text: str, period: int | None, term_start: date | None = None,
              term_end: date | None = None, today: date | None = None) -> Found | None:
    """The date in `text` that applies to this student's period, if clear."""
    found = find_dates(strip_html(text), term_start, term_end, today)
    if not found:
        return None
    qualified = [(f, _matches(f.qualifier, period)) for f in found]
    mine = [f for f, ok in qualified if ok]
    if mine:
        return mine[0]
    if any(ok is False for _, ok in qualified):
        return None          # qualified dates exist, none for this student
    distinct = {f.day for f in found}
    if len(distinct) > 1 and (term_start or term_end):
        # e.g. "First semester due Dec 14 … Second semester due May 24"
        found = [f for f in found
                 if (not term_start or f.day >= term_start)
                 and (not term_end or f.day <= term_end)]
        distinct = {f.day for f in found}
    if len(distinct) == 1:
        return found[0]
    return None              # several unqualified dates: ambiguous
