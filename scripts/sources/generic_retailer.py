from __future__ import annotations

import re
import time
from urllib.parse import urljoin

import requests
from bs4 import BeautifulSoup

from .common import SourceHealth, extract_jsonld_products, infer_prices, make_deal, parse_money, utcnow_iso


class GenericRetailerSource:
    """Best-effort public sale-page adapter.

    It first consumes Product JSON-LD. If the retailer renders products only through client-side
    JavaScript, the health result will say zero extracted rather than fabricating completeness.
    Phase 2 keeps this HTTP-only; Playwright fallback can be added source-by-source if necessary.
    """

    def __init__(self, name: str, urls: list[str]):
        self.name = name
        self.urls = urls

    def collect(self) -> tuple[list[dict], SourceHealth]:
        started = time.perf_counter()
        deals: dict[str, dict] = {}
        errors: list[str] = []
        pages_ok = 0
        for page_url in self.urls:
            try:
                r = requests.get(page_url, timeout=30, headers={
                    "User-Agent": "Mozilla/5.0 (compatible; AUDealHunter/1.0; +https://github.com/)"
                })
                r.raise_for_status()
                pages_ok += 1
                soup = BeautifulSoup(r.text, "html.parser")
                for p in extract_jsonld_products(soup):
                    title = p.get("name") or ""
                    offers = p.get("offers") or {}
                    if isinstance(offers, list):
                        offers = offers[0] if offers else {}
                    price = parse_money(offers.get("price") or offers.get("lowPrice"))
                    url = urljoin(page_url, p.get("url") or offers.get("url") or "")
                    # JSON-LD rarely exposes was-price; inspect nearby product text when present.
                    text = f"{title} {p.get('description','')}"
                    inferred_current, was, pct = infer_prices(text)
                    price = price or inferred_current
                    if not title or price is None:
                        continue
                    # Generic sale pages may not expose numerical old price; retain product because
                    # its presence on the retailer's dedicated promotion/clearance page is itself a deal signal.
                    d = make_deal(source=self.name, title=title, url=url or page_url, retailer=self.name,
                                  price=price, was_price=was, discount_percent=pct,
                                  extra={"promotion_page": page_url})
                    deals[d["id"]] = d
            except Exception as exc:
                errors.append(f"{page_url}: {type(exc).__name__}: {exc}")
        latency = round((time.perf_counter() - started) * 1000)
        if pages_ok == 0:
            return [], SourceHealth(self.name, "error", utcnow_iso(), 0, "; ".join(errors)[:800], latency)
        if deals:
            msg = f"{pages_ok}/{len(self.urls)} pages fetched; JSON-LD products extracted"
            if errors:
                msg += f"; {len(errors)} page errors"
            status = "ok" if not errors else "partial"
        else:
            msg = f"{pages_ok}/{len(self.urls)} pages fetched but no Product JSON-LD extracted; likely JS-rendered or promotion-only content"
            status = "warning"
        return list(deals.values()), SourceHealth(self.name, status, utcnow_iso(), len(deals), msg, latency)
