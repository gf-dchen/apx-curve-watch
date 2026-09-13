"""Announce the upcoming hour's schedule right when the operating hour rolls over.

Reuses whichever ``BidSet`` the caller already fetched this tick -- a single
``fetch_bidset`` call returns the whole day, so the next hour's curve is already
in hand and this needs no extra APX round-trip.
"""

from __future__ import annotations

from datetime import date

from gfem.foundry.bidding import apx_bids

from apx_curve_watch.alert import announce_hour
from apx_curve_watch.config import WatchConfig
from apx_curve_watch.snapshot import ladder_snapshot


class HourRolloverAnnouncer:
    def __init__(self) -> None:
        self._last_he: tuple[date, int] | None = None

    def maybe_run(
        self, config: WatchConfig, bidset: apx_bids.BidSet, fordate: date, he: int
    ) -> None:
        current = (fordate, he)
        is_first_tick = self._last_he is None
        rolled_over = not is_first_tick and self._last_he != current
        self._last_he = current
        if not rolled_over:
            return

        next_he = he + 1
        if next_he > 24:  # next hour is tomorrow's HE1, a different operating day
            return
        ladders = ladder_snapshot(bidset, next_he, config.resources)
        announce_hour(
            fordate, next_he, ladders, "next hour", teams_webhook_url=config.teams_webhook_url
        )
