# Pelotonia Dashboard & Scraper

## Project Purpose
Fundraising analytics dashboard and automated data collection for a Pelotonia team.
Data is sourced from the Pelotonia API, PledgeIt campaign page, and organization endpoints.

## Structure
- `app/` — Application code:
  - `pelotonia_scraper.py` — Scrapes Pelotonia API for team/member/donation/route data into SQLite
  - `pledgeit_scraper.py` — Scrapes aggregate Pelotonia Kids stats from PledgeIt campaign page
  - `org_scraper.py` — Scrapes aggregate stats for ~31 top Pelotonia parent organizations from the API
  - `pelotonia_data.db` — SQLite database (teams, members, donations, member_routes, daily_snapshots, events, routes, rides, donor_identities, kids_snapshots, org_snapshots, org_member_profiles)
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
- **True-up mode**: `--trueup` runs the incremental scrape, then (a) soft-prunes members not seen this run — clears `team_id`, zeros participation flags, and removes their `member_routes`, but keeps the rows so donation history (NOT NULL FK to `members.public_id`) survives — and (b) re-fetches every surviving member's profile so participation flags are authoritative. Run weekly to reconcile the DB with departures the daily incremental never removes.
- **Backfill mode**: `--backfill-donations` fetches donations for members with raised > 0 but no donation records (one-time catch-up)
- **first_scraped**: Members table records `first_scraped` (set once on insert, backfilled from `last_scraped` for pre-existing rows) — surfaced as the "Signed Up" column on the Members tab
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
- **Overview**: Pelotonia-branded goals panel (editable targets via localStorage, campaign arrow asset, friendly timestamp; funds goal renders as `$XK`), Fundraising Growth dual-axis chart (cumulative line + daily bars) with a footnote that the cumulative total reflects only record-by-record donations and runs below the official raised figure, Participant Signups Over Time (Riders/Challengers/Volunteers lines), Participant Types by Sub-Team chart, Raised by Sub-Team chart
- **Teams**: 2026 Goals & Progress table (all sub-teams), Participant Types by Sub-Team chart, Raised by Sub-Team chart
- **Routes & Events**: Signature Ride & Gravel Day signup totals + vertical bar chart (Raised vs Committed) + route tables with member drill-down modals
- **Members**: KPI cards (member count, unique donors, avg donors/member), searchable/sortable member table with donation modals, column header click-to-sort (Rider ID, Name, Sub-Team, Type, Years, Raised, All-Time, Signed Up), "Rider ID" column from `public_id` (the Pelotonia rider ID, e.g. `PF0041`/`TW766516` — searchable and CSV-exported), "Signed Up" column from `first_scraped`, cross-tab navigation from other tabs. Type column (`utils/memberType.ts`): Rider > Challenger > Volunteer > untyped-with-route→Rider > on-team-but-untyped→**Registered** > off-team→`—`. The type-search box matches the derived label (e.g. "registered", "volunteer")
- **Donors**: Top donors table with recipient breakdown modals
- **Companies**: Corporate donor analytics with drill-down modal (matches by recognition_name)
- **Donations**: Donation feed table with search
- **Infographics**: Thermometer-style visualizations per team, editable targets via localStorage, campaign timeline calculations, prior-year benchmarking
- **Daily Report**: Email-style report view with daily/weekly toggle, sub-team filter, KPI cards, top movers, compact sub-team participation table. In daily mode, when today's (just-written, overnight-only) snapshot is the latest row, it falls back to yesterday's snapshot as "latest" so the delta covers a complete day of activity
- **Pelotonia Kids**: 5 KPIs (fundraisers, raised, goal, progress %, teams) + 2 line charts from PledgeIt campaign data
- **Leaderboard**: Organization comparison — 4 KPIs, sortable table (incl. Riders column from per-org participant breakdown), top-15 bar chart

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

