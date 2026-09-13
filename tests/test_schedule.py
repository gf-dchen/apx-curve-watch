from datetime import time

from apx_curve_watch.schedule import parse_check_times


def test_parses_multiple_times_in_order():
    assert parse_check_times("08:15,08:00") == (time(8, 0), time(8, 15))


def test_empty_string_is_no_checks():
    assert parse_check_times("") == ()


def test_tolerates_stray_whitespace():
    assert parse_check_times(" 08:00 , 08:15 ") == (time(8, 0), time(8, 15))


def test_duplicate_times_collapse():
    assert parse_check_times("08:00,08:00") == (time(8, 0),)
