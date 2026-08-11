from __future__ import annotations

import base64
import os
import time
from typing import Iterable

import requests

from .common import SourceHealth, make_deal, parse_money, utcnow_iso


class EbaySource:
    name = "eBay AU"
    token_url = "https://api.ebay.com/identity/v1/oauth2/token"
    search_url = "https://api.ebay.com/buy/browse/v1/item_summary/search"

    DEFAULT_QUERIES = [
        "black friday", "clearance", "deal", "sale",
        "laptop", "ssd", "monitor", "graphics card", "router", "headphones",
        "phone", "tablet", "tv", "vacuum", "gaming", "camera"
    ]

    def __init__(self, queries: Iterable[str] | None = None):
        self.client_id = os.getenv("EBAY_CLIENT_ID", "").strip()
        self.client_secret = os.getenv("EBAY_CLIENT_SECRET", "").strip()
        configured = os.getenv("EBAY_SEARCH_QUERIES", "").strip()
        self.queries = list(queries or ([q.strip() for q in configured.split("|") if q.strip()] if configured else self.DEFAULT_QUERIES))

    def _token(self) -> str:
        auth = base64.b64encode(f"{self.client_id}:{self.client_secret}".encode()).decode()
        r = requests.post(
            self.token_url,
            headers={"Authorization": f"Basic {auth}", "Content-Type": "application/x-www-form-urlencoded"},
            data={"grant_type": "client_credentials", "scope": "https://api.ebay.com/oauth/api_scope"},
            timeout=25,
        )
        r.raise_for_status()
        return r.json()["access_token"]

    def collect(self) -> tuple[list[dict], SourceHealth]:
        started = time.perf_counter()
        if not self.client_id or not self.client_secret:
            return [], SourceHealth(self.name, "not_configured", utcnow_iso(), 0, "Add EBAY_CLIENT_ID and EBAY_CLIENT_SECRET GitHub secrets")
        try:
            token = self._token()
            headers = {
                "Authorization": f"Bearer {token}",
                "X-EBAY-C-MARKETPLACE-ID": "EBAY_AU",
                "Accept": "application/json",
            }
            by_id: dict[str, dict] = {}
            for q in self.queries:
                r = requests.get(self.search_url, headers=headers, params={"q": q, "limit": 50}, timeout=25)
                r.raise_for_status()
                for item in r.json().get("itemSummaries", []):
                    price = parse_money((item.get("price") or {}).get("value"))
                    marketing = item.get("marketingPrice") or {}
                    was = parse_money((marketing.get("originalPrice") or {}).get("value"))
                    pct = parse_money(marketing.get("discountPercentage"))
                    # "All Discounts" means we keep an item only when eBay supplies a promotion signal,
                    # otherwise broad keyword queries would turn the dashboard into an ordinary search result page.
                    if was is None and pct is None:
                        continue
                    url = item.get("itemWebUrl") or item.get("itemAffiliateWebUrl") or "https://www.ebay.com.au/"
                    title = item.get("title") or "eBay deal"
                    item_id = item.get("itemId")
                    extra = {
                        "seller": (item.get("seller") or {}).get("username"),
                        "condition": item.get("condition"),
                        "currency": ((item.get("price") or {}).get("currency") or "AUD"),
                        "market": "AU",
                    }
                    if item_id:
                        extra["id"] = f"ebay-{item_id}"
                    deal = make_deal(
                        source=self.name, title=title, url=url, retailer="eBay AU",
                        price=price, was_price=was, discount_percent=pct, extra=extra,
                    )
                    by_id[item_id or url] = deal
            latency = round((time.perf_counter() - started) * 1000)
            return list(by_id.values()), SourceHealth(self.name, "ok", utcnow_iso(), len(by_id), f"Browse API; {len(self.queries)} discovery queries", latency)
        except Exception as exc:
            latency = round((time.perf_counter() - started) * 1000)
            return [], SourceHealth(self.name, "error", utcnow_iso(), 0, f"{type(exc).__name__}: {exc}", latency)
