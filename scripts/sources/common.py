from __future__ import annotations

import hashlib
import html
import json
import re
from dataclasses import dataclass, asdict
from datetime import datetime, timezone
from typing import Any
from urllib.parse import urlparse

PRICE_RE = re.compile(r"(?:A\$|AU\$|\$)\s*([0-9][0-9,]*(?:\.\d{1,2})?)")
PERCENT_RE = re.compile(r"(?<!\d)(\d{1,2}(?:\.\d+)?)\s*%\s*(?:off|discount)?", re.I)
SAVE_RE = re.compile(r"\b(?:save|saving)\s*(?:A\$|AU\$|\$)?\s*([0-9][0-9,]*(?:\.\d{1,2})?)", re.I)
WAS_RE = re.compile(r"\b(?:was|rrp|normally|regular(?:ly)?|from)\s*[:\-]?\s*(?:A\$|AU\$|\$)\s*([0-9][0-9,]*(?:\.\d{1,2})?)", re.I)


def utcnow_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def clean_text(value: Any) -> str:
    text = html.unescape(str(value or ""))
    text = re.sub(r"<[^>]+>", " ", text)
    return re.sub(r"\s+", " ", text).strip()


def parse_money(value: Any) -> float | None:
    if value is None:
        return None
    if isinstance(value, (int, float)):
        return float(value)
    m = re.search(r"([0-9][0-9,]*(?:\.\d{1,2})?)", str(value))
    return float(m.group(1).replace(",", "")) if m else None


def infer_prices(text: str) -> tuple[float | None, float | None, float | None]:
    """Return current price, was price, advertised discount percent when inferable."""
    t = clean_text(text)
    prices = [float(x.replace(",", "")) for x in PRICE_RE.findall(t)]
    current = prices[0] if prices else None
    was_match = WAS_RE.search(t)
    was = float(was_match.group(1).replace(",", "")) if was_match else None
    pct_match = PERCENT_RE.search(t)
    pct = float(pct_match.group(1)) if pct_match else None
    save_match = SAVE_RE.search(t)
    save = float(save_match.group(1).replace(",", "")) if save_match else None

    if current is not None and was is None and save:
        was = current + save
    if current is not None and was is None and pct and pct < 100:
        was = current / (1 - pct / 100)
    if current is not None and was is not None and was > current and pct is None:
        pct = ((was - current) / was) * 100
    return current, was, pct


def stable_id(source: str, url: str, title: str) -> str:
    raw = f"{source}|{url}|{title}".lower().encode("utf-8")
    return f"{source.lower().replace(' ','-')}-{hashlib.sha1(raw).hexdigest()[:16]}"


def retailer_from_url(url: str) -> str:
    host = urlparse(url).netloc.lower().replace("www.", "")
    known = {
        "amazon.com.au": "Amazon AU",
        "ebay.com.au": "eBay AU",
        "mwave.com.au": "Mwave",
        "scorptec.com.au": "Scorptec",
        "centrecom.com.au": "Centre Com",
        "umart.com.au": "Umart",
        "jbhifi.com.au": "JB Hi-Fi",
        "officeworks.com.au": "Officeworks",
        "thegoodguys.com.au": "The Good Guys",
        "harveynorman.com.au": "Harvey Norman",
        "bigw.com.au": "BIG W",
        "target.com.au": "Target",
        "myer.com.au": "Myer",
        "davidjones.com": "David Jones",
    }
    for domain, name in known.items():
        if host.endswith(domain):
            return name
    return host or "Unknown retailer"


def category_guess(title: str) -> str:
    t = title.lower()
    rules = [
        ("Storage", ["ssd", "nvme", "hard drive", "hdd", "micro sd", "microsd"]),
        ("Graphics", ["rtx ", "radeon", "graphics card", " gpu"]),
        ("Processors", ["ryzen", "core i5", "core i7", "core i9", " cpu"]),
        ("Monitors", ["monitor", "oled display"]),
        ("Networking", ["router", "switch", "wifi", "wi-fi", "unifi", "ubiquiti", "ethernet"]),
        ("Laptops", ["laptop", "macbook", "notebook"]),
        ("Phones", ["iphone", "galaxy s", "pixel ", "smartphone"]),
        ("Gaming", ["playstation", "xbox", "nintendo", "gaming"]),
        ("Home", ["vacuum", "air fryer", "fridge", "washing machine", "dryer", "coffee machine"]),
    ]
    for cat, needles in rules:
        if any(n in t for n in needles):
            return cat
    return "Other"


@dataclass
class SourceHealth:
    source: str
    status: str
    checked_at: str
    deals_found: int = 0
    message: str = ""
    latency_ms: int | None = None

    def dict(self) -> dict[str, Any]:
        return asdict(self)


def make_deal(*, source: str, title: str, url: str, retailer: str | None = None,
              price: float | None = None, was_price: float | None = None,
              discount_percent: float | None = None, category: str | None = None,
              first_seen: str | None = None, extra: dict[str, Any] | None = None) -> dict[str, Any]:
    title = clean_text(title)
    d: dict[str, Any] = {
        "id": stable_id(source, url, title),
        "source": source,
        "title": title,
        "model": None,
        "retailer": retailer or retailer_from_url(url),
        "category": category or category_guess(title),
        "price": price,
        "was_price": was_price,
        "discount_percent": round(discount_percent, 2) if discount_percent is not None else None,
        "historical_low": None,
        "market_average": None,
        "deal_score": 0,
        "good_deal": False,
        "ozbargain_votes": None,
        "suspected_inflated_rrp": False,
        "first_seen": first_seen or utcnow_iso(),
        "last_seen": utcnow_iso(),
        "url": url,
        "score_breakdown": {},
    }
    if extra:
        d.update(extra)
    return d


def extract_jsonld_products(soup: Any) -> list[dict[str, Any]]:
    products: list[dict[str, Any]] = []
    for script in soup.find_all("script", attrs={"type": "application/ld+json"}):
        raw = script.string or script.get_text(" ", strip=True)
        if not raw:
            continue
        try:
            obj = json.loads(raw)
        except Exception:
            continue
        stack = obj if isinstance(obj, list) else [obj]
        while stack:
            item = stack.pop()
            if isinstance(item, list):
                stack.extend(item)
                continue
            if not isinstance(item, dict):
                continue
            if "@graph" in item:
                stack.append(item["@graph"])
            if item.get("@type") == "Product" or (isinstance(item.get("@type"), list) and "Product" in item["@type"]):
                products.append(item)
    return products
