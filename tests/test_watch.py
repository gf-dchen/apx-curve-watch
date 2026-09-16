from datetime import date, datetime

from gfem.data.ercot.lib.tz import ERCOT_TZ
from gfem.foundry.bidding.apx_bids import BidSet, OfferCurve

from apx_curve_watch import watch
from apx_curve_watch.store import CurveStore, Snapshot
from apx_curve_watch.watch import current_operating_hour, poll_once


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


def _config(**overrides):
    from apx_curve_watch.config import WatchConfig

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


def test_first_observation_of_an_hour_does_not_announce(monkeypatch, tmp_path):
    monkeypatch.setattr(watch, "current_operating_hour", lambda: (date(2026, 9, 13), 16))
    bidset = _bidset(OfferCurve("SAH_ESR1", 16, [(150.0, 50.0)], "Slope", "Accepted"))
    monkeypatch.setattr(watch.apx_bids, "fetch_bidset", lambda *a, **k: bidset)

    calls = []
    monkeypatch.setattr(watch, "announce", lambda *a, **k: calls.append((a, k)))

    store = CurveStore(tmp_path)
    poll_once(_config(), store)

    assert calls == []  # no baseline existed yet -- must not announce
    assert store.load_latest(date(2026, 9, 13), 16) == {"SAH_ESR1": [[150.0, 50.0]]}


def test_second_poll_diffs_against_the_stored_baseline(monkeypatch, tmp_path):
    monkeypatch.setattr(watch, "current_operating_hour", lambda: (date(2026, 9, 13), 16))
    calls = []
    monkeypatch.setattr(watch, "announce", lambda *a, **k: calls.append((a, k)))
    store = CurveStore(tmp_path)

    first = _bidset(OfferCurve("SAH_ESR1", 16, [(150.0, 50.0)], "Slope", "Accepted"))
    monkeypatch.setattr(watch.apx_bids, "fetch_bidset", lambda *a, **k: first)
    poll_once(_config(), store)
    assert calls == []  # first observation

    second = _bidset(OfferCurve("SAH_ESR1", 16, [(150.0, 60.0)], "Slope", "Accepted"))
    monkeypatch.setattr(watch.apx_bids, "fetch_bidset", lambda *a, **k: second)
    poll_once(_config(), store)
    assert len(calls) == 1  # real change against the now-existing baseline


def test_a_previously_stored_empty_hour_still_diffs_normally(monkeypatch, tmp_path):
    monkeypatch.setattr(watch, "current_operating_hour", lambda: (date(2026, 9, 13), 16))
    store = CurveStore(tmp_path)
    store.save(
        Snapshot(fordate=date(2026, 9, 13), he=16, observed_at=datetime.now(ERCOT_TZ), ladders={})
    )

    calls = []
    monkeypatch.setattr(watch, "announce", lambda *a, **k: calls.append((a, k)))
    bidset = _bidset(OfferCurve("SAH_ESR1", 16, [(150.0, 50.0)], "Slope", "Accepted"))
    monkeypatch.setattr(watch.apx_bids, "fetch_bidset", lambda *a, **k: bidset)

    poll_once(_config(), store)
    assert len(calls) == 1  # a resource newly appearing after a real {} baseline IS a change
