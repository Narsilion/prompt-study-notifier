from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from zoneinfo import ZoneInfo


@dataclass(frozen=True, slots=True)
class CronSchedule:
    minute: set[int]
    hour: set[int]
    day_of_month: set[int]
    month: set[int]
    day_of_week: set[int]


def _parse_field(field: str, minimum: int, maximum: int) -> set[int]:
    result: set[int] = set()
    for chunk in field.split(","):
        chunk = chunk.strip()
        if not chunk:
            continue
        if chunk == "*":
            result.update(range(minimum, maximum + 1))
            continue
        if chunk.startswith("*/"):
            step = int(chunk[2:])
            result.update(range(minimum, maximum + 1, step))
            continue
        if "-" in chunk:
            start_text, end_text = chunk.split("-", 1)
            result.update(range(int(start_text), int(end_text) + 1))
            continue
        result.add(int(chunk))
    if not result:
        raise ValueError("Empty cron field")
    if min(result) < minimum or max(result) > maximum:
        raise ValueError(f"Cron field out of range: {field}")
    return result


def parse_cron_expr(expr: str) -> CronSchedule:
    fields = expr.split()
    if len(fields) != 5:
        raise ValueError("Cron expression must contain 5 fields")
    return CronSchedule(
        minute=_parse_field(fields[0], 0, 59),
        hour=_parse_field(fields[1], 0, 23),
        day_of_month=_parse_field(fields[2], 1, 31),
        month=_parse_field(fields[3], 1, 12),
        day_of_week=_parse_field(fields[4], 0, 6),
    )


def _cron_weekday(value: datetime) -> int:
    return (value.isoweekday()) % 7


def matches_datetime(schedule: CronSchedule, value: datetime) -> bool:
    return (
        value.minute in schedule.minute
        and value.hour in schedule.hour
        and value.day in schedule.day_of_month
        and value.month in schedule.month
        and _cron_weekday(value) in schedule.day_of_week
    )


def compute_next_run(expr: str, *, timezone_name: str, after: datetime | None = None) -> datetime:
    zone = ZoneInfo(timezone_name)
    base = after.astimezone(zone) if after else datetime.now(zone)
    candidate = base.replace(second=0, microsecond=0) + timedelta(minutes=1)
    schedule = parse_cron_expr(expr)

    for _ in range(60 * 24 * 370):
        if matches_datetime(schedule, candidate):
            return candidate.astimezone(UTC)
        candidate += timedelta(minutes=1)
    raise ValueError(f"Could not compute next run for cron: {expr}")
