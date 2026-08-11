"""AU Deal Hunter collector — Phase 4.

Invariant: promotions are retained independently of their Deal Score. The Good Deals tab is a derived view.
"""
from __future__ import annotations

import json
import os
from datetime import datetime, timezone, timedelta
from pathlib import Path

from intelligence import enrich_deals, score_deal  # re-exported for tests/backward compatibility
from discord_alerts import process_discord_alerts
from sources import OzBargainSource, EbaySource, GenericRetailerSource, AmazonAUSource
from au_rules import enforce_au_deal
from remote_config import load_remote_config, load_source_controls, load_admin_rules, apply_admin_rules

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "docs" / "data" / "deals.json"
MAX_STALE_DAYS = 14


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def load_existing() -> dict:
    if not OUT.exists():
        return {"updated_at": None, "deals": [], "source_health": []}
    try:
        return json.loads(OUT.read_text(encoding="utf-8"))
    except Exception:
        return {"updated_at": None, "deals": [], "source_health": []}


def parse_dt(value: str | None) -> datetime | None:
    if not value:
        return None
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00"))
    except Exception:
        return None


def merge(existing: list[dict], fresh: list[dict]) -> list[dict]:
    """Merge observations without filtering on score.

    Missing listings are retained for MAX_STALE_DAYS so a temporary source outage does not erase them.
    """
    by_id = {d.get("id"): d for d in existing if d.get("id")}
    observed = set()
    for d in fresh:
        did = d.get("id")
        if not did:
            continue
        observed.add(did)
        old = by_id.get(did)
        if old:
            d["first_seen"] = old.get("first_seen") or d.get("first_seen")
            # Preserve metadata not necessarily emitted by source adapters.
            for key in ("ozbargain_votes", "preference_score"):
                if d.get(key) is None and old.get(key) is not None:
                    d[key] = old[key]
        by_id[did] = d

    cutoff = datetime.now(timezone.utc) - timedelta(days=MAX_STALE_DAYS)
    retained = []
    for d in by_id.values():
        last = parse_dt(d.get("last_seen")) or parse_dt(d.get("first_seen"))
        if d.get("id") in observed or last is None or last >= cutoff:
            retained.append(d)
    return retained


def sources():
    controls = load_source_controls()
    candidates = [
        ("ozbargain", OzBargainSource()),
        ("ebay_au", EbaySource()),
        ("amazon_au", AmazonAUSource()),
        ("mwave", GenericRetailerSource("Mwave", [
            "https://www.mwave.com.au/catalog/mwave-promos",
            "https://www.mwave.com.au/clearance",
        ])),
        ("scorptec", GenericRetailerSource("Scorptec", [
            "https://www.scorptec.com.au/promotions",
            "https://www.scorptec.com.au/product/clearance",
        ])),
        ("centrecom", GenericRetailerSource("Centre Com", [
            "https://www.centrecom.com.au/promotions",
            "https://www.centrecom.com.au/promotion/hotdeals",
            "https://www.centrecom.com.au/clearance",
        ])),
        ("umart", GenericRetailerSource("Umart", [
            "https://www.umart.com.au/hot-deals",
            "https://www.umart.com.au/promotions",
            "https://www.umart.com.au/clearance-sale",
        ])),
    ]
    return [src for key, src in candidates if controls.get(key, True)]


def main():
    existing = load_existing()
    config = load_remote_config()
    watchlist, blocks = load_admin_rules()
    if not os.getenv("DISCORD_DEAL_SCORE_THRESHOLD"):
        os.environ["DISCORD_DEAL_SCORE_THRESHOLD"] = str(config.get("good_deal_score_threshold", 75))
    if not os.getenv("DISCORD_REALERT_PRICE_DROP_PERCENT"):
        os.environ["DISCORD_REALERT_PRICE_DROP_PERCENT"] = str(config.get("discord_price_drop_percent", 3))
    if not os.getenv("DISCORD_REALERT_SCORE_IMPROVEMENT"):
        os.environ["DISCORD_REALERT_SCORE_IMPROVEMENT"] = str(config.get("discord_score_improvement", 8))
    collected: list[dict] = []
    health: list[dict] = []
    for source in sources():
        deals, status = source.collect()
        au_deals=[]
        rejected=0
        for deal in deals:
            ok, reason=enforce_au_deal(deal)
            if ok: au_deals.append(deal)
            else: rejected += 1
        collected.extend(au_deals)
        if rejected:
            status.message += f"; rejected {rejected} non-AU/non-AUD records"
            status.deals_found = len(au_deals)
        health.append(status.dict())
        print(f"[{status.status.upper():>14}] {status.source:<15} {status.deals_found:>4} deals — {status.message}")

    collected, blocked_count = apply_admin_rules(collected, watchlist, blocks)
    merged = merge(existing.get("deals", []), collected)
    merged, _ = apply_admin_rules(merged, watchlist, blocks)
    enriched, intel_stats = enrich_deals(merged, collected)
    enriched.sort(key=lambda d: (d.get("good_deal", False), d.get("deal_score", 0), d.get("discount_percent") or 0), reverse=True)

    discord_stats = process_discord_alerts(enriched)
    print(f"Discord: {discord_stats}")

    out = {
        "schema_version": 5,
        "demo": False,
        "updated_at": now_iso(),
        "scan_interval_hours": int(config.get("scan_interval_hours", 6)),
        "market": "AU",
        "currency": "AUD",
        "deals": enriched,
        "source_health": health,
        "stats": {
            "fresh_records": len(collected),
            "retained_records": len(enriched),
            "sources_ok": sum(1 for h in health if h["status"] == "ok"),
            "sources_total": len(health),
            **intel_stats,
            "discord_status": discord_stats.get("status"),
            "discord_qualified": discord_stats.get("qualified", 0),
            "discord_alerts_sent": discord_stats.get("sent", 0),
            "discord_duplicates_suppressed": discord_stats.get("duplicates_suppressed", 0),
            "discord_alert_failures": discord_stats.get("failed", 0),
            "discord_price_drop_realerts": discord_stats.get("price_drop_realerts", 0),
            "discord_score_realerts": discord_stats.get("score_realerts", 0),
            "blocked_by_admin": blocked_count,
            "watchlist_rules": len(watchlist),
        },
        "discord": discord_stats,
    }
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(out, indent=2, ensure_ascii=False), encoding="utf-8")
    print(f"Wrote {len(enriched)} retained records to {OUT}")
    print(f"Price intelligence: {intel_stats}")


if __name__ == "__main__":
    main()
