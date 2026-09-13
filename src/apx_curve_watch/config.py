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

_REPO_ROOT = Path(__file__).resolve().parents[2]

load_dotenv(_REPO_ROOT / ".env")


@dataclass(frozen=True)
class WatchConfig:
    participant: str
    env: str
    resources: tuple[str, ...]
    poll_seconds: int
    storage_dir: str
    teams_webhook_url: str | None
    next_day_check_times: tuple[time, ...]

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
        )
