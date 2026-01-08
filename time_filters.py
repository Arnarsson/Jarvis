"""Shared helpers for parsing natural language time filters."""

import re
from calendar import monthrange
from datetime import datetime, timedelta
from typing import Optional, Tuple

TimeRange = Tuple[Optional[datetime], Optional[datetime]]

_MONTH_LOOKUP = {
    "jan": 1, "january": 1,
    "feb": 2, "february": 2,
    "mar": 3, "march": 3,
    "apr": 4, "april": 4,
    "may": 5,
    "jun": 6, "june": 6,
    "jul": 7, "july": 7,
    "aug": 8, "august": 8,
    "sep": 9, "sept": 9, "september": 9,
    "oct": 10, "october": 10,
    "nov": 11, "november": 11,
    "dec": 12, "december": 12,
}

_ABSOLUTE_FORMATS = [
    ("%Y-%m-%d", "day"),
    ("%Y/%m/%d", "day"),
    ("%Y.%m.%d", "day"),
    ("%Y-%m-%d %H:%M", "day"),
    ("%Y-%m-%d %H:%M:%S", "day"),
    ("%m/%d/%Y", "day"),
    ("%d/%m/%Y", "day"),
    ("%B %d %Y", "day"),
    ("%b %d %Y", "day"),
    ("%d %B %Y", "day"),
    ("%d %b %Y", "day"),
    ("%B %Y", "month"),
    ("%b %Y", "month"),
    ("%Y-%m", "month"),
    ("%Y/%m", "month"),
    ("%Y.%m", "month"),
    ("%Y", "year"),
]


def _range_for_precision(dt: datetime, precision: str) -> TimeRange:
    if precision == "day":
        start = dt.replace(hour=0, minute=0, second=0, microsecond=0)
        end = start + timedelta(days=1)
        return start, end
    if precision == "month":
        start = dt.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
        _, month_days = monthrange(dt.year, dt.month)
        end = start + timedelta(days=month_days)
        return start, end
    if precision == "year":
        start = datetime(dt.year, 1, 1)
        end = datetime(dt.year + 1, 1, 1)
        return start, end
    return dt, dt + timedelta(days=1)


def _parse_absolute_time(expr: str, now: datetime) -> Optional[TimeRange]:
    if not expr:
        return None

    expr = expr.strip()
    if not expr:
        return None

    cleaned = expr.replace(",", " ").strip()
    cleaned = re.sub(r"\s+", " ", cleaned)

    iso_candidate = cleaned
    if iso_candidate.upper().endswith("Z"):
        iso_candidate = iso_candidate[:-1]
        try:
            dt = datetime.fromisoformat(iso_candidate)
            dt = dt.replace(tzinfo=None)
            return _range_for_precision(dt, "day")
        except ValueError:
            pass

    try:
        dt = datetime.fromisoformat(cleaned)
        dt = dt.replace(tzinfo=None)
        return _range_for_precision(dt, "day")
    except ValueError:
        pass

    for fmt, precision in _ABSOLUTE_FORMATS:
        try:
            dt = datetime.strptime(cleaned, fmt)
        except ValueError:
            continue
        return _range_for_precision(dt, precision)

    md_match = re.match(
        r"(?P<month>[a-z]+)\s+(?P<day>\d{1,2})(?:st|nd|rd|th)?$",
        cleaned,
        re.IGNORECASE,
    )
    if md_match:
        month_name = md_match.group("month").lower()
        month = _MONTH_LOOKUP.get(month_name)
        if month:
            day = int(md_match.group("day"))
            try:
                dt = datetime(now.year, month, day)
                return _range_for_precision(dt, "day")
            except ValueError:
                pass

    m_match = re.match(r"(?P<month>[a-z]+)$", cleaned, re.IGNORECASE)
    if m_match:
        month_name = m_match.group("month").lower()
        month = _MONTH_LOOKUP.get(month_name)
        if month:
            dt = datetime(now.year, month, 1)
            return _range_for_precision(dt, "month")

    return None


