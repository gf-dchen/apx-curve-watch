"""The poll loop: fetch the live PRE book, snapshot EVERY hour of today, diff
each against the last stored snapshot, announce whatever moved, and archive --
unattended.

The whole day is watched, not just the operating hour: an edit to HE20 made at
14:00 is news at 14:00, not six hours later when HE20 finally becomes current.
One tick's changes go out as a single announcement, since one re-submission
routinely rewrites a block of hours at once."""

from __future__ import annotations

import logging
import time
from datetime import date, datetime
from pathlib import Path

from gfem.data.ercot.lib.tz import ERCOT_TZ
from gfem.foundry.bidding import apx_bids

from apx_curve_watch.alert import announce
from apx_curve_watch.config import WatchConfig
from apx_curve_watch.diff import HourChange, diff_snapshots
from apx_curve_watch.next_day_check import NextDayBidCheck
from apx_curve_watch.snapshot import ladder_snapshot
from apx_curve_watch.store import CurveStore, Snapshot

logger = logging.getLogger("apx_curve_watch")

ALL_HOURS = tuple(range(1, 25))


def current_operating_hour(now: datetime | None = None) -> tuple[date, int]:
    """``(fordate, hour-ending)`` for ``now`` (default: right now), in ERCOT local
    time. Hour-ending is 1..24: 14:05 CT falls in HE15, the interval dispatching
    right now."""
    local = (now or datetime.now(ERCOT_TZ)).astimezone(ERCOT_TZ)
    return local.date(), local.hour + 1


def poll_once(config: WatchConfig, store: CurveStore) -> None:
    fordate, current_he = current_operating_hour()
    bidset = apx_bids.fetch_bidset(fordate, config.participant, market_status="PRE", env=config.env)
    if bidset is None:
        logger.warning("no bidset for %s (fetch failed, or nothing on file yet)", fordate)
        return

    observed_at = datetime.now(ERCOT_TZ)
    changes: list[HourChange] = []
    for he in ALL_HOURS:
        ladders = ladder_snapshot(bidset, he, config.resources)
        previous = store.load_latest(fordate, he)
        if previous is None:
            # Never tracked this hour before (a fresh day, or a fresh install
            # mid-day): there's nothing to diff against yet, so this poll just
            # establishes the baseline rather than announcing every existing
            # point as a false-positive "change".
            store.save(Snapshot(fordate, he, observed_at, ladders))
            continue
        # An hour previously stored as genuinely empty ({}) still diffs
        # normally: a resource newly appearing there IS a real change.
        diffs = diff_snapshots(previous, ladders)
        if diffs:
            changes.append(HourChange(he=he, diffs=diffs, ladders=ladders))
            # Archived only when it moves -- the store is a change log, so an
            # unchanged hour must not write a snapshot per tick (24 hours x
            # every tick would bury the real history).
            store.save(Snapshot(fordate, he, observed_at, ladders))

    announce(
        fordate,
        changes,
        bidset=bidset,
        resources=config.resources,
        current_he=current_he,
        teams_webhook_url=config.teams_webhook_url,
    )


def run(config: WatchConfig) -> None:
    store = CurveStore(Path(config.storage_dir))
    next_day_check = NextDayBidCheck(config.next_day_check_times)
    logger.info(
        "apx-curve-watch starting: participant=%s env=%s poll=%ss resources=%s "
        "next_day_check_times=%s",
        config.participant,
        config.env,
        config.poll_seconds,
        config.resources or "(all)",
        [t.strftime("%H:%M") for t in config.next_day_check_times] or "(none)",
    )
    while True:
        try:
            poll_once(config, store)
        except Exception:
            logger.exception("poll failed; will retry next tick")
        try:
            next_day_check.maybe_run(config, datetime.now(ERCOT_TZ))
        except Exception:
            logger.exception("next-day bid check failed; will retry next tick")
        time.sleep(config.poll_seconds)
