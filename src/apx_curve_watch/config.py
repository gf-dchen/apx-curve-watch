"""Runtime configuration, resolved from the environment on each call.

Credentials themselves are read by ``gfem.env``/``apx_client`` further down the
call chain (``APX_CLIENT_ID`` / ``APX_SECRET`` / ``APX_USERNAME`` /
``APX_PASSWORD``) -- this module only holds the knobs specific to *this* tool.
"""

from __future__ import annotations

import os
from dataclasses import dataclass


@dataclass(frozen=True)
class WatchConfig:
    participant: str
    env: str
    resources: tuple[str, ...]
    poll_seconds: int
    storage_dir: str
    teams_webhook_url: str | None

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
        )
