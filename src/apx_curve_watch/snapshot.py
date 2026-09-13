"""Turn a fetched ``BidSet`` into the per-resource ladder this tool diffs and stores.

Reuses ``apx_bids.ladder`` -- the cumulative MW->$ envelope across whatever curves
APX holds for a (resource, hour) -- so the change view reads the same as the ladder
charts ``live_monitor.py`` already draws from the same data.
"""

from __future__ import annotations

from gfem.foundry.bidding import apx_bids

Ladders = dict[str, list[list[float]]]


def ladder_snapshot(bidset: apx_bids.BidSet, he: int, resources: tuple[str, ...] = ()) -> Ladders:
    """``{resource: [[mw, price], ...]}`` for hour-ending ``he``.

    ``resources`` narrows to that set; empty (the default) means every resource
    the bidset carries for this hour. Points are lists, not tuples, so a snapshot
    round-trips through JSON unchanged.
    """
    names = resources or tuple(bidset.resources)
    return {
        resource: [[mw, price] for mw, price in apx_bids.ladder(bidset, he, resource=resource)]
        for resource in names
    }