A weekly true-up runs Sundays at 09:00 UTC (5am ET) to reconcile departures and refresh every member's profile:
```
0 9 * * 0 cd /home/zabx/source/pelotonia-dashboard && export PATH="$HOME/google-cloud-sdk/bin:$PATH" && app/.venv/bin/python app/pelotonia_scraper.py --trueup && bash deploy-gcp.sh >> scraper.log 2>&1
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
- **API**: Uses `peloton/{id}` endpoint per org (hardcoded IDs, 0.3s rate limiting)
- **Raised reconstruction**: Each org's stored `raised` is the *robust reconstruction* `SUM(direct child raised) + generalPelotonFunds` (via `reconstruct_raised()`, one extra `peloton/{id}/members` fetch per org), **not** the API's raw `fundraising.raised` field — same methodology `dashboard.py:_get_overview` uses for the top-bar total, so the Leaderboard and the top bar agree. Falls back to the raw field if the child list is unavailable. See Known Issue #2.
- **Participant breakdown**: Also derives riders/challengers/volunteers per org by recursively walking each org's sub-peloton tree (`peloton/{id}/members`, paginated, max depth 4) to collect leaf member publicIds, then reading `participantTypes` from each `user/{id}` profile. This makes a full run much slower than the aggregate-only scrape.
- **Profile cache**: Results are cached in the `org_member_profiles` table (and reused from the existing `members` table when fresh) with a 14-day staleness window, so most runs only fetch newcomers and stale entries.
- **Storage**: `org_snapshots` table in `pelotonia_data.db` — one row per org per day (now includes `riders_count`, `challengers_count`, `volunteers_count`)
- **Usage**: `python app/org_scraper.py` (scrape) / `--summary` (print leaderboard) / `--skip-profiles` (aggregate stats only, no participant walk) / `--refresh-all-profiles` (force re-fetch every cached profile)
- **Dependencies**: stdlib only

## Conventions
- All monetary figures use full precision where available
- Dates in YYYY-MM-DD format
- Timestamps displayed in user's local timezone with friendly formatting (e.g., "Apr 5, 2026, 3:42 PM EDT")

## Known Issues
1. **Hidden donor lists** — Some members have raised > 0 but `is_donor_list_visible=0`, so their individual donation records can't be fetched via the API. Their totals are reflected in `members.raised` but not in the `donations` table.
2. **Top-of-house / team-level funds** — Pelotonia credits some donations (private/corporate gifts) to a team's total without attributing them to an individual member. Every "Funds Raised" surface shows an **official** total broken into two parts: **tracked** = `SUM(member.raised)` (attributed to members) and **team-level** = `official − tracked` (top-of-house, not attributable), surfaced as a "$X from members + $Y team-level" sub-line on the Overview goals panel, Infographics thermometer cards, and the email report's Funds Raised card.
   - **Org level**: official is the *robust reconstruction* `SUM(sub-team raised) + parent.general_peloton_funds` — **not** the parent's own `raised` field, which is unreliable (the API has dropped it to ~$72K of gpf when it stops aggregating sub-teams). `_get_overview` exposes `raised` (= reconstruction), `raised_tracked`, `raised_team_level`; `daily_report.py` mirrors this. `org_scraper.py` also applies the same reconstruction so the Leaderboard matches the top bar (they can still differ momentarily since the two scrapers run on different schedules).
   - **Sub-team level**: official is the sub-team's own `teams.raised` (reliable — it's what the reconstruction sums). Team-breakdown rows add `official_raised`/`team_level_raised`; the report's sub-team table "Raised" column shows the official figure.
   - The Fundraising Growth chart still only sums record-by-record donations and runs below the official figure (footnoted on the Overview tab).
3. **Bundle cache not thread-safe** — `_cache` dict in dashboard.py is accessed without locking. Fine for single-threaded Flask dev server, but would need `threading.Lock` under Gunicorn with threads.
4. **Sub-team snapshots lack participant-type counts** — `daily_snapshots` for sub-teams only record `raised` and `members_count`, not `riders_count`/`challengers_count`/`volunteers_count`. Sub-team report deltas for specific types are approximated.
5. **Volunteer goals not tracked** — `GOALS_2026_SUBTEAMS` in constants.ts only has rider/challenger/funds goals. Volunteer goal column in TeamsTab always shows 0.
6. **Roster-vs-profile ghost members** — Pelotonia's team-roster API (`peloton/{team}/members`) keeps returning members whose individual profile (`user/{publicId}`) reports `peloton = null` — i.e. they've left the team or re-registered under a new `publicId` (e.g. Brooke Edmonds appears under both an old dead ID and her active rider ID). As of 2026-07-16 audit: **64** such ghosts (39 untyped/"Registered", 23 volunteers, 2 riders), 13 carrying small donations. Because they stay on the roster, `--trueup`'s soft-prune (which keys off members the roster *stops* returning) never removes them, and `scrape_member_profiles` ignores the profile `peloton` field. Reported to Pelotonia (emailed audit CSV) to ask why the roster returns them; **no fix applied pending their response**. Candidate fix: soft-prune any member whose profile `peloton` is null/mismatched (keep the row for donation FK), wired into the profile scrape / trueup.
