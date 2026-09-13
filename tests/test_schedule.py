from datetime import time

from apx_curve_watch.schedule import parse_check_times


def test_parses_multiple_single_times_in_order():
    assert parse_check_times("08:15,08:00") == (time(8, 0), time(8, 15))


def test_empty_string_is_no_checks():
    assert parse_check_times("") == ()


def test_tolerates_stray_whitespace():
    assert parse_check_times(" 08:00 , 08:15 ") == (time(8, 0), time(8, 15))


def test_duplicate_times_collapse():
    assert parse_check_times("08:00,08:00") == (time(8, 0),)


def test_window_expands_at_the_given_interval_inclusive_of_both_ends():
    assert parse_check_times("08:30-09:00:15") == (time(8, 30), time(8, 45), time(9, 0))


def test_window_with_a_non_dividing_interval_stops_before_overshooting_the_end():
    assert parse_check_times("08:00-08:20:7") == (time(8, 0), time(8, 7), time(8, 14))


def test_adjoining_windows_dedupe_their_shared_boundary():
    result = parse_check_times("08:30-09:00:15,09:00-09:30:10")
    assert result == (
        time(8, 30),
        time(8, 45),
        time(9, 0),
        time(9, 10),
        time(9, 20),
        time(9, 30),
    )


def test_windows_and_single_times_combine_in_one_spec():
    result = parse_check_times("07:00,08:30-09:00:15")
    assert result == (time(7, 0), time(8, 30), time(8, 45), time(9, 0))


def test_the_three_deadline_windows_daniel_asked_for():
    result = parse_check_times("08:30-09:00:15,09:00-09:30:10,09:30-10:00:5")
    assert result[0] == time(8, 30)
    assert result[-1] == time(10, 0)
    assert time(8, 45) in result  # every 15 min in the first window
    assert time(9, 10) in result  # every 10 min in the second window
    assert time(9, 35) in result  # every 5 min in the third window
