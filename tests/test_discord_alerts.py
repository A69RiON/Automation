import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

from discord_alerts import should_alert, qualifies, process_discord_alerts


def deal(price=100.0, score=85, good=True):
    return {
        "id": "deal-1",
        "product_key": "product-1",
        "title": "Test Product",
        "retailer": "Test Store",
        "price": price,
        "deal_score": score,
        "good_deal": good,
        "status": "active",
        "url": "https://example.com/deal",
    }


def test_qualifies_good_deal(monkeypatch):
    monkeypatch.setenv("DISCORD_DEAL_SCORE_THRESHOLD", "75")
    assert qualifies(deal(score=80)) is True
    assert qualifies(deal(score=70)) is False
    assert qualifies(deal(score=90, good=False)) is False


def test_first_good_deal_alerts(monkeypatch):
    monkeypatch.setenv("DISCORD_DEAL_SCORE_THRESHOLD", "75")
    ok, reason = should_alert(deal(), None)
    assert ok is True
    assert reason == "new_good_deal"


def test_duplicate_is_suppressed(monkeypatch):
    monkeypatch.setenv("DISCORD_REALERT_PRICE_DROP_PERCENT", "3")
    monkeypatch.setenv("DISCORD_REALERT_SCORE_IMPROVEMENT", "8")
    previous = {"last_alert_price": 100, "last_alert_score": 85}
    ok, reason = should_alert(deal(price=99, score=86), previous)
    assert ok is False
    assert reason == "duplicate_suppressed"


def test_price_drop_realerts(monkeypatch):
    monkeypatch.setenv("DISCORD_REALERT_PRICE_DROP_PERCENT", "3")
    previous = {"last_alert_price": 100, "last_alert_score": 85}
    ok, reason = should_alert(deal(price=96, score=85), previous)
    assert ok is True
    assert reason == "price_drop"


def test_missing_webhook_does_not_fail_collection(monkeypatch, tmp_path):
    monkeypatch.delenv("DISCORD_WEBHOOK_URL", raising=False)
    history = tmp_path / "alert-history.json"
    stats = process_discord_alerts([deal()], history_path=history)
    assert stats["status"] == "not_configured"
    assert stats["qualified"] == 1
    assert stats["sent"] == 0
    assert history.exists()
