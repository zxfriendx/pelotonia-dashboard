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
- `frontend/` — React + TypeScript + Vite SPA (built to `frontend/dist/`, served by Flask)
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
- **Ticker API**: Same base URL + `/ticker` — returns `currentYearRaised`, `totalParticipants`, `allTimeRaised`. Dashboard maps these to `pelotonia_total_raised`, `pelotonia_member_count`, `pelotonia_all_time_raised`. Cached to `.ticker_cache.json` for resilience.
- **Pagination**: Header-based (`Pagination-Page`, `Pagination-Limit`)
- **Incremental mode**: `--incremental` refreshes teams+members (~34 API calls when stable), plus profiles for new/stale/old (7+ days) members, re-fetches routes for refreshed members, and donations only for members whose raised amount changed. Full scrape ~4min.
- **Backfill mode**: `--backfill-donations` fetches donations for members with raised > 0 but no donation records (one-time catch-up)
- **Atomic commits**: All scrape changes committed in a single transaction at the end, preventing dashboard from serving partial data mid-scrape
- **Busy timeout**: Scraper uses `timeout=30` and `busy_timeout=30000` on SQLite connection to coexist with Flask reads
- **Daily snapshots**: `daily_snapshots` table tracks fundraising totals per team per day
- **Route freshness**: Incremental mode clears and re-fetches routes for members whose profiles are refreshed, preventing stale route entries
- **goal_override**: Column included in CREATE TABLE schema and preserved by ON CONFLICT UPDATE (scraper never overwrites it)

## Dashboard Details
- **Primary endpoint**: `/api/bundle` — returns all 20 data sets in one response, used by the frontend
- **Cache**: mtime-based — the bundle is rebuilt only when `pelotonia_data.db`'s file mtime changes
- **Individual endpoints** (`/api/overview`, `/api/teams`, etc.) still work independently for ad-hoc queries
- **Frontend**: React SPA built to `frontend/dist/`, served by Flask's catch-all route

### KPI Strip (top cards)
- 3 flip cards: Raised (2026), All-Time Raised, Members — flip to show All Pelotonia totals from ticker API
- 5 simple cards: First Year Riders, Signature Riders, Gravel Riders, Cancer Survivors, High Rollers

### Tabs (11 total)
- **Overview**: Pelotonia-branded goals panel (editable targets via localStorage, campaign arrow asset, friendly timestamp), Fundraising Growth dual-axis chart (cumulative line + daily bars), Participant Signups Over Time (Riders/Challengers/Volunteers lines), Participant Types by Sub-Team chart, Raised by Sub-Team chart
- **Teams**: 2026 Goals & Progress table (all sub-teams), Participant Types by Sub-Team chart, Raised by Sub-Team chart
- **Routes & Events**: Signature Ride & Gravel Day signup totals + vertical bar chart (Raised vs Committed) + route tables with member drill-down modals
- **Members**: KPI cards (member count, unique donors, avg donors/member), searchable/sortable member table with donation modals, column header click-to-sort (Name, Sub-Team, Type, Years, Raised, All-Time), cross-tab navigation from other tabs
- **Donors**: Top donors table with recipient breakdown modals
- **Companies**: Corporate donor analytics with drill-down modal (matches by recognition_name)
- **Donations**: Donation feed table with search
- **Infographics**: Thermometer-style visualizations per team, editable targets via localStorage, campaign timeline calculations, prior-year benchmarking
- **Daily Report**: Email-style report view with daily/weekly toggle, sub-team filter, KPI cards, top movers, compact sub-team participation table
- **Pelotonia Kids**: 5 KPIs (fundraisers, raised, goal, progress %, teams) + 2 line charts from PledgeIt campaign data
- **Leaderboard**: Organization comparison — 4 KPIs, sortable table, top-15 bar chart

