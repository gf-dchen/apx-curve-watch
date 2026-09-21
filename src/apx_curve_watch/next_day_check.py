"""Scheduled checks on tomorrow's book: is it there, and does it look right?

Runs at fixed wall-clock times (e.g. 08:30 and 09:00 CT), not on every poll
tick, so a quiet morning gets exactly one nudge per configured time rather than
one every 30 seconds -- ``NextDayBidCheck`` tracks which (date, time) pairs have
already fired.

Two announcements come out of one fetch, in escalating order: nothing on file at
all (``announce_missing_bids``), or a book that is on file but fails a desk rule
(``announce_bid_review``, rules in ``bid_review``). A book that's there and looks
right says nothing.
"""

from __future__ import annotations

import logging
from datetime import date, datetime, time, timedelta

from gfem.foundry.bidding import apx_bids

from apx_curve_watch.alert import announce_bid_review, announce_missing_bids
from apx_curve_watch.bid_review import review
from apx_curve_watch.config import WatchConfig
from apx_curve_watch.day_book import fetch_day_book

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
        """Runs at most one real check per call, even if several configured
        times are newly due at once (e.g. the process starts mid-morning,
        well past most of the schedule) -- otherwise a late start fires one
        near-identical fetch and announcement per already-passed time, back
        to back, instead of a single catch-up check."""
        today = now.date()
        due = [t for t in self.check_times if now.time() >= t and (today, t) not in self._fired]
        if not due:
            return
        for check_time in due:
            self._fired.add((today, check_time))
        self._check(config, now, due[-1])

    def _check(self, config: WatchConfig, now: datetime, check_time: time) -> None:
        tomorrow = now.date() + timedelta(days=1)
        label = check_time.strftime("%H:%M")
        book = fetch_day_book(tomorrow, config.participant, env=config.env)
        missing = missing_resources(book.bidset if book else None, config.resources)
        announce_missing_bids(label, tomorrow, missing, teams_webhook_url=config.teams_webhook_url)
        if book is None or missing:
            # A fetch failure, or a resource with nothing on file at all: the
            # nudge above already covers it, and reviewing a book that isn't
            # there just restates the same gap once per rule (an absent ESR
            # would fail the symmetry rule in all 24 hours).
            return
        announce_bid_review(
            label,
            tomorrow,
            review(
                book,
                config.resources,
                charge_block_hours=config.charge_block_hours,
                charge_block_mwh=config.charge_block_mwh,
                min_discharge_mw=config.min_discharge_mw,
                check_discharge_present=config.check_discharge_present,
                check_as_present=config.check_as_present,
                check_symmetry=config.check_esr_symmetry,
            ),
            teams_webhook_url=config.teams_webhook_url,
        )
