from datetime import date

from apx_curve_watch.alert import render, render_hour, render_missing_bids
from apx_curve_watch.diff import diff_snapshots


def test_render_prints_the_new_schedule_not_the_delta():
    old = {"SAH_ESR1": [[-200.0, 25.0]]}
    new = {"SAH_ESR1": [[-200.0, 27.0], [-50.0, 40.0]]}
    diffs = diff_snapshots(old, new)
    message = render(date(2026, 9, 13), 9, diffs, new)
    assert "-200.000 MW @    27.0000" in message
    assert " -50.000 MW @    40.0000" in message
    assert "moved" not in message
    assert "added" not in message


def test_unchanged_resource_is_not_in_the_message():
    old = {"SAH_ESR1": [[-200.0, 25.0]], "SAH_ESR2": [[-200.0, 25.0]]}
    new = {"SAH_ESR1": [[-200.0, 27.0]], "SAH_ESR2": [[-200.0, 25.0]]}
    diffs = diff_snapshots(old, new)
    message = render(date(2026, 9, 13), 9, diffs, new)
    assert "SAH_ESR1" in message
    assert "SAH_ESR2" not in message


def test_render_missing_bids_names_the_check_time_date_and_gaps():
    message = render_missing_bids("08:00", date(2026, 9, 14), ("SAH_ESR1", "SAH_ESR2"))
    assert "08:00" in message
    assert "2026-09-14" in message
    assert "SAH_ESR1" in message
    assert "SAH_ESR2" in message


def test_render_hour_lists_every_resource_with_its_points():
    ladders = {"SAH_ESR1": [[150.0, 50.0]], "SAH_ESR2": [[100.0, 45.0]]}
    message = render_hour(date(2026, 9, 13), 17, ladders, "next hour")
    assert "HE17" in message
    assert "next hour" in message
    assert "SAH_ESR1" in message
    assert "150.000 MW @    50.0000" in message


def test_render_hour_notes_when_a_resource_has_nothing_on_file():
    message = render_hour(date(2026, 9, 13), 17, {"SAH_ESR1": []}, "next hour")
    assert "(no offers on file yet)" in message
