from dataclasses import dataclass
from datetime import UTC, date, datetime, timedelta, tzinfo


@dataclass(frozen=True)
class DateRange:
    start: date
    end: date  # inclusive
    name: str


def _is_num(v: object) -> bool:
    return isinstance(v, (int, float)) and not isinstance(v, bool)


def parse_ts(v: object) -> datetime | None:
    """Epoch ms / epoch s / ISO string -> aware UTC datetime, or None."""
    if _is_num(v):
        try:
            return datetime.fromtimestamp(v / 1000 if v > 1e11 else v, tz=UTC)
        except (OverflowError, OSError, ValueError):
            return None
    if isinstance(v, str) and v:
        try:
            return datetime.fromisoformat(v.replace("Z", "+00:00")).astimezone(UTC)
        except ValueError:
            return None
    return None


def resolve_range(
    *,
    current: bool = False,
    last: bool = False,
    date_from: str | None = None,
    date_to: str | None = None,
    today: date,
) -> DateRange:
    if current:
        start = today.replace(day=1)
        return DateRange(start, today, start.strftime("%Y-%m"))
    if last:
        end = today.replace(day=1) - timedelta(days=1)
        start = end.replace(day=1)
        return DateRange(start, end, start.strftime("%Y-%m"))
    if date_to and not date_from:
        raise ValueError("--to requires --from")
    if not date_from:
        start = today - timedelta(days=29)
        return DateRange(start, today, f"last30_{today:%Y-%m-%d}")
    start = datetime.strptime(date_from, "%Y-%m-%d").date()
    end = datetime.strptime(date_to, "%Y-%m-%d").date() if date_to else today
    if end < start:
        raise ValueError(f"--to ({end}) is before --from ({start})")
    return DateRange(start, end, f"{start:%Y-%m-%d}_{end:%Y-%m-%d}")


def to_utc_bounds(r: DateRange, tz: tzinfo | None = None) -> tuple[datetime, datetime]:
    """Inclusive local dates -> [since, until) in UTC. tz=None means the system zone."""

    def midnight(d: date) -> datetime:
        dt = datetime(d.year, d.month, d.day, tzinfo=tz)
        return (dt if tz else dt.astimezone()).astimezone(UTC)

    return midnight(r.start), midnight(r.end + timedelta(days=1))
