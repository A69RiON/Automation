# AU Deal Hunter

GitHub-hosted Australian deal dashboard with two non-destructive views:

- **Good Deals** — intelligent ranked view.
- **All Discounts** — every collected promotion, even when the Deal Score is poor.

## Current status

Phase 1 and the initial Phase 2 implementation are included. See `PHASES.md`.

## Current collectors

- OzBargain `/deals/feed`
- eBay AU Browse API (credentials required)
- Mwave promotion + clearance pages
- Scorptec promotions + clearance pages
- Centre Com promotions + hot deals + clearance pages
- Umart hot deals + promotions + clearance pages

Retailer HTML adapters intentionally report `warning` when pages are fetched but no structured product data can be extracted. They do not pretend that a scan succeeded.

## GitHub setup

1. Create/push to a GitHub repository.
2. **Settings → Pages → Deploy from a branch**, choose your default branch and `/docs`.
3. In **Settings → Secrets and variables → Actions**, add eBay credentials when available:
   - `EBAY_CLIENT_ID`
   - `EBAY_CLIENT_SECRET`
4. Optional repository variable:
   - `EBAY_SEARCH_QUERIES` — pipe-separated discovery queries.
5. Enable Actions. The included workflow runs every six hours at minute 17 UTC and can also be triggered manually.

## Security

Never commit API secrets, browser cookies, Amazon credentials or Discord webhook URLs. Phase 4 reads the Discord webhook from a GitHub Actions secret.

## Source layout

```text
scripts/
  collector.py
  sources/
    common.py
    ozbargain.py
    ebay.py
    generic_retailer.py
```

Each source returns normalized deals plus a health record. A failed source cannot erase previously collected records; stale records are retained temporarily and visibly age in the dashboard.

## Amazon

Amazon's current direct programmatic product path is Creators API. Direct Amazon support will be connected only against valid Creators API credentials/onboarding rather than hard-coding or scraping around the supported integration. OzBargain-sourced Amazon deals can still enter the dashboard in the meantime.
