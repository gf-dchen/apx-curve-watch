"""The poll loop: fetch the live PRE book, snapshot the current operating hour,
diff it against the last stored snapshot, announce, and archive -- unattended."""

from __future__ import annotations

import logging
import time
from datetime import date, datetime
from pathlib import Path

from gfem.data.ercot.lib.tz import ERCOT_TZ
from gfem.foundry.bidding import apx_bids

from apx_curve_watch.alert import announce
from apx_curve_watch.config import WatchConfig
from apx_curve_watch.diff import diff_snapshots
from apx_curve_watch.hour_rollover import HourRolloverAnnouncer
from apx_curve_watch.next_day_check import NextDayBidCheck
from apx_curve_watch.snapshot import ladder_snapshot
from apx_curve_watch.store import CurveStore, Snapshot

logger = logging.getLogger("apx_curve_watch")


def current_operating_hour(now: datetime | None = None) -> tuple[date, int]:
    """``(fordate, hour-ending)`` for ``now`` (default: right now), in ERCOT local
    time. Hour-ending is 1..24: 14:05 CT falls in HE15, the interval dispatching
    right now."""
    local = (now or datetime.now(ERCOT_TZ)).astimezone(ERCOT_TZ)
    return local.date(), local.hour + 1


def poll_once(config: WatchConfig, store: CurveStore, rollover: HourRolloverAnnouncer) -> None:
    fordate, he = current_operating_hour()
    bidset = apx_bids.fetch_bidset(fordate, config.participant, market_status="PRE", env=config.env)
    if bidset is None:
        logger.warning("no bidset for %s (fetch failed, or nothing on file yet)", fordate)
        return

    new_ladders = ladder_snapshot(bidset, he, config.resources)
    old_ladders = store.load_latest(fordate, he) or {}
    announce(
        fordate,
        he,
        diff_snapshots(old_ladders, new_ladders),
        new_ladders,
        bidset=bidset,
        resources=config.resources,
        teams_webhook_url=config.teams_webhook_url,
    )
    store.save(
        Snapshot(fordate=fordate, he=he, observed_at=datetime.now(ERCOT_TZ), ladders=new_ladders)
    )
    rollover.maybe_run(config, bidset, fordate, he)


def run(config: WatchConfig) -> None:
    store = CurveStore(Path(config.storage_dir))
    next_day_check = NextDayBidCheck(config.next_day_check_times)
    rollover = HourRolloverAnnouncer()
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
            poll_once(config, store, rollover)
        except Exception:
            logger.exception("poll failed; will retry next tick")
        try:
            next_day_check.maybe_run(config, datetime.now(ERCOT_TZ))
        except Exception:
            logger.exception("next-day bid check failed; will retry next tick")
        time.sleep(config.poll_seconds)
