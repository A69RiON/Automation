"""Discord alert engine for AU Deal Hunter Phase 4.

Secrets are read from environment variables only. No webhook URL is written to
public dashboard data or committed source.
"""
from __future__ import annotations

import json
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import requests

ROOT = Path(__file__).resolve().parents[1]
HISTORY_PATH = ROOT / "data" / "alert-history.json"
DEFAULT_SCORE_THRESHOLD = 75
DEFAULT_PRICE_DROP_PERCENT = 3.0
DEFAULT_SCORE_IMPROVEMENT = 8


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def load_history(path: Path = HISTORY_PATH) -> dict[str, Any]:
    if not path.exists():
        return {"schema_version": 1, "alerts": {}}
    try:
        doc = json.loads(path.read_text(encoding="utf-8"))
        if not isinstance(doc.get("alerts"), dict):
            doc["alerts"] = {}
        return doc
    except Exception:
        return {"schema_version": 1, "alerts": {}}


def save_history(history: dict[str, Any], path: Path = HISTORY_PATH) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    history["schema_version"] = 1
    history["updated_at"] = utc_now_iso()
    path.write_text(json.dumps(history, indent=2, ensure_ascii=False), encoding="utf-8")


def _float_env(name: str, default: float) -> float:
    try:
        return float(os.getenv(name, str(default)))
    except ValueError:
        return default


def _int_env(name: str, default: int) -> int:
    try:
        return int(os.getenv(name, str(default)))
    except ValueError:
        return default


def qualifies(deal: dict[str, Any]) -> bool:
    threshold = _int_env("DISCORD_DEAL_SCORE_THRESHOLD", DEFAULT_SCORE_THRESHOLD)
    return (
        deal.get("good_deal") is True
        and (deal.get("deal_score") or 0) >= threshold
        and deal.get("status", "active") == "active"
        and deal.get("price") is not None
        and bool(deal.get("url"))
    )


def should_alert(deal: dict[str, Any], previous: dict[str, Any] | None) -> tuple[bool, str]:
    if not qualifies(deal):
        return False, "not_qualified"
    if not previous:
        return True, "new_good_deal"

    price = float(deal["price"])
    old_price = previous.get("last_alert_price")
    old_score = previous.get("last_alert_score")

    price_drop_threshold = _float_env("DISCORD_REALERT_PRICE_DROP_PERCENT", DEFAULT_PRICE_DROP_PERCENT)
    score_improvement_threshold = _int_env("DISCORD_REALERT_SCORE_IMPROVEMENT", DEFAULT_SCORE_IMPROVEMENT)

    if old_price not in (None, 0):
        price_drop = (float(old_price) - price) / float(old_price) * 100
        if price_drop >= price_drop_threshold:
            return True, "price_drop"

    if old_score is not None and (deal.get("deal_score") or 0) - int(old_score) >= score_improvement_threshold:
        return True, "score_improved"

    return False, "duplicate_suppressed"


def _aud(value: Any) -> str:
    if value is None:
        return "—"
    try:
        return f"A${float(value):,.2f}"
    except (TypeError, ValueError):
        return "—"


def _pct(value: Any) -> str:
    if value is None:
        return "—"
    try:
        return f"{float(value):.1f}%"
    except (TypeError, ValueError):
        return "—"


