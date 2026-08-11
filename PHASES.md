# AU Deal Hunter — implementation phases

## Phase 1 — Dashboard foundation ✅
- GitHub Pages static dashboard
- Good Deals and All Discounts tabs
- Search, category, retailer and sort controls
- Deal-score explanation UI

## Phase 2 — Real data collection ✅ initial implementation
- Pluggable source-adapter framework
- OzBargain RSS collector
- eBay AU Browse API collector (requires GitHub secrets)
- Public promotion/clearance page adapters for Mwave, Scorptec, Centre Com and Umart
- Normalized schema and non-destructive merge
- Source-health reporting in dashboard
- Six-hour GitHub Actions schedule
- Stale-data retention when a source temporarily fails

### Phase 2 limitations to address in later iterations
- Retailers that client-render product grids may need dedicated parsers or Playwright fallback.
- Amazon direct collection requires Amazon Associates / Creators API onboarding and credentials. OzBargain can still surface Amazon-linked deals meanwhile.
- Broad marketplace discovery is not equivalent to enumerating literally every SKU on a marketplace; source-specific APIs impose discovery/query constraints.

## Phase 3 — Deal intelligence ⏳
- SQLite/JSON price history persisted between GitHub Action runs
- Product/model normalization across retailers
- Cross-retailer matching and market average
- Historical low / normal street price
- Inflated-RRP detection
- Improved Deal Score
- Expiry/status logic

## Phase 4 — Alerts and automation ⏳
- Discord webhook for Good Deals
- Duplicate-notification suppression
- Re-alert on meaningful price drop/improvement
- Normal six-hour schedule
- More aggressive Black Friday/Cyber Monday schedule
- Failure notifications / workflow observability

## Phase 5 — Production hardening ⏳
- Dedicated source adapters for additional AU retailers
- Retry/backoff and anti-breakage tests
- Mobile dashboard refinement
- Manual refresh workflow
- Configuration documentation
- End-to-end validation
