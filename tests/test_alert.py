from datetime import date

from gfem.foundry.bidding.apx_bids import BidSet, OfferCurve

from apx_curve_watch import alert
from apx_curve_watch.alert import announce, render, render_missing_bids
from apx_curve_watch.diff import HourChange, diff_snapshots

WEBHOOK = "https://example.invalid/webhook"


def _bidset(*curves: OfferCurve) -> BidSet:
    return BidSet(fordate=date(2026, 9, 13), market_status="PRE", curves=list(curves))


def _change(he: int, old: dict, new: dict) -> HourChange:
    return HourChange(he=he, diffs=diff_snapshots(old, new), ladders=new)


def test_render_prints_the_new_schedule_not_the_delta():
    old = {"SAH_ESR1": [[-200.0, 25.0]]}
    new = {"SAH_ESR1": [[-200.0, 27.0], [-50.0, 40.0]]}
    message = render(date(2026, 9, 13), [_change(9, old, new)])
    assert "-200.000 MW @    27.0000" in message
    assert " -50.000 MW @    40.0000" in message
    assert "moved" not in message
    assert "added" not in message


def test_unchanged_resource_is_not_in_the_message():
    old = {"SAH_ESR1": [[-200.0, 25.0]], "SAH_ESR2": [[-200.0, 25.0]]}
    new = {"SAH_ESR1": [[-200.0, 27.0]], "SAH_ESR2": [[-200.0, 25.0]]}
    message = render(date(2026, 9, 13), [_change(9, old, new)])
    assert "SAH_ESR1" in message
    assert "SAH_ESR2" not in message


def test_every_hour_that_moved_is_named_once_in_one_message():
    old = {"SAH_ESR1": [[100.0, 50.0]]}
    new = {"SAH_ESR1": [[200.0, 50.0]]}
    message = render(date(2026, 9, 13), [_change(15, old, new), _change(16, old, new)])
    assert message.splitlines()[0] == "[2026-09-13] bid curve changed -- HE15, HE16:"
    assert "  HE15 SAH_ESR1:" in message
    assert "  HE16 SAH_ESR1:" in message


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
    announce(date(2026, 9, 13), [_change(9, old, new)], teams_webhook_url=WEBHOOK)
    [(url, (text, title))] = calls
    assert url == WEBHOOK
    assert text == render(date(2026, 9, 13), [_change(9, old, new)])
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
        [_change(17, old, new)],
        bidset=bidset,
        current_he=17,
        teams_webhook_url=WEBHOOK,
    )
    [(url, (text, title))] = calls
    assert url == WEBHOOK
    assert "HE20" in text  # rest-of-day, not just HE17
    assert "150" in text  # MW rounded to a whole number for Teams
    assert "$50.00" in text  # price keeps decimals, gets a $ prefix
    assert "Total" not in text  # Teams table drops the Total column
    assert title == "[2026-09-13] bid curve changed -- HE17"


def test_the_table_starts_at_the_earliest_hour_that_moved(monkeypatch):
    # An edit to HE20 seen during HE17 is read against the rest of the day, so
    # the table still opens at the current hour rather than at the change.
    calls = []
    monkeypatch.setattr(alert.teams, "post_card", lambda url, card: calls.append((url, card)))
    monkeypatch.setattr(alert.teams_codeblock, "build_card", lambda text, title="": (text, title))

    bidset = _bidset(
        OfferCurve("SAH_ESR1", 17, [(-200.0, 27.0)], "Slope", "Accepted"),
        OfferCurve("SAH_ESR1", 20, [(150.0, 50.0)], "Slope", "Accepted"),
    )
    old = {"SAH_ESR1": [[100.0, 50.0]]}
    new = {"SAH_ESR1": [[150.0, 50.0]]}
    announce(
        date(2026, 9, 13),
        [_change(20, old, new)],
        bidset=bidset,
        current_he=17,
        teams_webhook_url=WEBHOOK,
    )
    [(_url, (text, title))] = calls
    assert "HE17" in text
    assert title == "[2026-09-13] bid curve changed -- HE20"


def test_a_change_behind_the_current_hour_still_shows_its_own_hour(monkeypatch):
    calls = []
    monkeypatch.setattr(alert.teams, "post_card", lambda url, card: calls.append((url, card)))
    monkeypatch.setattr(alert.teams_codeblock, "build_card", lambda text, title="": (text, title))

    bidset = _bidset(OfferCurve("SAH_ESR1", 9, [(-200.0, 27.0)], "Slope", "Accepted"))
    old = {"SAH_ESR1": [[-100.0, 25.0]]}
    new = {"SAH_ESR1": [[-200.0, 27.0]]}
    announce(
        date(2026, 9, 13),
        [_change(9, old, new)],
        bidset=bidset,
        current_he=17,
        teams_webhook_url=WEBHOOK,
    )
    [(_url, (text, _title))] = calls
    assert "HE09" in text  # table opens at the change, not at HE17


def test_announce_does_not_touch_teams_without_a_webhook_url(monkeypatch):
    calls = []
    monkeypatch.setattr(alert.teams, "post_card", lambda *a, **k: calls.append((a, k)))

    old = {"SAH_ESR1": [[-200.0, 25.0]]}
    new = {"SAH_ESR1": [[-200.0, 27.0]]}
    announce(date(2026, 9, 13), [_change(9, old, new)], teams_webhook_url=None)
    assert calls == []


def test_a_tick_with_nothing_moving_announces_nothing(monkeypatch):
    calls = []
    monkeypatch.setattr(alert.teams, "post_card", lambda *a, **k: calls.append((a, k)))
    announce(date(2026, 9, 13), [], teams_webhook_url=WEBHOOK)
    assert calls == []


def test_bid_review_puts_the_header_on_the_card_not_inside_the_code_block(monkeypatch):
    from apx_curve_watch.bid_review import Finding

    calls = []
    monkeypatch.setattr(alert.teams, "post_card", lambda url, card: calls.append((url, card)))
    monkeypatch.setattr(alert.teams_codeblock, "build_card", lambda text, title="": (text, title))

    finding = Finding("charge-block", "charge HE09-HE13: 600 MWh site-wide", ["HE09 -200"])
    alert.announce_bid_review(
        "08:30", date(2026, 9, 14), [finding], teams_webhook_url="https://example/hook"
    )

    (_url, (text, title)) = calls[0]
    assert title == "[08:30 CT check] 2026-09-14 day-ahead bid looks wrong (1 check failed)"
    assert text == "charge HE09-HE13: 600 MWh site-wide\n  HE09 -200"


def test_a_clean_review_says_nothing(monkeypatch):
    calls = []
    monkeypatch.setattr(alert.teams, "post_card", lambda url, card: calls.append((url, card)))
    alert.announce_bid_review(
        "08:30", date(2026, 9, 14), [], teams_webhook_url="https://example/hook"
    )
    assert calls == []
