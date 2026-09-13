from datetime import datetime

from gfem.data.ercot.lib.tz import ERCOT_TZ

from apx_curve_watch.watch import current_operating_hour


def test_he_is_hour_plus_one():
    now = datetime(2026, 9, 13, 14, 5, tzinfo=ERCOT_TZ)
    fordate, he = current_operating_hour(now)
    assert fordate == now.date()
    assert he == 15


def test_top_of_hour_is_still_that_hours_he():
    now = datetime(2026, 9, 13, 14, 0, tzinfo=ERCOT_TZ)
    _, he = current_operating_hour(now)
    assert he == 15


def test_just_before_midnight_is_he24_same_day():
    now = datetime(2026, 9, 13, 23, 30, tzinfo=ERCOT_TZ)
    fordate, he = current_operating_hour(now)
    assert fordate == now.date()
    assert he == 24
