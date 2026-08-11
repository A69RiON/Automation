from __future__ import annotations

import hashlib
import json
import math
import re
import statistics
from collections import defaultdict
from datetime import datetime, timezone, timedelta
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
HISTORY_FILE = ROOT / "data" / "price-history.json"
MAX_OBSERVATIONS_PER_PRODUCT = 720  # ~180 days at a 6-hour cadence

STOPWORDS = {
    "sale", "deal", "deals", "black", "friday", "cyber", "monday", "offer", "offers",
    "save", "saving", "off", "discount", "new", "brand", "free", "shipping", "delivery",
    "australia", "australian", "au", "the", "and", "with", "for", "from", "only", "online",
    "special", "clearance", "promo", "promotion", "hot", "price", "rrp", "was", "now",
}
BRANDS = [
    "samsung", "apple", "asus", "acer", "lenovo", "dell", "hp", "msi", "gigabyte", "corsair",
    "logitech", "razer", "sony", "lg", "panasonic", "philips", "dyson", "nintendo", "xbox",
    "playstation", "amd", "intel", "nvidia", "ubiquiti", "unifi", "netgear", "tp-link", "tplink",
    "western digital", "wd", "seagate", "kingston", "crucial", "sandisk", "anker", "bose", "jbl",
]
MODEL_RE = re.compile(r"\b(?=[A-Z0-9-]{5,24}\b)(?=[A-Z0-9-]*[A-Z])(?=[A-Z0-9-]*\d)[A-Z0-9]+(?:-[A-Z0-9]+)*\b", re.I)
CAPACITY_RE = re.compile(r"\b\d+(?:\.\d+)?\s?(?:tb|gb|mb)\b", re.I)
SIZE_RE = re.compile(r"\b\d{2,3}(?:\.\d+)?\s?(?:inch|inches|\")\b", re.I)
GEN_RE = re.compile(r"\b(?:rtx|rx|ryzen|core)\s?[a-z]?\d{3,5}[a-z0-9-]*\b", re.I)


def num(value: Any, default: float | None = None) -> float | None:
    try:
        result = float(value)
        return result if math.isfinite(result) else default
    except (TypeError, ValueError):
        return default


def parse_dt(value: str | None) -> datetime | None:
    if not value:
        return None
    try:
        dt = datetime.fromisoformat(value.replace("Z", "+00:00"))
        return dt if dt.tzinfo else dt.replace(tzinfo=timezone.utc)
    except Exception:
        return None


def normalize_space(value: str) -> str:
    return re.sub(r"\s+", " ", value).strip()


def detect_brand(title: str) -> str | None:
    low = title.lower()
    for brand in sorted(BRANDS, key=len, reverse=True):
        if re.search(rf"\b{re.escape(brand)}\b", low):
            return brand.title() if brand not in {"wd", "amd", "hp", "msi", "lg", "jbl"} else brand.upper()
    return None


def extract_model(title: str) -> str | None:
    # Prefer recognisable product-generation strings first.
    gen = GEN_RE.search(title)
    if gen:
        return normalize_space(gen.group(0).upper())
    candidates = []
    for match in MODEL_RE.finditer(title.upper()):
        token = match.group(0).strip("-")
        # Reject common price/capacity-looking tokens and generic years.
        if re.fullmatch(r"\d+(?:GB|TB|MB)", token):
            continue
        if re.fullmatch(r"20\d{2}", token):
            continue
        if token in {"BLACK-FRIDAY", "WI-FI", "WIFI-6", "WIFI-7"}:
            continue
        candidates.append(token)
    if not candidates:
        return None
    # Longer/more structured identifiers are usually safer than short tokens.
    return sorted(candidates, key=lambda s: ("-" in s, len(s)), reverse=True)[0]


def title_tokens(title: str) -> list[str]:
    low = title.lower().replace("wi-fi", "wifi")
    low = re.sub(r"[^a-z0-9.+]+", " ", low)
    toks = []
    for tok in low.split():
        if tok in STOPWORDS or len(tok) < 2:
            continue
        if tok.isdigit() and len(tok) <= 2:
            continue
        toks.append(tok)
    return toks


def product_identity(deal: dict[str, Any]) -> dict[str, Any]:
    title = str(deal.get("title") or "")
    brand = detect_brand(title)
    model = deal.get("model") or extract_model(title)
    capacities = [normalize_space(x.lower().replace(" ", "")) for x in CAPACITY_RE.findall(title)]
    sizes = [normalize_space(x.lower().replace(" ", "")) for x in SIZE_RE.findall(title)]
    tokens = title_tokens(title)

    if model:
        raw = "|".join(filter(None, [brand or "", model.upper(), capacities[0] if capacities else "", sizes[0] if sizes else ""]))
        method = "model"
        confidence = 0.95
    else:
        # Keep up to 8 informative tokens in original order; require enough detail for cross-retailer comparisons.
        signature = []
        for tok in tokens:
            if tok not in signature:
                signature.append(tok)
            if len(signature) >= 8:
                break
        extras = capacities[:1] + sizes[:1]
        raw = "|".join(([brand.lower()] if brand else []) + signature + extras)
        method = "title_signature"
        confidence = 0.70 if len(signature) >= 5 else 0.45

    digest = hashlib.sha1(raw.encode("utf-8")).hexdigest()[:20] if raw else hashlib.sha1(title.lower().encode("utf-8")).hexdigest()[:20]
    return {
        "product_key": f"product-{digest}",
        "brand": brand,
        "model": model,
        "match_method": method,
        "match_confidence": confidence,
    }


