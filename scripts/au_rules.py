from __future__ import annotations

AU_DOMAINS = (
    ".com.au", ".net.au", ".org.au", "amazon.com.au", "ebay.com.au", "ozbargain.com.au"
)


def enforce_au_deal(deal: dict) -> tuple[bool, str]:
    """Reject non-AUD/non-AU listings before they reach the dashboard.

    Missing currency is allowed for feeds whose source is explicitly Australian,
    but explicit non-AUD currency is rejected.
    """
    currency = str(deal.get("currency") or "AUD").upper()
    if currency != "AUD":
        return False, f"currency={currency}"
    url = str(deal.get("url") or "").lower()
    retailer = str(deal.get("retailer") or "").lower()
    source = str(deal.get("source") or "").lower()
    trusted_au = any(x in retailer or x in source for x in ("au", "ozbargain", "mwave", "scorptec", "centre com", "umart"))
    domain_au = any(d in url for d in AU_DOMAINS)
    if not trusted_au and url and not domain_au:
        return False, "non-AU URL/source"
    deal["currency"] = "AUD"
    deal["market"] = "AU"
    return True, "ok"
