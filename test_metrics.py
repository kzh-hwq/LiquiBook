import math
from metrics import to_num, book_metrics

# Du lieu mau lay tu tai lieu NEO API (HPG)
HPG = {"symbol": "HPG", "bidPrice1": "29750.0", "bidVol1": 293000, "bidPrice2": 29700, "bidVol2": 208800,
       "bidPrice3": 29650, "bidVol3": 25900, "askPrice1": "29800.0", "askVol1": 4000, "askPrice2": 29850,
       "askVol2": 342000, "askPrice3": 29900, "askVol3": 218800}


def test_to_num():
    assert to_num("29750.0") == 29750.0
    assert to_num("ATO") is None and to_num(None) is None


def test_hpg():
    m = book_metrics(HPG)
    assert m["spread"] == 50
    assert math.isclose(m["mid"], 29775)
    assert m["bid_depth"] == 527700 and m["ask_depth"] == 564800
    assert math.isclose(m["imbalance"], (527700 - 564800) / (527700 + 564800))
    assert math.isclose(m["spread_pct"], 50 / 29775 * 100)


def test_invalid_book():
    assert book_metrics({**HPG, "bidPrice1": "ATO"}) is None
    assert book_metrics({**HPG, "bidPrice1": 29900}) is None   # crossed
