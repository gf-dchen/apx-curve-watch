"""Announce the newly-current hour's schedule right when the operating hour
rolls over -- e.g. rolling into HE22 announces HE22 itself, not HE23.

Reuses whichever ``BidSet`` the caller already fetched this tick -- a single
``fetch_bidset`` call returns the whole day, so that hour's curve is already
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

        ladders = ladder_snapshot(bidset, he, config.resources)
        announce_hour(fordate, he, ladders, "new hour", teams_webhook_url=config.teams_webhook_url)
