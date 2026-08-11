# AU Deal Hunter — Phase 5 Production Build

Australia-first deal intelligence dashboard with AUD enforcement, secure Supabase-backed admin controls, Discord Good Deal alerts, price history and scheduled GitHub Actions collection.

See `PHASE5_SETUP.md` for deployment.

# AU Deal Hunter — Phase 4

GitHub-hosted Australian deal dashboard with two independent views:

1. **Good Deals** — price-intelligence-ranked promotions.
2. **All Discounts** — every detected promotion, including weaker advertised discounts.

Phase 4 adds automated Discord webhook alerts and durable duplicate suppression.

## Automation

`.github/workflows/refresh-deals.yml` runs every six hours at minute 17 and can also be started manually from GitHub Actions. It collects deals, updates price history, evaluates Good Deals, sends eligible Discord alerts, writes dashboard data, and commits the updated history files.

## Required Discord setup

Create a Discord webhook in the target channel, then add the URL to GitHub as an **Actions repository secret** named exactly:

`DISCORD_WEBHOOK_URL`

Do not put the real webhook URL in this repository, `config.example.env`, HTML, JavaScript, JSON, or screenshots shared publicly.

### Optional GitHub Actions repository variables

- `DISCORD_DEAL_SCORE_THRESHOLD` — default `75`
- `DISCORD_REALERT_PRICE_DROP_PERCENT` — default `3`
- `DISCORD_REALERT_SCORE_IMPROVEMENT` — default `8`

If these variables are absent, the Python defaults above are used.

## Duplicate/re-alert policy

`data/alert-history.json` stores only alert metadata — never the webhook secret. A qualifying deal is sent the first time. It is suppressed on later scans unless the price drops by the configured threshold or the Deal Score improves materially.

## eBay

Optional secrets:
- `EBAY_CLIENT_ID`
- `EBAY_CLIENT_SECRET`

Optional variable:
- `EBAY_SEARCH_QUERIES`

## GitHub Pages

The static dashboard is under `/docs`. If your GitHub plan supports Pages for the repository visibility you chose, configure Pages to deploy the `main` branch `/docs` folder.

## Phase 5

Production hardening will expand dedicated retailer adapters, retries/backoff, expired-deal handling, Black Friday higher-frequency scanning and deployment diagnostics.
