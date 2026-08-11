from __future__ import annotations

import re
import time
import xml.etree.ElementTree as ET
from datetime import datetime
from email.utils import parsedate_to_datetime
from urllib.parse import urljoin

import requests

from .common import SourceHealth, infer_prices, make_deal, clean_text, retailer_from_url, utcnow_iso


class OzBargainSource:
    name = "OzBargain"
    feed_url = "https://www.ozbargain.com.au/deals/feed"

    def collect(self) -> tuple[list[dict], SourceHealth]:
        started = time.perf_counter()
        try:
            r = requests.get(self.feed_url, timeout=25, headers={"User-Agent": "AU-Deal-Hunter/1.0 (+GitHub Actions)"})
            r.raise_for_status()
            root = ET.fromstring(r.content)
            deals: list[dict] = []
            for item in root.findall(".//item"):
                title = clean_text(item.findtext("title"))
                link = clean_text(item.findtext("link"))
                desc = clean_text(item.findtext("description"))
                pub = clean_text(item.findtext("pubDate"))
                first_seen = utcnow_iso()
                if pub:
                    try:
                        first_seen = parsedate_to_datetime(pub).isoformat()
                    except Exception:
                        pass
                combined = f"{title} {desc}"
                price, was, pct = infer_prices(combined)

                # OzBargain itself is the source; infer merchant from title suffix such as "@ Amazon AU".
                retailer = "OzBargain-listed deal"
                m = re.search(r"\s@\s([^|\[\]]+?)(?:\s\[|$)", title)
                if m:
                    retailer = clean_text(m.group(1))

                # Keep all feed deals, even if the feed title does not expose a numerical discount.
                deals.append(make_deal(
                    source=self.name, title=title, url=link, retailer=retailer,
                    price=price, was_price=was, discount_percent=pct, first_seen=first_seen,
                    extra={"community_source": "OzBargain"}
                ))
            latency = round((time.perf_counter() - started) * 1000)
            return deals, SourceHealth(self.name, "ok", utcnow_iso(), len(deals), "RSS feed parsed", latency)
        except Exception as exc:
            latency = round((time.perf_counter() - started) * 1000)
            return [], SourceHealth(self.name, "error", utcnow_iso(), 0, f"{type(exc).__name__}: {exc}", latency)