def build_payload(deal: dict[str, Any], reason: str) -> dict[str, Any]:
    title_prefix = {
        "new_good_deal": "🔥 GOOD DEAL",
        "price_drop": "📉 PRICE DROP",
        "score_improved": "⬆️ DEAL IMPROVED",
    }.get(reason, "🔥 GOOD DEAL")

    fields = [
        {"name": "Current price", "value": _aud(deal.get("price")), "inline": True},
        {"name": "Deal Score", "value": f"{deal.get('deal_score', 0)}/100", "inline": True},
        {"name": "Retailer", "value": str(deal.get("retailer") or "Unknown"), "inline": True},
        {"name": "Advertised discount", "value": _pct(deal.get("discount_percent")), "inline": True},
        {"name": "Real discount", "value": _pct(deal.get("real_discount_percent")), "inline": True},
        {"name": "Historical low", "value": _aud(deal.get("historical_low")), "inline": True},
        {"name": "Observed normal", "value": _aud(deal.get("normal_street_price")), "inline": True},
        {"name": "Competitor low", "value": _aud(deal.get("competitor_low")), "inline": True},
        {"name": "Data confidence", "value": str(deal.get("data_confidence") or "low").title(), "inline": True},
    ]
    if deal.get("ozbargain_votes") is not None:
        fields.append({"name": "OzBargain", "value": f"+{deal['ozbargain_votes']} votes", "inline": True})
    if deal.get("new_historical_low"):
        fields.append({"name": "Price intelligence", "value": "🏆 New tracked historical low", "inline": False})

    description_bits = []
    if reason == "price_drop":
        description_bits.append("This deal was alerted before, but the price has now dropped enough to trigger a new alert.")
    elif reason == "score_improved":
        description_bits.append("This deal was alerted before, but its Deal Score has materially improved.")
    else:
        description_bits.append("A newly detected promotion passed the Good Deal threshold.")
    if deal.get("suspected_inflated_rrp"):
        description_bits.append("⚠️ Advertised RRP/was-price has an intelligence warning; score already includes the penalty.")

    return {
        "username": "AU Deal Hunter",
        "allowed_mentions": {"parse": []},
        "embeds": [{
            "title": f"{title_prefix} — {deal.get('title', 'Deal')}",
            "url": deal.get("url"),
            "description": "\n".join(description_bits),
            "fields": fields,
            "footer": {"text": f"AU Deal Hunter • {reason.replace('_', ' ')}"},
            "timestamp": utc_now_iso(),
        }],
    }


def send_webhook(webhook_url: str, payload: dict[str, Any]) -> None:
    response = requests.post(webhook_url, json=payload, timeout=20)
    if response.status_code not in (200, 204):
        raise RuntimeError(f"Discord webhook returned HTTP {response.status_code}: {response.text[:300]}")


def process_discord_alerts(deals: list[dict[str, Any]], history_path: Path = HISTORY_PATH) -> dict[str, Any]:
    """Send eligible alerts and persist suppression state.

    If DISCORD_WEBHOOK_URL is absent, the collector remains successful and returns
    a not_configured status. A webhook failure is reported but does not corrupt
    alert history for messages that were not accepted by Discord.
    """
    webhook_url = os.getenv("DISCORD_WEBHOOK_URL", "").strip()
    history = load_history(history_path)
    alerts = history.setdefault("alerts", {})
    stats = {
        "status": "ok" if webhook_url else "not_configured",
        "qualified": 0,
        "sent": 0,
        "duplicates_suppressed": 0,
        "failed": 0,
        "price_drop_realerts": 0,
        "score_realerts": 0,
        "message": "Discord webhook configured." if webhook_url else "Add DISCORD_WEBHOOK_URL as a GitHub Actions secret to enable alerts.",
    }

    for deal in deals:
        if not qualifies(deal):
            continue
        stats["qualified"] += 1
        key = str(deal.get("id") or deal.get("product_key") or deal.get("url"))
        previous = alerts.get(key)
        do_send, reason = should_alert(deal, previous)
        if not do_send:
            if reason == "duplicate_suppressed":
                stats["duplicates_suppressed"] += 1
            continue
        if not webhook_url:
            continue

        try:
            send_webhook(webhook_url, build_payload(deal, reason))
        except Exception as exc:
            stats["failed"] += 1
            stats["status"] = "partial"
            stats["message"] = f"One or more Discord alerts failed: {exc}"
            continue

        now = utc_now_iso()
        prior_count = int(previous.get("alert_count", 0)) if previous else 0
        alerts[key] = {
            "deal_id": deal.get("id"),
            "product_key": deal.get("product_key"),
            "title": deal.get("title"),
            "retailer": deal.get("retailer"),
            "last_alert_price": deal.get("price"),
            "last_alert_score": deal.get("deal_score"),
            "last_alert_reason": reason,
            "last_alert_at": now,
            "alert_count": prior_count + 1,
        }
        stats["sent"] += 1
        if reason == "price_drop":
            stats["price_drop_realerts"] += 1
        elif reason == "score_improved":
            stats["score_realerts"] += 1

    save_history(history, history_path)
    return stats
