"""Zero-tolerance positional diff between two ladder snapshots.

Daniel's ask was "any point moves at all" -- not a materiality threshold -- so this
compares segment ``i`` of the old ladder to segment ``i`` of the new one exactly,
with no MW/price tolerance. A curve gaining or losing a segment (e.g. 3 -> 4 price
points) shows up as ``added``/``dropped`` at the tail rather than shifting every
later segment's comparison, since ERCOT's 5-point ceiling makes that a structural
move worth calling out on its own.
"""

from __future__ import annotations

from dataclasses import dataclass

from apx_curve_watch.snapshot import Ladders

Point = list[float] | None


@dataclass(frozen=True)
class SegmentChange:
    index: int
    kind: str  # "moved" | "added" | "dropped"
    before: Point
    after: Point


@dataclass(frozen=True)
class ResourceDiff:
    resource: str
    segments: list[SegmentChange]


def diff_snapshots(old: Ladders, new: Ladders) -> list[ResourceDiff]:
    """Every resource whose ladder changed, ``old`` -> ``new``. Empty if nothing moved."""
    out: list[ResourceDiff] = []
    for resource in sorted(set(old) | set(new)):
        before = old.get(resource, [])
        after = new.get(resource, [])
        segments: list[SegmentChange] = []
        for i in range(max(len(before), len(after))):
            b = before[i] if i < len(before) else None
            a = after[i] if i < len(after) else None
            if b is None:
                segments.append(SegmentChange(i, "added", None, a))
            elif a is None:
                segments.append(SegmentChange(i, "dropped", b, None))
            elif b != a:
                segments.append(SegmentChange(i, "moved", b, a))
        if segments:
            out.append(ResourceDiff(resource, segments))
    return out
