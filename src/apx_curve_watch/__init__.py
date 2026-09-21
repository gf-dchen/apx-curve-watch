"""``apx-curve-watch``: store the current ERCOT operating hour's dispatch schedule
bid curve as APX holds it, and log when any point on it moves."""

from __future__ import annotations

import argparse
import logging
import sys
from datetime import timedelta
from pathlib import Path

from gfem.foundry.bidding import apx_bids

from apx_curve_watch.bid_review import render_review, review, review_header
from apx_curve_watch.config import WatchConfig
from apx_curve_watch.day_book import fetch_day_book
from apx_curve_watch.table import render_table
from apx_curve_watch.watch import current_operating_hour, run

__all__ = ["main"]


def _configure_logging(log_file: str) -> None:
    formatter = logging.Formatter("%(asctime)s %(levelname)s %(message)s")
    console = logging.StreamHandler()
    console.setFormatter(formatter)
    handlers: list[logging.Handler] = [console]

    if log_file:
        Path(log_file).parent.mkdir(parents=True, exist_ok=True)
        file_handler = logging.FileHandler(log_file)
        file_handler.setFormatter(formatter)
        handlers.append(file_handler)

    logging.basicConfig(level=logging.INFO, handlers=handlers, force=True)


def main() -> int:
    parser = argparse.ArgumentParser(prog="apx-curve-watch")
    parser.add_argument(
        "--table",
        action="store_true",
        help="print today's full-day energy ladder as a table and exit, instead of polling",
    )
    parser.add_argument(
        "--review",
        action="store_true",
        help="run the day-ahead reasonability checks against tomorrow's book and exit, "
        "instead of polling -- the same checks the morning schedule runs",
    )
    args = parser.parse_args()

    config = WatchConfig.from_env()
    _configure_logging(config.log_file)
    if not config.participant:
        print("APX_MARKET_PARTICIPANT is not set", file=sys.stderr)
        return 1

    if args.table:
        fordate, _ = current_operating_hour()
        bidset = apx_bids.fetch_bidset(
            fordate, config.participant, market_status="PRE", env=config.env
        )
        if bidset is None:
            print(
                f"no bidset for {fordate} (fetch failed, or nothing on file yet)", file=sys.stderr
            )
            return 1
        print(render_table(bidset, config.resources))
        return 0

    if args.review:
        tomorrow = current_operating_hour()[0] + timedelta(days=1)
        book = fetch_day_book(tomorrow, config.participant, env=config.env)
        if book is None or book.bidset is None:
            print(f"no bidset for {tomorrow} (fetch failed, or nothing on file yet)")
            return 1
        findings = review(
            book,
            config.resources,
            charge_block_hours=config.charge_block_hours,
            charge_block_mwh=config.charge_block_mwh,
            min_discharge_mw=config.min_discharge_mw,
            check_discharge_present=config.check_discharge_present,
            check_symmetry=config.check_esr_symmetry,
        )
        if not findings:
            print(f"{tomorrow} day-ahead bid passes every check")
            return 0
        print(review_header("", tomorrow, findings))
        print(render_review(findings))
        return 1

    run(config)
    return 0
