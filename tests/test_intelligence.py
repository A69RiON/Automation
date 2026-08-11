import json
import sys
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

import intelligence
from intelligence import product_identity, enrich_deals, score_deal


def test_exact_model_identity_matches_across_retailers():
    a={"title":"Samsung 990 PRO 2TB NVMe SSD MZ-V9P2T0BW"}
    b={"title":"Samsung MZ-V9P2T0BW 990 Pro NVMe 2TB SSD"}
    ia=product_identity(a)
    ib=product_identity(b)
    assert ia["model"] == "MZ-V9P2T0BW"
    assert ia["product_key"] == ib["product_key"]
    assert ia["match_confidence"] >= .9


def test_market_and_history_enrichment(tmp_path, monkeypatch):
    history=tmp_path/"price-history.json"
    monkeypatch.setattr(intelligence, "HISTORY_FILE", history)
    base={
        "title":"Samsung 990 PRO 2TB NVMe SSD MZ-V9P2T0BW", "model":None,
        "category":"Storage", "was_price":349.0, "discount_percent":20.0,
        "first_seen":"2026-08-10T00:00:00+00:00", "last_seen":"2026-08-12T00:00:00+00:00",
        "ozbargain_votes":None, "source":"Test"
    }
    first=[dict(base,id="a1",retailer="Amazon AU",price=279.0,url="https://a"),
           dict(base,id="s1",retailer="Scorptec",price=299.0,url="https://s")]
    enriched,_=enrich_deals(first, first)
    # second observation creates usable history and a new low
    second=[dict(base,id="a1",retailer="Amazon AU",price=219.0,url="https://a",last_seen="2026-08-12T06:00:00+00:00"),
            dict(base,id="s1",retailer="Scorptec",price=289.0,url="https://s",last_seen="2026-08-12T06:00:00+00:00")]
    enriched,stats=enrich_deals(second, second)
    amazon=next(x for x in enriched if x["retailer"]=="Amazon AU")
    assert amazon["historical_low"] == 219.0
    assert amazon["history_samples"] >= 2
    assert amazon["competitor_low"] == 289.0
    assert amazon["new_historical_low"] is True
    assert stats["cross_retailer_matches"] >= 2


def test_low_score_promotion_remains_classifiable():
    d={"discount_percent":20,"price":279,"historical_low":229,"history_samples":5,
       "real_discount_percent":0,"market_average":279,"competitor_low":259,"competitor_count":2,
       "match_confidence":.95,"retailer":"Scorptec","ozbargain_votes":None,"source":"Test",
       "status":"active","suspected_inflated_rrp":True}
    score_deal(d)
    assert d["deal_score"] < 70
    assert d["good_deal"] is False
