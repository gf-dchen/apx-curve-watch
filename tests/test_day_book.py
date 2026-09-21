"""AS-offer parsing, against the shape a live PRE response actually has."""

from datetime import date

from gfem.foundry.bidding.apx_bids import BidSet, OfferCurve

from apx_curve_watch.day_book import DayBook, parse_as_offers

# Namespaced exactly as APX returns it, with an unoffered hour written as an
# empty <CurvePoint/> and RRS-PFR split across two LinkedOfferIDs -- both are
# real features of a live book, not invented edge cases.
XML = """<Response xmlns="http://service.apx.com/schedule" MarketStatus="PRE">
 <MarketParticipantData Region="TX" MarketParticipant="QGFEN">
  <BidsOffers IntervalLength="PT1H" TransactionType="Gen" Location="SAH_ESR1">
   <MarketSchedule ProductType="Energy">
    <Curve FromInterval="9" CurveType="Slope" Status="Accepted">
     <CurvePoint MW="-100" Price="25"/><CurvePoint MW="0" Price="25"/>
    </Curve>
    <Curve FromInterval="20" CurveType="Slope" Status="Accepted">
     <CurvePoint MW="0" Price="65"/><CurvePoint MW="100" Price="65"/>
    </Curve>
   </MarketSchedule>
   <MarketSchedule ProductType="ECRS" LinkedOfferID="1">
    <Curve FromInterval="9"><CurvePoint/></Curve>
    <Curve FromInterval="20" Status="Accepted"><CurvePoint MW="100" Price="1"/></Curve>
   </MarketSchedule>
   <MarketSchedule ProductType="RRS-PFR" LinkedOfferID="1">
    <Curve FromInterval="20" Status="Accepted"><CurvePoint MW="60" Price="1"/></Curve>
   </MarketSchedule>
   <MarketSchedule ProductType="RRS-PFR" LinkedOfferID="2">
    <Curve FromInterval="20" Status="Accepted"><CurvePoint MW="80" Price="1"/></Curve>
   </MarketSchedule>
  </BidsOffers>
 </MarketParticipantData>
</Response>"""


def test_as_offers_are_read_per_resource_hour_and_product():
    offers = parse_as_offers(XML)
    assert offers == {"SAH_ESR1": {20: {"ECRS": 100.0, "RRS-PFR": 80.0}}}


def test_energy_is_left_to_the_gfem_parser():
    assert "Energy" not in parse_as_offers(XML)["SAH_ESR1"][20]


def test_an_unoffered_hour_is_absent_not_zero():
    # HE09 carries an empty <CurvePoint/> for ECRS -- that hour offers no AS at
    # all, which must not read as "ECRS bid, 0 MW".
    assert 9 not in parse_as_offers(XML)["SAH_ESR1"]


def test_duplicate_product_legs_envelope_rather_than_sum():
    # RRS-PFR under two LinkedOfferIDs (60 and 80) is one 80 MW offer, not 140.
    assert parse_as_offers(XML)["SAH_ESR1"][20]["RRS-PFR"] == 80.0


def test_malformed_xml_degrades_to_no_as_rather_than_raising():
    assert parse_as_offers("<Response") == {}


def test_as_mw_is_the_largest_product_and_zero_where_nothing_is_bid():
    book = DayBook(
        fordate=date(2026, 9, 21),
        bidset=BidSet(fordate=date(2026, 9, 21), market_status="PRE", curves=[]),
        as_offers=parse_as_offers(XML),
    )
    assert book.as_mw("SAH_ESR1", 20) == 100.0
    assert book.as_mw("SAH_ESR1", 9) == 0.0
    assert book.as_mw("SAH_ESR2", 20) == 0.0


def test_day_book_holds_both_sides_of_the_same_response():
    curves = [OfferCurve("SAH_ESR1", 20, [(0.0, 65.0), (100.0, 65.0)], "Slope", "Accepted")]
    book = DayBook(
        fordate=date(2026, 9, 21),
        bidset=BidSet(fordate=date(2026, 9, 21), market_status="PRE", curves=curves),
        as_offers=parse_as_offers(XML),
    )
    assert book.bidset is not None and book.bidset.hours() == [20]
    assert book.as_products("SAH_ESR1", 20) == {"ECRS": 100.0, "RRS-PFR": 80.0}
