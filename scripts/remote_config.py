from __future__ import annotations
import os, requests

DEFAULTS = {
    "good_deal_score_threshold": 75,
    "discord_price_drop_percent": 3,
    "discord_score_improvement": 8,
    "scan_interval_hours": 6,
    "market": "AU",
    "currency": "AUD",
}


def _headers():
    key=os.getenv("SUPABASE_SECRET_KEY") or os.getenv("SUPABASE_SERVICE_ROLE_KEY")
    return {"apikey": key, "Authorization": f"Bearer {key}", "Content-Type":"application/json"} if key else None


def load_remote_config() -> dict:
    cfg=dict(DEFAULTS)
    url=os.getenv("SUPABASE_URL", "").rstrip("/")
    headers=_headers()
    if not url or not headers:
        return cfg
    try:
        r=requests.get(f"{url}/rest/v1/app_settings?select=key,value",headers=headers,timeout=15)
        r.raise_for_status()
        for row in r.json(): cfg[row["key"]]=row["value"]
    except Exception as exc:
        print(f"Remote settings unavailable; using defaults: {exc}")
    return cfg


def load_source_controls() -> dict[str,bool]:
    url=os.getenv("SUPABASE_URL", "").rstrip("/")
    headers=_headers()
    if not url or not headers: return {}
    try:
        r=requests.get(f"{url}/rest/v1/source_controls?select=source_key,enabled",headers=headers,timeout=15)
        r.raise_for_status()
        return {x["source_key"]: bool(x["enabled"]) for x in r.json()}
    except Exception as exc:
        print(f"Remote source controls unavailable: {exc}")
        return {}


def load_admin_rules() -> tuple[list[dict], list[dict]]:
    url=os.getenv("SUPABASE_URL", "").rstrip("/")
    headers=_headers()
    if not url or not headers: return [], []
    try:
        w=requests.get(f"{url}/rest/v1/watchlist?select=*&enabled=eq.true",headers=headers,timeout=15); w.raise_for_status()
        b=requests.get(f"{url}/rest/v1/blocked_deals?select=*",headers=headers,timeout=15); b.raise_for_status()
        return w.json(), b.json()
    except Exception as exc:
        print(f"Remote admin rules unavailable: {exc}")
        return [], []

def apply_admin_rules(deals: list[dict], watchlist: list[dict], blocks: list[dict]) -> tuple[list[dict], int]:
    out=[]; blocked=0
    block_patterns=[str(x.get("pattern") or "").lower() for x in blocks if x.get("pattern")]
    for d in deals:
        hay=f"{d.get('title','')} {d.get('model','')} {d.get('retailer','')}".lower()
        if any(p in hay for p in block_patterns): blocked += 1; continue
        pref=0
        for w in watchlist:
            q=str(w.get("query") or "").lower()
            if q and q in hay:
                price=d.get("price")
                maxp=w.get("max_price_aud")
                mind=w.get("min_discount_percent") or 0
                if (maxp is None or price is None or float(price)<=float(maxp)) and float(d.get("discount_percent") or 0)>=float(mind):
                    pref=max(pref,5)
        if pref: d["preference_score"]=pref; d["watchlist_match"]=True
        out.append(d)
    return out, blocked