def load_history() -> dict[str, Any]:
    if not HISTORY_FILE.exists():
        return {"schema_version": 1, "products": {}}
    try:
        doc = json.loads(HISTORY_FILE.read_text(encoding="utf-8"))
        if not isinstance(doc.get("products"), dict):
            raise ValueError("invalid products")
        return doc
    except Exception:
        return {"schema_version": 1, "products": {}}


def save_history(doc: dict[str, Any]) -> None:
    HISTORY_FILE.parent.mkdir(parents=True, exist_ok=True)
    doc["schema_version"] = 1
    doc["updated_at"] = datetime.now(timezone.utc).isoformat()
    HISTORY_FILE.write_text(json.dumps(doc, indent=2, ensure_ascii=False), encoding="utf-8")


def record_observations(history: dict[str, Any], fresh: list[dict[str, Any]]) -> None:
    products = history.setdefault("products", {})
    now = datetime.now(timezone.utc).isoformat()
    seen_pairs: set[tuple[str, str]] = set()
    for deal in fresh:
        price = num(deal.get("price"))
        if price is None or price <= 0:
            continue
        ident = product_identity(deal)
        deal.update(ident)
        pair = (ident["product_key"], str(deal.get("retailer") or deal.get("source") or "Unknown"))
        if pair in seen_pairs:
            continue
        seen_pairs.add(pair)
        p = products.setdefault(ident["product_key"], {
            "title": deal.get("title"), "brand": ident["brand"], "model": ident["model"], "observations": []
        })
        p["title"] = deal.get("title") or p.get("title")
        p["brand"] = ident["brand"] or p.get("brand")
        p["model"] = ident["model"] or p.get("model")
        obs = p.setdefault("observations", [])
        obs.append({
            "timestamp": deal.get("last_seen") or now,
            "retailer": deal.get("retailer"),
            "price": round(price, 2),
            "deal_id": deal.get("id"),
            "source": deal.get("source"),
        })
        # Keep bounded history while retaining chronological order.
        if len(obs) > MAX_OBSERVATIONS_PER_PRODUCT:
            del obs[:-MAX_OBSERVATIONS_PER_PRODUCT]


def history_metrics(history: dict[str, Any], key: str) -> dict[str, Any]:
    product = history.get("products", {}).get(key, {})
    obs = product.get("observations", [])
    prices = [num(x.get("price")) for x in obs]
    prices = [p for p in prices if p is not None and p > 0]
    if not prices:
        return {"historical_low": None, "historical_median": None, "history_samples": 0, "history_days": 0}
    timestamps = [parse_dt(x.get("timestamp")) for x in obs]
    timestamps = [x for x in timestamps if x]
    days = 0
    if len(timestamps) >= 2:
        days = max(0, (max(timestamps) - min(timestamps)).days)
    return {
        "historical_low": round(min(prices), 2),
        "historical_median": round(statistics.median(prices), 2),
        "history_samples": len(prices),
        "history_days": days,
    }


def status_for(deal: dict[str, Any], observed_ids: set[str]) -> str:
    if deal.get("id") in observed_ids:
        return "active"
    last = parse_dt(deal.get("last_seen")) or parse_dt(deal.get("first_seen"))
    if not last:
        return "unknown"
    age = datetime.now(timezone.utc) - last.astimezone(timezone.utc)
    if age <= timedelta(hours=36):
        return "recently_missing"
    return "stale"