### Chart Features
- Chart.js with chartjs-plugin-datalabels (registered globally — all charts must explicitly set `datalabels: { display: false }` unless they use labels)
- Participant Types chart: stacked horizontal bars, labels shown only when text fits in segment (canvas pixel measurement via `measureText` + `xScale.getPixelForValue`)
- Raised by Sub-Team chart: horizontal bars, $Xk labels for bars >= $1,000
- Fundraising Growth: dual-axis chart — cumulative line (left y-axis) + daily bars (right y-axis)
- Participant Signups Over Time: multi-line chart — Total Members, Riders, Challengers, Volunteers
- Route Fundraising: vertical grouped bars (Raised vs Committed)

### Responsive Design
- Three CSS breakpoints — 900px (grid collapse), 768px (scrollable tab bar), 600px (full mobile)
- Cards use `min-width: 0; overflow: hidden` to prevent CSS grid overflow
- Chart containers use `max-width: 100%`

### Cross-tab Interactions
- Fundraiser rows → Members tab (highlight + scroll)
- Member rows → donation modal
- Donor rows → recipient breakdown modal
- Route rows → member list modal
- Company rows → donation detail modal (filtered by recognition_name)
- Members tab search bar has X Clear button when filter active
- Members table default sort: 2026 raised (descending), click headers to re-sort

### Brand Assets
- `frontend/public/pelotonia-arrow-green.png` — Cropped Pelotonia campaign arrow (main arrow only, no chevron accent), used in goals panel progress bars

## Deployment

### GCP Cloud Run (Production)
- **URL**: `https://pelotonia-dashboard-401340053598.us-central1.run.app/`
- **deploy-gcp.sh**: `gcloud builds submit` + `gcloud run deploy` (Cloud Run, us-central1, 256Mi, max 2 instances)
- **Container**: Bakes SQLite DB into image (no external DB). Updated daily via auto-deploy.

### Local Development Server
- **Access**: `http://100.101.251.71:5050/` via Tailscale (SSH'd into server)
- **Process**: Flask serves built frontend from `frontend/dist/`
- **Frontend build**: `(cd frontend && npm run build)` — rebuilds dist, Flask picks up new assets on next request
- **Vite dev server**: `(cd frontend && npm run dev)` — runs on port 5173 with API proxy to Flask on 5050
- **Backend restart**: Kill Flask process and re-run `app/.venv/bin/python app/dashboard.py --port 5050`

### Local Cron Jobs
Scrapers run 3× daily at 7am, 1pm, 7pm ET (11:00, 17:00, 23:00 UTC). Scrape and GCP deploy are chained in a single cron entry so the deploy waits for the scraper's atomic commit before packaging the SQLite DB into the container image (previously the deploy fired on a fixed timer and often bundled stale data).
```
0 11,17,23 * * * cd /home/zabx/source/pelotonia-dashboard && export PATH="$HOME/google-cloud-sdk/bin:$PATH" && app/.venv/bin/python app/pelotonia_scraper.py --incremental && app/.venv/bin/python app/pledgeit_scraper.py && app/.venv/bin/python app/org_scraper.py && bash deploy-gcp.sh >> scraper.log 2>&1
```

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
- Timestamps displayed in user's local timezone with friendly formatting (e.g., "Apr 5, 2026, 3:42 PM EDT")

## Known Issues
1. **Hidden donor lists** — Some members have raised > 0 but `is_donor_list_visible=0`, so their individual donation records can't be fetched via the API. Their totals are reflected in `members.raised` but not in the `donations` table.
2. **General peloton funds gap** — The parent team's `raised` includes `general_peloton_funds` not attributed to individual members. Surfaced as a footnote on the Overview goals panel.
3. **Bundle cache not thread-safe** — `_cache` dict in dashboard.py is accessed without locking. Fine for single-threaded Flask dev server, but would need `threading.Lock` under Gunicorn with threads.
4. **Sub-team snapshots lack participant-type counts** — `daily_snapshots` for sub-teams only record `raised` and `members_count`, not `riders_count`/`challengers_count`/`volunteers_count`. Sub-team report deltas for specific types are approximated.
5. **Volunteer goals not tracked** — `GOALS_2026_SUBTEAMS` in constants.ts only has rider/challenger/funds goals. Volunteer goal column in TeamsTab always shows 0.
