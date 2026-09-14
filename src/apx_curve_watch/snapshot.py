"""Turn a fetched ``BidSet`` into the per-resource ladder this tool diffs and stores.

Uses ``curve_points`` (not ``apx_bids.ladder`` directly) so a curve's own points
aren't dropped when two of them share a price -- see ``curve_points`` for why.
"""

from __future__ import annotations

from gfem.foundry.bidding import apx_bids

from apx_curve_watch.curve_points import curve_points

Ladders = dict[str, list[list[float]]]


def ladder_snapshot(bidset: apx_bids.BidSet, he: int, resources: tuple[str, ...] = ()) -> Ladders:
    """``{resource: [[mw, price], ...]}`` for hour-ending ``he``.

    ``resources`` narrows to that set; empty (the default) means every resource
    the bidset carries for this hour. Points are lists, not tuples, so a snapshot
    round-trips through JSON unchanged.
    """
    names = resources or tuple(bidset.resources)
    return {
        resource: [[mw, price] for mw, price in curve_points(bidset, he, resource)]
        for resource in names
    }
