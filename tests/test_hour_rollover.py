from datetime import date

from gfem.foundry.bidding.apx_bids import BidSet, OfferCurve

from apx_curve_watch import hour_rollover as hr
from apx_curve_watch.config import WatchConfig
from apx_curve_watch.hour_rollover import HourRolloverAnnouncer


def _config(**overrides) -> WatchConfig:
    base = dict(
        participant="QGFEN",
        env="prod",
        resources=(),
        poll_seconds=30,
        storage_dir="./curves",
        teams_webhook_url=None,
        next_day_check_times=(),
        log_file="",
    )
    base.update(overrides)
    return WatchConfig(**base)


def _bidset(*curves: OfferCurve) -> BidSet:
    return BidSet(fordate=date(2026, 9, 13), market_status="PRE", curves=list(curves))


def _capture(monkeypatch):
    calls = []
    monkeypatch.setattr(hr, "announce_hour", lambda *a, **k: calls.append((a, k)))
    return calls


def test_first_tick_ever_does_not_announce(monkeypatch):
    calls = _capture(monkeypatch)
    bidset = _bidset(OfferCurve("SAH_ESR1", 16, [(150.0, 50.0)], "Slope", "Accepted"))

    HourRolloverAnnouncer().maybe_run(_config(), bidset, date(2026, 9, 13), 15)
    assert calls == []


def test_same_hour_on_a_later_tick_does_not_announce(monkeypatch):
    calls = _capture(monkeypatch)
    bidset = _bidset(OfferCurve("SAH_ESR1", 16, [(150.0, 50.0)], "Slope", "Accepted"))

    check = HourRolloverAnnouncer()
    check.maybe_run(_config(), bidset, date(2026, 9, 13), 15)
    check.maybe_run(_config(), bidset, date(2026, 9, 13), 15)
    assert calls == []


def test_hour_advancing_announces_the_new_next_hour(monkeypatch):
    calls = _capture(monkeypatch)
    bidset = _bidset(OfferCurve("SAH_ESR1", 17, [(150.0, 50.0)], "Slope", "Accepted"))

    check = HourRolloverAnnouncer()
    check.maybe_run(_config(), bidset, date(2026, 9, 13), 15)  # first tick, no announce
    check.maybe_run(_config(), bidset, date(2026, 9, 13), 16)  # rolled over to HE16
    [(args, kwargs)] = calls
    fordate, he, ladders, label = args
    assert he == 17  # the hour AFTER the one we just rolled into
    assert label == "next hour"
    assert ladders == {"SAH_ESR1": [[150.0, 50.0]]}


def test_he24_rollover_does_not_reach_into_tomorrow(monkeypatch):
    calls = _capture(monkeypatch)
    bidset = _bidset()

    check = HourRolloverAnnouncer()
    check.maybe_run(_config(), bidset, date(2026, 9, 13), 23)
    check.maybe_run(_config(), bidset, date(2026, 9, 13), 24)
    assert calls == []
