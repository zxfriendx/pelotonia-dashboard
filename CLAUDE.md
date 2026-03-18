# Pelotonia Dashboard & Scraper

## Project Purpose
Fundraising analytics dashboard and automated data collection for a Pelotonia team.
Data is sourced from the Pelotonia API, PledgeIt campaign page, and organization endpoints.

## Structure
- `app/` — Application code:
  - `pelotonia_scraper.py` — Scrapes Pelotonia API for team/member/donation/route data into SQLite
  - `pledgeit_scraper.py` — Scrapes aggregate Pelotonia Kids stats from PledgeIt campaign page
  - `org_scraper.py` — Scrapes aggregate stats for ~31 top Pelotonia parent organizations from the API
  - `pelotonia_data.db` — SQLite database (teams, members, donations, member_routes, daily_snapshots, events, routes, rides, donor_identities, kids_snapshots, org_snapshots)
  - `dashboard.py` — Flask dashboard (port 5050) with fundraising, routes, members, donor analytics, kids tracking
  - `daily_report.py` — Daily/weekly email report with HTML + PNG infographic attachment, sent via SMTP
  - `SCRAPER.md` — Scraper technical guide
- `k8s/` — Draft Kubernetes manifests (Deployment, CronJob, PVC)
- `Dockerfile` — Container image (python:3.12-slim + Flask + scrapers)
- `.gcloudignore` — Cloud Build file filter
- `deploy-gcp.sh` — Build + deploy script for GCP Cloud Run

## Environment Variables
| Variable | Used By | Description |
|----------|---------|-------------|
| `PELOTONIA_DB` | All scripts | Path to SQLite database (default: `app/pelotonia_data.db`) |
| `GMAIL_APP_PASSWORD` | daily_report.py | Gmail app password for SMTP |
| `GMAIL_SENDER` | daily_report.py | Sender email address |
| `REPORT_RECIPIENT` | daily_report.py | Report recipient email |
| `REPORT_SENDER_NAME` | daily_report.py | Display name for sender (default: "Pelotonia Dashboard") |

## Key Numbers (update when new data arrives)
- All-time raised: $339M (through 2025)
- 2025 total: $29.2M (record)
- PIIO investment: $102.2M
- Scholars: 734 from 53 countries

## Scraper Details
- **API**: `https://pelotonia-p3-middleware-production.azurewebsites.net/api/`
- **Pagination**: Header-based (`Pagination-Page`, `Pagination-Limit`)
- **Incremental mode**: `--incremental` refreshes teams+members (~34 API calls when stable), plus profiles for new/stale/old (7+ days) members, re-fetches routes for refreshed members, and donations only for members whose raised amount changed. Full scrape ~4min.
- **Backfill mode**: `--backfill-donations` fetches donations for members with raised > 0 but no donation records (one-time catch-up)
- **Atomic commits**: All scrape changes committed in a single transaction at the end, preventing dashboard from serving partial data mid-scrape
- **Daily snapshots**: `daily_snapshots` table tracks fundraising totals per team per day
- **Route freshness**: Incremental mode clears and re-fetches routes for members whose profiles are refreshed, preventing stale route entries
- **goal_override**: Column included in CREATE TABLE schema and preserved by ON CONFLICT UPDATE (scraper never overwrites it)

## Dashboard Details
- **Primary endpoint**: `/api/bundle` — returns all 20 data sets in one response, used by the frontend
- **Cache**: mtime-based — the bundle is rebuilt only when `pelotonia_data.db`'s file mtime changes
- **Individual endpoints** (`/api/overview`, `/api/teams`, etc.) still work independently for ad-hoc queries

### Tabs (11 total)
- **Overview**: Goals panel (editable targets via localStorage, general peloton funds footnote), Fundraising Growth chart, Participant Signups Over Time chart, Participant Types by Sub-Team chart, Raised by Sub-Team chart
- **Teams**: 2026 Goals & Progress table (all sub-teams), Participant Types by Sub-Team chart, Raised by Sub-Team chart
- **Routes & Events**: Signature Ride & Gravel Day signup totals + route tables with member drill-down modals
- **Members**: KPI cards (member count, unique donors, avg donors/member), searchable/sortable member table with donation modals, cross-tab navigation from other tabs
- **Donors**: Top donors table with recipient breakdown modals
- **Companies**: Corporate donor analytics
- **Donations**: Donation feed table with search
- **Infographics**: Thermometer-style visualizations per team, editable targets via localStorage, campaign timeline calculations, prior-year benchmarking
- **Daily Report**: Email-style report view with daily/weekly toggle, sub-team filter, KPI cards, top movers, sub-team participation table
- **Pelotonia Kids**: 5 KPIs (fundraisers, raised, goal, progress %, teams) + 2 line charts from PledgeIt campaign data
- **Leaderboard**: Organization comparison — 4 KPIs, sortable table, top-15 bar chart