def _parse_relative_time(expr: str, now: datetime) -> Optional[TimeRange]:
    if not expr:
        return None

    reduced = expr.lower().strip()
    if not reduced:
        return None

    start_of_day = lambda dt: dt.replace(hour=0, minute=0, second=0, microsecond=0)

    if reduced in {"today", "this day"}:
        start = start_of_day(now)
        return start, start + timedelta(days=1)
    if reduced in {"yesterday", "prev day", "previous day"}:
        start = start_of_day(now - timedelta(days=1))
        return start, start + timedelta(days=1)

    if "last week" in reduced or "past week" in reduced:
        return now - timedelta(weeks=1), now
    if "last month" in reduced or "past month" in reduced:
        return now - timedelta(days=30), now
    if "last year" in reduced or "past year" in reduced:
        return now - timedelta(days=365), now

    match = re.search(r"(?:last|past)\s+(\d+)\s+(day|week|month|hour|year)s?", reduced)
    if match:
        count = int(match.group(1))
        unit = match.group(2)
        deltas = {
            "day": timedelta(days=count),
            "week": timedelta(weeks=count),
            "month": timedelta(days=count * 30),
            "hour": timedelta(hours=count),
            "year": timedelta(days=count * 365),
        }
        delta = deltas.get(unit)
        if delta:
            return now - delta, now

    return None


def _parse_single_time_expr(expr: str, now: datetime) -> Optional[TimeRange]:
    return _parse_relative_time(expr, now) or _parse_absolute_time(expr, now)


def normalize_timestamp(value: Optional[str]) -> Optional[datetime]:
    if not value:
        return None
    text = value.strip()
    if not text:
        return None
    try:
        return datetime.fromisoformat(text.replace("Z", "+00:00")).replace(tzinfo=None)
    except ValueError:
        for fmt in ("%Y-%m-%d %H:%M:%S", "%Y/%m/%d %H:%M:%S"):
            try:
                return datetime.strptime(text, fmt)
            except ValueError:
                continue
    return None


def timestamp_in_range(ts: Optional[str], time_range: Optional[TimeRange]) -> bool:
    if not time_range or not ts:
        return True
    dt = normalize_timestamp(ts)
    if not dt:
        return True
    start, end = time_range
    if start and dt < start:
        return False
    if end and dt >= end:
        return False
    return True


def parse_time_query(time_query: str) -> Optional[TimeRange]:
    """Parse natural language time queries into (start, end) range."""
    if not time_query:
        return None

    raw = time_query.strip()
    if not raw:
        return None

    lowered = raw.lower()
    if lowered in {"all", "any", "everything"}:
        return None

    now = datetime.now()

    range_match = re.search(r"(?:between|from)\s+(.+?)\s+(?:and|to)\s+(.+)", raw, re.IGNORECASE)
    if range_match:
        start_expr = range_match.group(1).strip(" ,")
        end_expr = range_match.group(2).strip(" ,")
        start_range = _parse_single_time_expr(start_expr, now)
        end_range = _parse_single_time_expr(end_expr, now)
        if start_range and end_range:
            start = start_range[0]
            end = end_range[1] or end_range[0]
            if start and end and start > end:
                start, end = end, start
            return start, end

    if lowered.startswith("since "):
        since_expr = raw[6:].strip()
        parsed = _parse_single_time_expr(since_expr, now)
        if parsed:
            return parsed[0], now

    if lowered.startswith("after "):
        after_expr = raw[6:].strip()
        parsed = _parse_single_time_expr(after_expr, now)
        if parsed:
            start = parsed[1] or parsed[0]
            return start, None

    if lowered.startswith("before "):
        before_expr = raw[7:].strip()
        parsed = _parse_single_time_expr(before_expr, now)
        if parsed:
            return None, parsed[0]

    if lowered.startswith("until "):
        until_expr = raw[6:].strip()
        parsed = _parse_single_time_expr(until_expr, now)
        if parsed:
            return None, parsed[0]

    if lowered.startswith("on "):
        on_expr = raw[3:].strip()
        parsed = _parse_single_time_expr(on_expr, now)
        if parsed:
            return parsed

    return _parse_single_time_expr(raw, now)
