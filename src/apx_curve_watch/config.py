"""Runtime configuration, resolved from the environment on each call.

Credentials themselves are read by ``gfem.env``/``apx_client`` further down the
call chain (``APX_CLIENT_ID`` / ``APX_SECRET`` / ``APX_USERNAME`` /
``APX_PASSWORD``) -- that resolution loads gfem-data's own ``.env``, anchored to
where ``gfem`` is installed, never this repo. This tool's OWN knobs (below) are
plain ``os.environ`` reads, so they need this repo's own ``.env`` loaded
separately -- ``load_dotenv`` is anchored to this file's repo root, never the
caller's cwd, for the same reason gfem anchors its own.
"""

from __future__ import annotations

import os
from dataclasses import dataclass
from datetime import time
from pathlib import Path

from dotenv import load_dotenv

from apx_curve_watch.schedule import parse_check_times

DEFAULT_NEXT_DAY_CHECK_TIMES = "08:30-09:00:15,09:00-09:30:10,09:30-10:00:5"
DEFAULT_CHARGE_BLOCK_HOURS = "9-13"
DEFAULT_CHARGE_BLOCK_MWH = 1000.0
DEFAULT_MIN_DISCHARGE_MW = 200.0

_REPO_ROOT = Path(__file__).resolve().parents[2]

load_dotenv(_REPO_ROOT / ".env")


DEFAULT_LOG_FILE = "apx-curve-watch.log"


def parse_hours(raw: str) -> tuple[int, ...]:
    """``"9-13"`` or ``"9,10,11"`` -> the hour-endings it names, sorted and deduped.

    Empty (or a spec naming no hour) disables whatever block it configures.
    """
    hours: list[int] = []
    for chunk in raw.split(","):
        chunk = chunk.strip()
        if not chunk:
            continue
        start, sep, end = chunk.partition("-")
        hours.extend(range(int(start), int(end) + 1) if sep else [int(start)])
    return tuple(sorted(set(hours)))


def _flag(raw: str) -> bool:
    return raw.strip().lower() not in {"", "0", "false", "no", "off"}


@dataclass(frozen=True)
class WatchConfig:
    participant: str
    env: str
    resources: tuple[str, ...]
    poll_seconds: int
    storage_dir: str
    teams_webhook_url: str | None
    next_day_check_times: tuple[time, ...]
    log_file: str
    # Day-ahead reasonability rules -- desk parameters, so each is a knob rather
    # than a constant in the rule itself (see ``bid_review``).
    charge_block_hours: tuple[int, ...] = ()
    charge_block_mwh: float = DEFAULT_CHARGE_BLOCK_MWH
    min_discharge_mw: float = DEFAULT_MIN_DISCHARGE_MW
    check_discharge_present: bool = True
    check_esr_symmetry: bool = True

    @classmethod
    def from_env(cls) -> WatchConfig:
        resources_raw = os.environ.get("APX_CURVE_WATCH_RESOURCES", "")
        return cls(
            participant=os.environ.get("APX_MARKET_PARTICIPANT", "QGFEN"),
            env=os.environ.get("APX_ENV", "prod"),
            resources=tuple(r.strip() for r in resources_raw.split(",") if r.strip()),
            poll_seconds=int(os.environ.get("APX_CURVE_WATCH_POLL_SECONDS", "30")),
            storage_dir=os.environ.get("APX_CURVE_WATCH_STORAGE_DIR", "./curves"),
            teams_webhook_url=os.environ.get("TEAMS_WEBHOOK_URL") or None,
            next_day_check_times=parse_check_times(
                os.environ.get("APX_CURVE_WATCH_NEXT_DAY_CHECK_TIMES", DEFAULT_NEXT_DAY_CHECK_TIMES)
            ),
            log_file=os.environ.get("APX_CURVE_WATCH_LOG_FILE", DEFAULT_LOG_FILE),
            charge_block_hours=parse_hours(
                os.environ.get("APX_CURVE_WATCH_CHARGE_BLOCK_HOURS", DEFAULT_CHARGE_BLOCK_HOURS)
            ),
            charge_block_mwh=float(
                os.environ.get("APX_CURVE_WATCH_CHARGE_BLOCK_MWH", DEFAULT_CHARGE_BLOCK_MWH)
            ),
            min_discharge_mw=float(
                os.environ.get("APX_CURVE_WATCH_MIN_DISCHARGE_MW", DEFAULT_MIN_DISCHARGE_MW)
            ),
            check_discharge_present=_flag(
                os.environ.get("APX_CURVE_WATCH_CHECK_DISCHARGE_PRESENT", "true")
            ),
            check_esr_symmetry=_flag(os.environ.get("APX_CURVE_WATCH_CHECK_ESR_SYMMETRY", "true")),
        )
