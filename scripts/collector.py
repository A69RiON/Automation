"""AU Deal Hunter collector — Phase 2.

Key invariant: low-scoring promotions are never discarded by the scoring layer.
The Good Deals tab is a derived view of the full retained discount/deal dataset.
"""
from __future__ import annotations

import json
import math
from datetime import datetime, timezone, timedelta
from pathlib import Path
from typing import Any

from sources import OzBargainSource, EbaySource, GenericRetailerSource

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "docs" / "data" / "deals.json"
STATE = ROOT / "data" / "collector-state.json"
MAX_STALE_DAYS = 14


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def num(v: Any, default: float = 0.0) -> float:
    try:
        x = float(v)
        return x if math.isfinite(x) else default
    except (TypeError, ValueError):
        return default


def score_deal(d: dict) -> dict:
    """Phase-2 score: conservative when history/competitor data is absent.

    Phase 3 replaces the placeholders with persisted historical and cross-retailer intelligence.
    """
    pct = d.get("discount_percent")
    discount = min(30, max(0, round(num(pct) * 0.75))) if pct is not None else 0

    hist, price = d.get("historical_low"), d.get("price")
    historical = 0
    if hist and price:
        # Strong only when current price approaches/beats history.
        ratio = num(price) / max(num(hist), 0.01)
        historical = 25 if ratio <= 1 else max(0, round(25 - (ratio - 1) * 100))

    market = d.get("market_average")
    competitor = 0
    if market and price:
        competitor = min(15, max(0, round((num(market) - num(price)) / max(num(market), 1) * 60 + 5)))

    community_votes = d.get("ozbargain_votes")
    community = min(15, round(num(community_votes) / 12)) if community_votes is not None else (5 if d.get("source") == "OzBargain" else 0)
    confidence = 8 if d.get("retailer") not in (None, "Unknown retailer") else 5
    preference = num(d.get("preference_score"), 0)
    total = min(100, int(discount + historical + competitor + community + confidence + preference))

    # Until Phase 3 history exists, a strong advertised discount can qualify while retaining a moderate threshold.
    good = total >= 75 or (pct is not None and num(pct) >= 35 and total >= 35)
    d["deal_score"] = total
    d["good_deal"] = bool(good)
    d["score_breakdown"] = {
        "advertised_discount": f"{discount}/30",
        "historical_value": f"{historical}/25",
        "competitor_value": f"{competitor}/15",
        "community_signal": f"{community}/15",
        "retailer_confidence": f"{confidence}/10",
        "preference": f"{int(preference)}/5",
    }
    return d


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
    by_id = {d.get("id"): d for d in existing if d.get("id")}
    observed = set()
    for d in fresh:
        did = d.get("id")
        if not did:
            continue
        observed.add(did)
        old = by_id.get(did)
        if old:
            # Preserve first seen and intelligence fields accumulated by later phases.
            d["first_seen"] = old.get("first_seen") or d.get("first_seen")
            for key in ("historical_low", "market_average", "ozbargain_votes", "preference_score"):
                if d.get(key) is None and old.get(key) is not None:
                    d[key] = old[key]
        by_id[did] = score_deal(d)

    # Preserve temporarily missing deals. A single source outage must not erase dashboard data.
    cutoff = datetime.now(timezone.utc) - timedelta(days=MAX_STALE_DAYS)
    retained = []
    for d in by_id.values():
        last = parse_dt(d.get("last_seen")) or parse_dt(d.get("first_seen"))
        if d.get("id") in observed or last is None or last >= cutoff:
            retained.append(d)
    return retained


def sources():
    return [
        OzBargainSource(),
        EbaySource(),
        GenericRetailerSource("Mwave", [
            "https://www.mwave.com.au/catalog/mwave-promos",
            "https://www.mwave.com.au/clearance",
        ]),
        GenericRetailerSource("Scorptec", [
            "https://www.scorptec.com.au/promotions",
            "https://www.scorptec.com.au/product/clearance",
        ]),
        GenericRetailerSource("Centre Com", [
            "https://www.centrecom.com.au/promotions",
            "https://www.centrecom.com.au/promotion/hotdeals",
            "https://www.centrecom.com.au/clearance",
        ]),
        GenericRetailerSource("Umart", [
            "https://www.umart.com.au/hot-deals",
            "https://www.umart.com.au/promotions",
            "https://www.umart.com.au/clearance-sale",
        ]),
    ]


def main():
    existing = load_existing()
    collected: list[dict] = []
    health: list[dict] = []
    for source in sources():
        deals, status = source.collect()
        collected.extend(deals)
        health.append(status.dict())
        print(f"[{status.status.upper():>14}] {status.source:<15} {status.deals_found:>4} deals — {status.message}")

    merged = merge(existing.get("deals", []), collected)
    merged.sort(key=lambda d: (d.get("good_deal", False), d.get("deal_score", 0), d.get("discount_percent") or 0), reverse=True)
    out = {
        "schema_version": 2,
        "demo": False,
        "updated_at": now_iso(),
        "scan_interval_hours": 6,
        "deals": merged,
        "source_health": health,
        "stats": {
            "fresh_records": len(collected),
            "retained_records": len(merged),
            "sources_ok": sum(1 for h in health if h["status"] == "ok"),
            "sources_total": len(health),
        },
    }
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(out, indent=2, ensure_ascii=False), encoding="utf-8")
    print(f"Wrote {len(merged)} retained records to {OUT}")


if __name__ == "__main__":
    main()
