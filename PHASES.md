# AU Deal Hunter implementation phases

## Phase 1 — Dashboard foundation ✅
GitHub Pages dashboard, Good Deals tab, All Discounts tab, search/filter/sort and score display.

## Phase 2 — Data collection ✅ initial implementation
Source adapter architecture, OzBargain, eBay API support, retailer adapters, source-health reporting and non-destructive retention.

## Phase 3 — Deal intelligence ✅
Persistent price history, product matching, competitor comparison, observed street price, real discount, historical lows, confidence and RRP anomaly detection.

## Phase 4 — Discord + full automation ✅
- Six-hour GitHub Actions schedule
- Discord webhook integration via GitHub Actions secret
- Good Deals only
- Configurable minimum Deal Score
- Duplicate suppression
- Price-drop re-alerts
- Score-improvement re-alerts
- Persistent alert history
- Discord status visible on the dashboard
- Manual workflow trigger remains available for testing

Default alert policy:
- Good Deal must be active and score >= 75
- Same deal/price is not repeatedly posted
- Re-alert when price falls by at least 3% from the last alerted price
- Re-alert when Deal Score improves by at least 8 points

## Phase 5 — Production hardening ⏭️
Dedicated retailer adapters, expired-deal cleanup, resilient retries/backoff, broader source coverage, Black Friday high-frequency mode, deployment diagnostics and final operational runbook.


## Phase 5 — Production / AU Admin (implemented foundation)
- AU-only/AUD enforcement
- Supabase Auth + RLS admin control centre
- Source enable/disable controls
- Watchlist and blocked-listing rules
- Remote deal/Discord settings
- eBay AU official API path
- Amazon AU Creators API credential-gated adapter
- GitHub Actions secrets integration
