import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
from au_rules import enforce_au_deal

def test_rejects_explicit_usd():
    d={"currency":"USD","url":"https://www.ebay.com.au/x","retailer":"eBay AU"}
    ok,_=enforce_au_deal(d)
    assert not ok

def test_accepts_au_and_normalises():
    d={"currency":"AUD","url":"https://www.mwave.com.au/x","retailer":"Mwave"}
    ok,_=enforce_au_deal(d)
    assert ok and d["market"]=="AU" and d["currency"]=="AUD"
