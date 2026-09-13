"""``apx-curve-watch``: store the current ERCOT operating hour's dispatch schedule
bid curve as APX holds it, and log when any point on it moves."""

from __future__ import annotations

import argparse
import logging
import sys
from pathlib import Path

from gfem.foundry.bidding import apx_bids

from apx_curve_watch.config import WatchConfig
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

    run(config)
    return 0