def score_deal(deal: dict[str, Any]) -> dict[str, Any]:
    price = num(deal.get("price"))
    advertised = num(deal.get("discount_percent"), 0.0) or 0.0
    real_discount = num(deal.get("real_discount_percent"))
    hist_low = num(deal.get("historical_low"))
    market_avg = num(deal.get("market_average"))
    competitor_low = num(deal.get("competitor_low"))
    samples = int(deal.get("history_samples") or 0)
    match_conf = num(deal.get("match_confidence"), 0.0) or 0.0

    # 20 pts: advertised promotion. Always visible, but capped so marketing alone cannot dominate.
    adv_points = min(20, max(0, round(advertised * 0.5)))

    # 30 pts: historical value. New lows score highest; real discount vs observed median helps too.
    hist_points = 0
    if price and hist_low and samples >= 2:
        if price <= hist_low * 1.001:
            hist_points = 30
        else:
            premium = (price - hist_low) / hist_low * 100
            hist_points = max(0, round(27 - premium * 1.6))
        if real_discount is not None and real_discount > 0:
            hist_points = min(30, max(hist_points, round(real_discount * 1.2)))

    # 20 pts: competitor value, only with sufficiently reliable product identity.
    comp_points = 0
    if price and market_avg and deal.get("competitor_count", 0) >= 1 and match_conf >= 0.70:
        advantage = (market_avg - price) / market_avg * 100
        comp_points = min(20, max(0, round(8 + advantage * 1.2)))
        if competitor_low and price <= competitor_low * 1.001:
            comp_points = max(comp_points, 18)

    votes = deal.get("ozbargain_votes")
    community = min(15, round((num(votes, 0.0) or 0.0) / 10)) if votes is not None else (4 if deal.get("source") == "OzBargain" else 0)
    retailer_confidence = 10 if deal.get("retailer") not in (None, "Unknown retailer") else 5
    freshness = {"active": 5, "recently_missing": 2, "stale": 0}.get(deal.get("status"), 1)

    penalty = 15 if deal.get("suspected_inflated_rrp") else 0
    total = int(max(0, min(100, adv_points + hist_points + comp_points + community + retailer_confidence + freshness - penalty)))

    data_confidence = "high" if samples >= 8 and (deal.get("competitor_count") or 0) >= 2 and match_conf >= .70 else "medium" if samples >= 2 or (deal.get("competitor_count") or 0) >= 1 else "low"
    # Strong intelligence threshold. With little history, only an unusually large promotion qualifies provisionally.
    good = total >= 70 or (data_confidence == "low" and advertised >= 45 and total >= 35)

    deal["deal_score"] = total
    deal["good_deal"] = bool(good)
    deal["data_confidence"] = data_confidence
    deal["score_breakdown"] = {
        "advertised_discount": f"{adv_points}/20",
        "historical_value": f"{hist_points}/30",
        "competitor_value": f"{comp_points}/20",
        "community_signal": f"{community}/15",
        "retailer_confidence": f"{retailer_confidence}/10",
        "freshness": f"{freshness}/5",
        "rrp_penalty": f"-{penalty}",
    }
    return deal


def enrich_deals(deals: list[dict[str, Any]], fresh: list[dict[str, Any]]) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    history = load_history()
    record_observations(history, fresh)

    observed_ids = {str(d.get("id")) for d in fresh if d.get("id")}
    for d in deals:
        d.update(product_identity(d))
        d["status"] = status_for(d, observed_ids)

    # Current market groups. Restrict market comparisons to identities with decent confidence.
    groups: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for d in deals:
        if d.get("status") in {"active", "recently_missing"} and num(d.get("price")) and num(d.get("match_confidence"), 0) >= .70:
            groups[d["product_key"]].append(d)

    for d in deals:
        hm = history_metrics(history, d["product_key"])
        d.update(hm)
        normal = hm["historical_median"]
        d["normal_street_price"] = normal
        price = num(d.get("price"))
        d["real_discount_percent"] = round((normal - price) / normal * 100, 2) if price and normal and normal > 0 else None

        peers = [x for x in groups.get(d["product_key"], []) if x.get("retailer") != d.get("retailer") and num(x.get("price"))]
        peer_prices = [num(x.get("price")) for x in peers]
        peer_prices = [p for p in peer_prices if p is not None]
        d["competitor_count"] = len(peer_prices)
        d["market_average"] = round(statistics.mean(peer_prices), 2) if peer_prices else None
        d["competitor_low"] = round(min(peer_prices), 2) if peer_prices else None

        was = num(d.get("was_price"))
        advertised = num(d.get("discount_percent"), 0.0) or 0.0
        benchmark_candidates = [x for x in [normal, d.get("market_average")] if num(x)]
        benchmark = statistics.median([num(x) for x in benchmark_candidates]) if benchmark_candidates else None
        real = d.get("real_discount_percent")
        d["suspected_inflated_rrp"] = bool(
            was and benchmark and was > benchmark * 1.20 and advertised >= 15 and (real is None or advertised - real >= 10)
        )
        d["new_historical_low"] = bool(price and hm["historical_low"] and price <= hm["historical_low"] * 1.001 and hm["history_samples"] >= 2)
        score_deal(d)

    save_history(history)
    meta = {
        "tracked_products": len(history.get("products", {})),
        "history_observations": sum(len(p.get("observations", [])) for p in history.get("products", {}).values()),
        "products_with_history": sum(1 for d in deals if (d.get("history_samples") or 0) >= 2),
        "cross_retailer_matches": sum(1 for d in deals if (d.get("competitor_count") or 0) >= 1),
        "new_historical_lows": sum(1 for d in deals if d.get("new_historical_low")),
        "inflated_rrp_flags": sum(1 for d in deals if d.get("suspected_inflated_rrp")),
    }
    return deals, meta
