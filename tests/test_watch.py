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


def _announced(monkeypatch):
    """Capture the changes list handed to ``announce`` on each tick."""
    ticks = []
    monkeypatch.setattr(watch, "announce", lambda fordate, changes, **k: ticks.append(changes))
    return ticks


def test_first_observation_of_an_hour_does_not_announce(monkeypatch, tmp_path):
    monkeypatch.setattr(watch, "current_operating_hour", lambda: (date(2026, 9, 13), 16))
    bidset = _bidset(OfferCurve("SAH_ESR1", 16, [(150.0, 50.0)], "Slope", "Accepted"))
    monkeypatch.setattr(watch.apx_bids, "fetch_bidset", lambda *a, **k: bidset)
    ticks = _announced(monkeypatch)

    store = CurveStore(tmp_path)
    poll_once(_config(), store)

    assert ticks == [[]]  # no baseline existed yet -- must not announce
    assert store.load_latest(date(2026, 9, 13), 16) == {"SAH_ESR1": [[150.0, 50.0]]}


def test_second_poll_diffs_against_the_stored_baseline(monkeypatch, tmp_path):
    monkeypatch.setattr(watch, "current_operating_hour", lambda: (date(2026, 9, 13), 16))
    ticks = _announced(monkeypatch)
    store = CurveStore(tmp_path)

    first = _bidset(OfferCurve("SAH_ESR1", 16, [(150.0, 50.0)], "Slope", "Accepted"))
    monkeypatch.setattr(watch.apx_bids, "fetch_bidset", lambda *a, **k: first)
    poll_once(_config(), store)
    assert ticks[-1] == []  # first observation

    second = _bidset(OfferCurve("SAH_ESR1", 16, [(150.0, 60.0)], "Slope", "Accepted"))
    monkeypatch.setattr(watch.apx_bids, "fetch_bidset", lambda *a, **k: second)
    poll_once(_config(), store)
    [change] = ticks[-1]  # real change against the now-existing baseline
    assert change.he == 16
    assert change.ladders == {"SAH_ESR1": [[150.0, 60.0]]}


def test_a_previously_stored_empty_hour_still_diffs_normally(monkeypatch, tmp_path):
    monkeypatch.setattr(watch, "current_operating_hour", lambda: (date(2026, 9, 13), 16))
    store = CurveStore(tmp_path)
    store.save(
        Snapshot(fordate=date(2026, 9, 13), he=16, observed_at=datetime.now(ERCOT_TZ), ladders={})
    )

    ticks = _announced(monkeypatch)
    bidset = _bidset(OfferCurve("SAH_ESR1", 16, [(150.0, 50.0)], "Slope", "Accepted"))
    monkeypatch.setattr(watch.apx_bids, "fetch_bidset", lambda *a, **k: bidset)

    poll_once(_config(), store)
    # a resource newly appearing after a real {} baseline IS a change
    assert [c.he for c in ticks[-1]] == [16]


def test_an_edit_to_a_later_hour_is_news_now_not_when_that_hour_arrives(monkeypatch, tmp_path):
    monkeypatch.setattr(watch, "current_operating_hour", lambda: (date(2026, 9, 13), 14))
    ticks = _announced(monkeypatch)
    store = CurveStore(tmp_path)

    first = _bidset(OfferCurve("SAH_ESR1", 20, [(0.0, 50.0), (100.0, 50.0)], "Slope", "Accepted"))
    monkeypatch.setattr(watch.apx_bids, "fetch_bidset", lambda *a, **k: first)
    poll_once(_config(), store)

    second = _bidset(OfferCurve("SAH_ESR1", 20, [(0.0, 50.0), (200.0, 50.0)], "Slope", "Accepted"))
    monkeypatch.setattr(watch.apx_bids, "fetch_bidset", lambda *a, **k: second)
    poll_once(_config(), store)

    assert [c.he for c in ticks[-1]] == [20]  # six hours before HE20 is current


def test_a_block_rewrite_is_one_announcement_naming_every_hour(monkeypatch, tmp_path):
    monkeypatch.setattr(watch, "current_operating_hour", lambda: (date(2026, 9, 13), 14))
    ticks = _announced(monkeypatch)
    store = CurveStore(tmp_path)

    def book(price):
        return _bidset(
            *(
                OfferCurve("SAH_ESR1", he, [(0.0, price), (200.0, price)], "Slope", "Accepted")
                for he in (15, 16, 17)
            )
        )

    monkeypatch.setattr(watch.apx_bids, "fetch_bidset", lambda *a, **k: book(50.0))
    poll_once(_config(), store)
    monkeypatch.setattr(watch.apx_bids, "fetch_bidset", lambda *a, **k: book(80.0))
    poll_once(_config(), store)

    assert len(ticks) == 2  # one announcement per tick, not one per hour
    assert [c.he for c in ticks[-1]] == [15, 16, 17]


def test_an_unchanged_hour_is_not_archived_again_every_tick(monkeypatch, tmp_path):
    # 24 hours x every tick would bury the real history -- the store is a change
    # log, so a quiet hour keeps exactly its baseline snapshot.
    monkeypatch.setattr(watch, "current_operating_hour", lambda: (date(2026, 9, 13), 16))
    _announced(monkeypatch)
    bidset = _bidset(OfferCurve("SAH_ESR1", 16, [(150.0, 50.0)], "Slope", "Accepted"))
    monkeypatch.setattr(watch.apx_bids, "fetch_bidset", lambda *a, **k: bidset)

    store = CurveStore(tmp_path)
    for _ in range(5):
        poll_once(_config(), store)

    archived = sorted(p.name for p in (tmp_path / "2026-09-13" / "HH16").glob("*.json"))
    assert len(archived) == 2  # the baseline snapshot + latest.json, nothing more
