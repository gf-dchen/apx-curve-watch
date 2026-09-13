from datetime import UTC, date, datetime

from apx_curve_watch.store import CurveStore, Snapshot


def test_load_latest_is_none_before_anything_saved(tmp_path):
    store = CurveStore(tmp_path)
    assert store.load_latest(date(2026, 9, 13), 15) is None


def test_save_then_load_latest_round_trips(tmp_path):
    store = CurveStore(tmp_path)
    ladders = {"SOHO_BESS1": [[100.0, 20.0], [200.0, 50.0]]}
    store.save(
        Snapshot(
            fordate=date(2026, 9, 13),
            he=15,
            observed_at=datetime(2026, 9, 13, 15, 3, tzinfo=UTC),
            ladders=ladders,
        )
    )
    assert store.load_latest(date(2026, 9, 13), 15) == ladders


def test_second_save_overwrites_latest_but_keeps_history(tmp_path):
    store = CurveStore(tmp_path)
    fordate, he = date(2026, 9, 13), 15
    store.save(Snapshot(fordate, he, datetime(2026, 9, 13, 15, 1, tzinfo=UTC), {"R": [[1.0, 2.0]]}))
    store.save(Snapshot(fordate, he, datetime(2026, 9, 13, 15, 2, tzinfo=UTC), {"R": [[3.0, 4.0]]}))
    assert store.load_latest(fordate, he) == {"R": [[3.0, 4.0]]}
    hour_dir = store._hour_dir(fordate, he)
    archived = sorted(p.name for p in hour_dir.glob("*.json") if p.name != "latest.json")
    assert len(archived) == 2


def test_unreadable_snapshot_treated_as_absent(tmp_path):
    store = CurveStore(tmp_path)
    latest = store.latest_path(date(2026, 9, 13), 15)
    latest.parent.mkdir(parents=True)
    latest.write_text("not json")
    assert store.load_latest(date(2026, 9, 13), 15) is None


def test_different_hours_do_not_collide(tmp_path):
    store = CurveStore(tmp_path)
    fordate = date(2026, 9, 13)
    store.save(Snapshot(fordate, 15, datetime(2026, 9, 13, 15, 0, tzinfo=UTC), {"R": [[1.0, 2.0]]}))
    store.save(Snapshot(fordate, 16, datetime(2026, 9, 13, 16, 0, tzinfo=UTC), {"R": [[9.0, 9.0]]}))
    assert store.load_latest(fordate, 15) == {"R": [[1.0, 2.0]]}
    assert store.load_latest(fordate, 16) == {"R": [[9.0, 9.0]]}
