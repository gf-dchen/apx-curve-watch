"""Scheduled checks that tomorrow's energy book has something on file.

Runs at fixed wall-clock times (e.g. 08:00 and 08:15 CT), not on every poll
tick, so a quiet morning gets exactly one nudge per configured time rather than
one every 30 seconds -- ``NextDayBidCheck`` tracks which (date, time) pairs have
already fired.
"""

from __future__ import annotations

import logging
from datetime import date, datetime, time, timedelta

from gfem.foundry.bidding import apx_bids

from apx_curve_watch.alert import announce_missing_bids
from apx_curve_watch.config import WatchConfig

logger = logging.getLogger("apx_curve_watch")


def missing_resources(
    bidset: apx_bids.BidSet | None, resources: tuple[str, ...]
) -> tuple[str, ...]:
    """Which watched ``resources`` have nothing on file in ``bidset``.

    With no resources configured (watch-everything mode) there's no per-resource
    expectation to check against, so this only flags a completely empty book.
    """
    if not resources:
        return () if bidset and bidset.resources else ("(entire book)",)
    return tuple(r for r in resources if not bidset or not bidset.hours(resource=r))


class NextDayBidCheck:
    def __init__(self, check_times: tuple[time, ...]) -> None:
        self.check_times = check_times
        self._fired: set[tuple[date, time]] = set()

    def maybe_run(self, config: WatchConfig, now: datetime) -> None:
        for check_time in self.check_times:
            key = (now.date(), check_time)
            if now.time() < check_time or key in self._fired:
                continue
            self._fired.add(key)
            self._check(config, now, check_time)

    def _check(self, config: WatchConfig, now: datetime, check_time: time) -> None:
        tomorrow = now.date() + timedelta(days=1)
        bidset = apx_bids.fetch_bidset(
            tomorrow, config.participant, market_status="PRE", env=config.env
        )
        missing = missing_resources(bidset, config.resources)
        announce_missing_bids(
            check_time.strftime("%H:%M"),
            tomorrow,
            missing,
            teams_webhook_url=config.teams_webhook_url,
        )
