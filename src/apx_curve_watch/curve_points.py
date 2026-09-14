"""The resolved ``(mw, price)`` points for one resource-hour.

``apx_bids.ladder`` groups points by PRICE across every curve APX holds for a
(resource, hour) to dedupe a genuine re-submission (or a DAM+RTM leg) without
summing them -- correct when there really are multiple curve objects, but it
also silently drops any point of a SINGLE curve that happens to share a price
with another of its own points (a flat/vertical segment). Confirmed live: a
real curve with points ``[(-200, 25), (0, 25)]`` came back from ``ladder`` as
just ``[(-200, 25)]`` -- the second point vanished because both share price 25.

With exactly one curve on file (the overwhelming common case), this returns
its points untouched. With more than one, it falls back to ``apx_bids.ladder``,
since deduping across curves is exactly what that's for.
"""

from __future__ import annotations

from gfem.foundry.bidding import apx_bids


def curve_points(bidset: apx_bids.BidSet, he: int, resource: str) -> list[tuple[float, float]]:
    curves = bidset.by_he(he, resource=resource)
    if len(curves) <= 1:
        return list(curves[0].points) if curves else []
    return apx_bids.ladder(bidset, he, resource=resource)
