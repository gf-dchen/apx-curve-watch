from datetime import date

from gfem.foundry.bidding.apx_bids import BidSet, OfferCurve

from apx_curve_watch import alert
from apx_curve_watch.alert import announce, render, render_missing_bids
from apx_curve_watch.diff import diff_snapshots


def _bidset(*curves: OfferCurve) -> BidSet:
    return BidSet(fordate=date(2026, 9, 13), market_status="PRE", curves=list(curves))


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


def test_announce_without_a_bidset_sends_the_console_message_to_teams(monkeypatch):
    calls = []
    monkeypatch.setattr(alert.teams, "post_card", lambda url, card: calls.append((url, card)))
    monkeypatch.setattr(alert.teams_codeblock, "build_card", lambda text, title="": (text, title))

    old = {"SAH_ESR1": [[-200.0, 25.0]]}
    new = {"SAH_ESR1": [[-200.0, 27.0]]}
    announce(
        date(2026, 9, 13),
        9,
        diff_snapshots(old, new),
        new,
        teams_webhook_url="https://example.invalid/webhook",
    )
    [(url, (text, title))] = calls
    assert url == "https://example.invalid/webhook"
    assert text == render(date(2026, 9, 13), 9, diff_snapshots(old, new), new)
    assert title == ""


def test_announce_with_a_bidset_sends_the_rest_of_day_table_to_teams_instead(monkeypatch):
    calls = []
    monkeypatch.setattr(alert.teams, "post_card", lambda url, card: calls.append((url, card)))
    monkeypatch.setattr(alert.teams_codeblock, "build_card", lambda text, title="": (text, title))

    bidset = _bidset(
        OfferCurve("SAH_ESR1", 17, [(-200.0, 27.0)], "Slope", "Accepted"),
        OfferCurve("SAH_ESR1", 20, [(150.0, 50.0)], "Slope", "Accepted"),
    )
    old = {"SAH_ESR1": [[-200.0, 25.0]]}
    new = {"SAH_ESR1": [[-200.0, 27.0]]}
    announce(
        date(2026, 9, 13),
        17,
        diff_snapshots(old, new),
        new,
        bidset=bidset,
        teams_webhook_url="https://example.invalid/webhook",
    )
    [(url, (text, title))] = calls
    assert url == "https://example.invalid/webhook"
    assert "HE20" in text  # rest-of-day, not just HE17
    assert "150" in text  # MW rounded to a whole number for Teams
    assert "$50.00" in text  # price keeps decimals, gets a $ prefix
    assert "Total" not in text  # Teams table drops the Total column
    assert "bid curve changed -- rest of today" in title


def test_announce_does_not_touch_teams_without_a_webhook_url(monkeypatch):
    calls = []
    monkeypatch.setattr(alert.teams, "post_card", lambda *a, **k: calls.append((a, k)))

    old = {"SAH_ESR1": [[-200.0, 25.0]]}
    new = {"SAH_ESR1": [[-200.0, 27.0]]}
    announce(date(2026, 9, 13), 9, diff_snapshots(old, new), new, teams_webhook_url=None)
    assert calls == []
