"""One operating day's whole APX book: energy ladders AND ancillary-service offers.

``apx_bids.fetch_bidset`` parses energy only, on purpose -- its
``ProductType != "Energy"`` filter exists because the ladder charts it feeds
want energy. The day-ahead review needs the AS side too: the 200 MW rule only
applies to an hour carrying BOTH discharge energy and an AS offer, so without
AS we'd have to warn on every discharge hour and cry wolf.

Rather than widen that shared parser (a gfem-data change on its own branch),
this repeats gfem's fetch out of its own pieces -- same query, same token, same
unzip -- and parses the non-``Energy`` ``MarketSchedule``s here. One round-trip
serves both sides: the same XML goes to ``parse_bidset`` and ``parse_as_offers``.

Confirmed against a live PRE response: AS rides as sibling ``MarketSchedule``
elements under the same ``<BidsOffers Location=...>``, with ``ProductType``
naming the service (``ECRS``, ``RRS-PFR``) and the same ``Curve`` /
``CurvePoint`` shape as energy.
"""

from __future__ import annotations

import logging
import xml.etree.ElementTree as ET
from dataclasses import dataclass
from datetime import date

import requests
from gfem.foundry.bidding import apx_bids, apx_client
from gfem.foundry.bidding.apx_client import APXCredentials, APXError

logger = logging.getLogger("apx_curve_watch")

# resource -> hour-ending -> AS product -> MW offered
ASOffers = dict[str, dict[int, dict[str, float]]]


@dataclass(frozen=True)
class DayBook:
    """What APX holds for one operating day, both product sides.

    ``bidset`` is ``None`` when the day carries no priced energy curve at all --
    the normal early-morning state, not an error.
    """

    fordate: date
    bidset: apx_bids.BidSet | None
    as_offers: ASOffers

    def as_products(self, resource: str, he: int) -> dict[str, float]:
        """``{product: MW}`` offered for one resource-hour; empty if none."""
        return self.as_offers.get(resource, {}).get(he, {})

    def as_mw(self, resource: str, he: int) -> float:
        """Largest single AS product MW offered for one resource-hour.

        Only ever compared against zero by the review rules ("is AS bid in this
        hour at all"), so how products would combine across services doesn't
        change any warning -- see ``parse_as_offers`` on the same question
        within one product.
        """
        return max(self.as_products(resource, he).values(), default=0.0)


def _tag(elem: ET.Element) -> str:
    return elem.tag.split("}")[-1]


def _children(elem: ET.Element, name: str) -> list[ET.Element]:
    return [child for child in elem if _tag(child) == name]


def _curve_mw(curve: ET.Element) -> float | None:
    """The MW an AS offer curve puts up, or ``None`` for an unoffered hour.

    An AS offer is a quantity at a price (``CurveType=Fixed``), so its MW is the
    top of its points -- APX writes an hour with nothing offered as an empty
    ``<CurvePoint/>``, which parses to nothing rather than to zero.
    """
    mws: list[float] = []
    for cp in _children(curve, "CurvePoint"):
        try:
            mws.append(float(cp.get("MW", "")))
        except (TypeError, ValueError):
            continue
    return max(mws) if mws else None


def parse_as_offers(xml: str) -> ASOffers:
    """Every non-energy offer in an APX Scheduling ``<Response>``, by resource-hour.

    A resource-hour can carry the same product more than once -- APX returns one
    ``MarketSchedule`` per ``LinkedOfferID``, and a live book had RRS-PFR under
    both offer 1 and offer 2 in HE23/24. Those are kept as the LARGEST of the
    two rather than summed: duplicate-looking offer legs stacking into a total
    above the resource's capability would be the more misleading error, and it
    matches how ``apx_bids.ladder`` envelopes duplicate energy curves. Nothing
    here depends on that choice today -- the rules only ask whether AS is bid at
    all -- so it is the conservative default rather than a claim about ERCOT's
    aggregation.
    """
    try:
        root = ET.fromstring(xml)
    except ET.ParseError as exc:
        logger.warning("APX AS-offer parse failed: %s", exc)
        return {}

    offers: ASOffers = {}
    for bo in (e for e in root.iter() if _tag(e) == "BidsOffers"):
        resource = bo.get("Location") or "?"
        for ms in _children(bo, "MarketSchedule"):
            product = (ms.get("ProductType") or "").strip()
            if not product or product == apx_bids.ENERGY_PRODUCT_TYPE:
                continue
            for cv in _children(ms, "Curve"):
                interval = cv.get("FromInterval")
                mw = _curve_mw(cv)
                if not interval or mw is None:
                    continue
                by_he = offers.setdefault(resource, {}).setdefault(int(interval), {})
                by_he[product] = max(by_he.get(product, 0.0), mw)
    return offers


def fetch_day_book(
    fordate: date, participant: str, *, market_status: str = "PRE", env: str = "prod"
) -> DayBook | None:
    """Fetch ``fordate``'s book, energy + AS. ``None`` on any fetch/unzip failure.

    Degrades the same way ``fetch_bidset`` does -- this feeds an unattended
    monitor, so an APX outage must cost one check, never the loop.
    """
    try:
        creds = APXCredentials.from_env()
        token = apx_client.get_token(creds, env)
        blob = apx_client.get_schedule_data(
            env,
            token,
            apx_bids.schedule_query(fordate, [participant], market_status=market_status),
        )
    except (APXError, requests.RequestException) as exc:
        logger.warning("APX day book fetch failed %s %s: %s", fordate, market_status, exc)
        return None

    xml = apx_bids.unzip_xml(blob)
    if xml is None:
        return None
    return DayBook(
        fordate=fordate,
        bidset=apx_bids.parse_bidset(xml, fordate, market_status),
        as_offers=parse_as_offers(xml),
    )