### Chart Features
- Chart.js with chartjs-plugin-datalabels
- Participant Types chart: stacked horizontal bars, labels shown for segments >= 5
- Raised by Sub-Team chart: horizontal bars, $Xk labels for bars >= $1,000
- Fundraising Growth: line chart from daily_snapshots
- Participant Signups Over Time: line chart from daily_snapshots

### Responsive Design
- Three CSS breakpoints — 900px (grid collapse), 768px (scrollable tab bar), 600px (full mobile)
- Cards use `min-width: 0; overflow: hidden` to prevent CSS grid overflow
- Chart containers use `max-width: 100%`

### Cross-tab Interactions
- Fundraiser rows → Members tab (highlight + scroll)
- Member rows → donation modal
- Donor rows → recipient breakdown modal
- Route rows → member list modal
- Members tab search bar has X Clear button when filter active
- Members table sorted by 2026 raised (descending)

## Deployment

### GCP Cloud Run
- **deploy-gcp.sh**: `gcloud builds submit` + `gcloud run deploy` (Cloud Run, us-central1, 256Mi, max 2 instances)
- **Container**: Bakes SQLite DB into image (no external DB). Updated daily via auto-deploy.

### Kubernetes
- `k8s/pvc.yaml` — PersistentVolumeClaim for SQLite
- `k8s/deployment.yaml` — Dashboard Deployment + Service
- `k8s/cronjob.yaml` — Daily scraper CronJob
- Set `PELOTONIA_DB=/data/pelotonia_data.db` to read from persistent volume

## Daily & Weekly Email Reports
- **Script**: `app/daily_report.py` — queries SQLite, builds HTML email + PNG infographic, sends via SMTP
- **Config**: Set `GMAIL_SENDER`, `GMAIL_APP_PASSWORD`, and `REPORT_RECIPIENT` env vars
- **Content**: 4 infographic cards (funds/riders/challengers/volunteers) in 2x2 grid, goal, top movers, participation by sub-team table
- **Weekly mode**: `--weekly` flag computes 7-day deltas instead of 1-day, shows 5 movers instead of 3
- **Image**: Pillow-rendered PNG attached to email (680px wide, lossless)
- **Manual run**: `python app/daily_report.py --send [--to email] [--weekly]`
- **Preview**: `python app/daily_report.py --preview --output report.html [--weekly]`

## Pelotonia Kids Scraper
- **Script**: `app/pledgeit_scraper.py` — scrapes aggregate stats from PledgeIt campaign page
- **Data**: Aggregate only (fundraiser count, amount raised, goal, team count) — no PII
- **Method**: Extracts `__NEXT_DATA__` JSON from Next.js page, parses Apollo cache
- **Storage**: `kids_snapshots` table in `pelotonia_data.db`
- **Usage**: `python app/pledgeit_scraper.py` (scrape) / `--summary` (print latest)
- **Dependencies**: stdlib only (urllib, json, re, sqlite3)

## Organization Leaderboard Scraper
- **Script**: `app/org_scraper.py` — fetches aggregate stats for ~31 parent Pelotonia organizations
- **API**: Uses `peloton/{id}` endpoint per org (hardcoded IDs, 0.5s rate limiting, ~15s total)
- **Storage**: `org_snapshots` table in `pelotonia_data.db` — one row per org per day
- **Usage**: `python app/org_scraper.py` (scrape) / `--summary` (print leaderboard)
- **Dependencies**: stdlib only

## Conventions
- All monetary figures use full precision where available
- Dates in YYYY-MM-DD format

## Known Issues
1. **Hidden donor lists** — Some members have raised > 0 but `is_donor_list_visible=0`, so their individual donation records can't be fetched via the API. Their totals are reflected in `members.raised` but not in the `donations` table.
2. **General peloton funds gap** — The parent team's `raised` includes `general_peloton_funds` not attributed to individual members. Surfaced as a footnote on the Overview goals panel.
