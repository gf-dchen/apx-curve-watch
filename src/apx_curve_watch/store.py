"""On-disk archive of every observed hourly ladder.

Storing the curve is a deliverable in its own right, independent of alerting --
the diff step just reads this back. Layout:
``{root}/{fordate}/HH{he:02d}/{timestamp}.json``, plus a ``latest.json`` per hour
that the next poll compares against.
"""

from __future__ import annotations

import json
import os
from dataclasses import dataclass
from datetime import date, datetime
from pathlib import Path

from apx_curve_watch.snapshot import Ladders


@dataclass(frozen=True)
class Snapshot:
    fordate: date
    he: int
    observed_at: datetime
    ladders: Ladders


class CurveStore:
    def __init__(self, root: Path) -> None:
        self.root = root

    def _hour_dir(self, fordate: date, he: int) -> Path:
        return self.root / fordate.isoformat() / f"HH{he:02d}"

    def latest_path(self, fordate: date, he: int) -> Path:
        return self._hour_dir(fordate, he) / "latest.json"

    def load_latest(self, fordate: date, he: int) -> Ladders | None:
        path = self.latest_path(fordate, he)
        if not path.exists():
            return None
        try:
            return json.loads(path.read_text())["ladders"]
        except (json.JSONDecodeError, KeyError, OSError):
            return None

    def save(self, snap: Snapshot) -> Path:
        hour_dir = self._hour_dir(snap.fordate, snap.he)
        hour_dir.mkdir(parents=True, exist_ok=True)
        blob = {
            "fordate": snap.fordate.isoformat(),
            "he": snap.he,
            "observed_at": snap.observed_at.isoformat(timespec="seconds"),
            "ladders": snap.ladders,
        }
        text = json.dumps(blob, indent=1, sort_keys=True)
        (hour_dir / f"{snap.observed_at.strftime('%Y%m%dT%H%M%SZ')}.json").write_text(text)

        latest = self.latest_path(snap.fordate, snap.he)
        tmp = latest.with_suffix(".tmp")
        tmp.write_text(text)
        os.replace(tmp, latest)
        return latest
