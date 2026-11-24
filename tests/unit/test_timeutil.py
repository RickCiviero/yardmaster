from datetime import UTC, date, datetime
from zoneinfo import ZoneInfo

import pytest
from yardmaster.timeutil import DateRange, parse_ts, resolve_range, to_utc_bounds

TODAY = date(2026, 11, 23)


def test_parse_ts_ms_s_iso_bool():
    want = datetime(2026, 11, 23, 12, 0, tzinfo=UTC)
    assert parse_ts(int(want.timestamp() * 1000)) == want
    assert parse_ts(int(want.timestamp())) == want
    assert parse_ts("2026-11-23T12:00:00Z") == want
    assert parse_ts("2026-11-23T14:00:00+02:00") == want
    assert parse_ts(True) is None
    assert parse_ts("not a date") is None
    assert parse_ts(None) is None
    assert parse_ts([1]) is None


def test_resolve_current_last_from_default():
    assert resolve_range(current=True, today=TODAY) == DateRange(
        date(2026, 11, 1), date(2026, 11, 23), "2026-11"
    )
    assert resolve_range(last=True, today=TODAY) == DateRange(
        date(2026, 10, 1), date(2026, 10, 31), "2026-10"
    )
    assert resolve_range(date_from="2026-09-04", date_to="2026-09-22", today=TODAY) == DateRange(
        date(2026, 9, 4), date(2026, 9, 22), "2026-09-04_2026-09-22"
    )
    assert resolve_range(date_from="2026-09-04", today=TODAY).end == TODAY
    assert resolve_range(today=TODAY) == DateRange(
        date(2026, 10, 25), date(2026, 11, 23), "last30_2026-11-23"
    )


def test_resolve_last_in_january_crosses_year():
    r = resolve_range(last=True, today=date(2027, 1, 15))
    assert (r.start, r.end, r.name) == (date(2026, 12, 1), date(2026, 12, 31), "2026-12")


def test_resolve_errors():
    with pytest.raises(ValueError):
        resolve_range(date_from="2026-09-22", date_to="2026-09-04", today=TODAY)
    with pytest.raises(ValueError):
        resolve_range(date_to="2026-09-04", today=TODAY)
    with pytest.raises(ValueError):
        resolve_range(date_from="2026-13-40", today=TODAY)


def test_utc_bounds_dst_and_midnight():
    tz = ZoneInfo("Europe/Madrid")
    r = DateRange(date(2026, 10, 25), date(2026, 10, 25), "x")  # DST ends: a 25-hour day
    since, until = to_utc_bounds(r, tz)
    assert since == datetime(2026, 10, 24, 22, 0, tzinfo=UTC)
    assert until == datetime(2026, 10, 25, 23, 0, tzinfo=UTC)
    inside = datetime(2026, 10, 25, 22, 59, 59, tzinfo=UTC)
    outside = datetime(2026, 10, 25, 23, 0, 0, tzinfo=UTC)
    assert since <= inside < until
    assert not (since <= outside < until)


def test_utc_bounds_default_local_zone_is_utc_aware():
    since, until = to_utc_bounds(DateRange(date(2026, 11, 1), date(2026, 11, 1), "x"))
    assert since.tzinfo is not None and until - since in (
        datetime(2026, 11, 2, tzinfo=UTC) - datetime(2026, 11, 1, tzinfo=UTC),
    )

