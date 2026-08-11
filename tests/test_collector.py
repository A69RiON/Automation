import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))

from collector import merge
from intelligence import score_deal


def test_low_score_is_not_deleted():
    d={"id":"x","title":"Ordinary sale","retailer":"Test","price":80,"was_price":100,"discount_percent":20,"historical_low":None,"market_average":None,"ozbargain_votes":None,"first_seen":"2026-08-12T00:00:00+00:00","last_seen":"2026-08-12T00:00:00+00:00","status":"active","match_confidence":.4,"history_samples":0,"competitor_count":0,"suspected_inflated_rrp":False}
    scored=score_deal(d)
    assert scored["discount_percent"] == 20
    merged=merge([], [scored])
    assert len(merged) == 1


def test_good_view_is_derived():
    d={"id":"x","title":"Strong sale","retailer":"Test","price":50,"was_price":100,"discount_percent":50,"historical_low":None,"market_average":None,"ozbargain_votes":None,"first_seen":"2026-08-12T00:00:00+00:00","last_seen":"2026-08-12T00:00:00+00:00","status":"active","match_confidence":.4,"history_samples":0,"competitor_count":0,"suspected_inflated_rrp":False}
    assert score_deal(d)["good_deal"] is True
