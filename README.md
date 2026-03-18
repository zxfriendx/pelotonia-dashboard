# Pelotonia Dashboard & Scraper

Real-time fundraising analytics dashboard and automated data collection for a [Pelotonia](https://www.pelotonia.org) team — the grassroots cycling community that funds cancer research at The Ohio State University Comprehensive Cancer Center.

## Repository Structure

```
pelotonia-dashboard/
├── app/                            # Application code
│   ├── pelotonia_scraper.py            # Main data scraper (Pelotonia API → SQLite)
│   ├── pledgeit_scraper.py             # Pelotonia Kids stats scraper (PledgeIt → SQLite)
│   ├── org_scraper.py                  # Organization leaderboard scraper (~31 parent orgs)
│   ├── dashboard.py                    # Flask dashboard (port 5050, 11 tabs)
│   ├── daily_report.py                 # Daily/weekly email report with HTML + PNG infographic
│   ├── pelotonia_data.db               # SQLite database (not in git)
│   └── SCRAPER.md                      # Scraper technical guide
├── k8s/                            # Kubernetes manifests (Shakudo/AWS)
│   ├── deployment.yaml                 # Dashboard Deployment + Service
│   ├── cronjob.yaml                    # Daily scraper CronJob
│   └── pvc.yaml                        # PersistentVolumeClaim for SQLite
├── Dockerfile                      # Container image (serves both dashboard and scrapers)
├── deploy-gcp.sh                   # Build + deploy script for GCP Cloud Run
├── .gcloudignore                   # Cloud Build file filter
└── CLAUDE.md                       # Project instructions for Claude Code
```

---

## Dashboard

A single-page Flask application with 11 tabs providing fundraising analytics.

### Tabs

| Tab | Contents |
|-----|----------|
| **Overview** | Goals panel (editable targets), Fundraising Growth chart, Participant Signups Over Time, Participant Types by Sub-Team, Raised by Sub-Team |
| **Teams** | 2026 Goals & Progress table (all sub-teams), Participant Types chart, Raised by Sub-Team chart |
| **Routes & Events** | Signature Ride & Gravel Day signup totals + route tables with member drill-down modals |
| **Members** | KPI cards, searchable/sortable member table with donation modals, cross-tab navigation |
| **Donors** | Top donors table with recipient breakdown modals |
| **Companies** | Corporate donor analytics |
| **Donations** | Donation feed table with search |
| **Infographics** | Thermometer visualizations per team, editable targets, campaign timeline, prior-year benchmarks |
| **Daily Report** | Email-style report view with daily/weekly toggle, sub-team filter, KPI cards, top movers |
| **Pelotonia Kids** | 5 KPIs + 2 line charts from PledgeIt campaign data |
| **Leaderboard** | Organization comparison — 4 KPIs, sortable table (Huntington highlighted), top-15 bar chart |

### Cross-Tab Drill-Downs

- **Fundraiser -> Member**: Click a top fundraiser to jump to Members tab, pre-filtered and highlighted
- **Member -> Donations**: Click any member to see a modal of donations received
- **Donor -> Recipients**: Click any donor to see a modal of recipients
- **Route -> Members**: Click any route to see a modal of signed-up members

### Caching

**mtime-based** — the `/api/bundle` response is cached in memory and rebuilt only when `pelotonia_data.db`'s file modification time changes. Repeated page loads are instant with zero DB queries.

### API Endpoints

All endpoints return JSON.

| Endpoint | Description |
|----------|-------------|
| `GET /api/bundle` | **Primary** — all 20 data sets in one response (mtime-cached) |
| `GET /api/overview` | Team KPIs: raised, goal, members, donors, survivors, high rollers |
| `GET /api/teams` | Sub-teams sorted by raised |
| `GET /api/fundraising-timeline` | Cumulative and daily donation amounts over time |
| `GET /api/snapshots` | Historical daily snapshots (parent team) |
| `GET /api/snapshots/teams` | Historical daily snapshots per sub-team |
| `GET /api/top-fundraisers` | Top 25 fundraisers with tags and ride info |
| `GET /api/team-breakdown` | Riders, challengers, committed, raised by sub-team |
| `GET /api/commitment-tiers` | Members grouped by commitment amount |
| `GET /api/ride-type-breakdown` | Members grouped by ride type |
| `GET /api/routes` | All routes with signup counts, raised, and committed |
| `GET /api/route-members/<route_id>` | Members on a specific route |
| `GET /api/signup-timeline` | Participant counts over time from daily snapshots |
| `GET /api/events` | Historical event metadata (year, participants, dates) |
| `GET /api/top-donors` | Top 25 donors by total amount |
| `GET /api/members` | All members with full detail |
| `GET /api/donations` | Donation feed (most recent 500) |
| `GET /api/companies` | Corporate donor analytics |
| `GET /api/kids-overview` | Pelotonia Kids aggregate stats |
| `GET /api/kids-snapshots` | Pelotonia Kids historical snapshots |
| `GET /api/org-leaderboard` | Organization leaderboard (latest per org) |
| `GET /api/org-snapshots` | Organization historical snapshots |

### Running the Dashboard

```bash
# Manual
cd app && .venv/bin/python dashboard.py --port 5050

# Via systemd (auto-restarts)
systemctl --user start pelotonia-dashboard
systemctl --user status pelotonia-dashboard
```

---

## Data Collection

### Pelotonia API

**Base URL:** `https://pelotonia-p3-middleware-production.azurewebsites.net/api`

Public, unauthenticated. Header-based pagination (`Pagination-Page`, `Pagination-Limit`). The scraper waits 0.5s between requests.

| Endpoint | Description |
|----------|-------------|
| `search/pelotons?query={term}` | Search for teams by name |
| `peloton/{id}` | Team detail (captain, story, fundraising) |
| `peloton/{id}/members` | Members of a team (paginated) |
| `peloton/{id}/fundraising` | Team fundraising summary |
| `event` | Current event details and available rides |
| `ride/{ride_id}/routes` | Routes for a specific ride |
| `user/{publicId}` | Individual member profile |
| `user/{publicId}/donations` | Donations received by a member (paginated) |
| `user/{publicId}/routes` | Routes a member is signed up for |
| `events/all` | Historical event metadata (all years) |

### Main Scraper

```bash
# Full scrape (~4 minutes, ~200+ API calls)
.venv/bin/python pelotonia_scraper.py

# Incremental scrape (~19 seconds, ~34 API calls) — used by daily cron
.venv/bin/python pelotonia_scraper.py --incremental

# Backfill donations for members with raised > 0 but no records
.venv/bin/python pelotonia_scraper.py --backfill-donations

# Other options
.venv/bin/python pelotonia_scraper.py --teams-only
.venv/bin/python pelotonia_scraper.py --team-id <id>
.venv/bin/python pelotonia_scraper.py --summary
.venv/bin/python pelotonia_scraper.py --export-csv
.venv/bin/python pelotonia_scraper.py --skip-donations
.venv/bin/python pelotonia_scraper.py --skip-profiles
.venv/bin/python pelotonia_scraper.py --db <path>
```

### Pelotonia Kids Scraper

Scrapes aggregate stats from the PledgeIt campaign page (fundraiser count, amount raised, goal, team count). Stdlib only.

```bash
python app/pledgeit_scraper.py             # Scrape latest stats
python app/pledgeit_scraper.py --summary   # Print latest snapshot
```

### Organization Leaderboard Scraper

Fetches aggregate stats for ~31 parent Pelotonia organizations via the `peloton/{id}` endpoint.

```bash
python app/org_scraper.py             # Scrape all orgs
python app/org_scraper.py --summary   # Print leaderboard
```

---

## Database Schema

SQLite at `app/pelotonia_data.db` (default). Override with `PELOTONIA_DB` env var. WAL journal mode for concurrent read access.

### Tables

| Table | Description |
|-------|-------------|
| `teams` | 15 sub-teams — name, raised, goal, goal_override, all_time_raised, members_count |
| `members` | ~300+ members — name, team, participation type, raised, committed, tags, story |
| `donations` | Individual donation records — amount, date, donor name, recipient, anonymity flags |
| `donor_identities` | Cross-referenced anonymous donor names with confidence levels |
| `rides` | Ride catalog (Signature Ride, Gravel Day) |
| `routes` | Route details — distance, commitment, capacity, start/end cities |
| `member_routes` | Junction table — which route each member selected |
| `daily_snapshots` | One row per team per day — raised, goal, members, signature/gravel riders |
| `events` | Historical event metadata (2012-2026) |
| `kids_snapshots` | Pelotonia Kids aggregate stats per day (from PledgeIt) |
| `org_snapshots` | Organization leaderboard stats per day (~31 orgs) |

### Entity Relationship

```
teams (1) ──────── (*) members
members (1) ────── (*) donations
members (*) ────── (*) member_routes (junction)
rides (1) ─────── (*) routes
routes (1) ────── (*) member_routes
teams (1) ─────── (*) daily_snapshots
```

---

## Deployment

### GCP Cloud Run

The container bakes the SQLite DB into the image (no external DB), updated daily via auto-deploy. Configure `deploy-gcp.sh` with your GCP project ID.

```bash
bash deploy-gcp.sh   # Manual deploy
```

### Auto-Deploy Chain

```
pelotonia-scraper.timer (11:00 UTC / 7am ET daily)
  → ExecStartPre: org_scraper.py
  → ExecStartPre: pledgeit_scraper.py
  → pelotonia_scraper.py --incremental
  → OnSuccess: pelotonia-deploy.service (GCP Cloud Run redeploy)
    → OnSuccess: pelotonia-report.service (daily email report)
```

### Kubernetes (Shakudo/AWS)

The `k8s/` directory contains draft manifests for running on Kubernetes with a persistent SQLite volume (no daily image rebuilds).

| Resource | File | Purpose |
|----------|------|---------|
| PersistentVolumeClaim | `k8s/pvc.yaml` | 100Mi volume for SQLite DB |
| Deployment + Service | `k8s/deployment.yaml` | Dashboard pod (reads DB from volume) |
| CronJob | `k8s/cronjob.yaml` | Daily scraper (writes DB to volume) |

All scripts read `PELOTONIA_DB` env var for the database path. Falls back to `app/pelotonia_data.db` if unset (local dev / GCP).

```bash
kubectl apply -f k8s/pvc.yaml
kubectl apply -f k8s/deployment.yaml
kubectl apply -f k8s/cronjob.yaml
```

---

## Scheduled Jobs

All services run as **user-level systemd units** (linger enabled).

| Service | Schedule | Description |
|---------|----------|-------------|
| `pelotonia-scraper.timer` | Daily at 11:00 UTC (7am ET) | Org scraper → Kids scraper → Main scraper (incremental) |
| `pelotonia-deploy.service` | On scraper success | GCP Cloud Run redeploy |
| `pelotonia-report.service` | On deploy success | Daily email report |
| `pelotonia-weekly-report.timer` | Thursdays 11:00 UTC | Weekly email report |
| `pelotonia-dashboard.service` | Always running | Flask dashboard on port 5050 |

```bash
systemctl --user status pelotonia-scraper.timer
systemctl --user list-timers
journalctl --user -u pelotonia-scraper.service -n 50
```

---

## Daily & Weekly Email Reports

`app/daily_report.py` generates an HTML email with an attached PNG infographic (680px wide, 2x2 KPI cards: funds/riders/challengers/volunteers). Sent via Gmail SMTP.

- **Daily**: Triggered automatically after GCP deploy
- **Weekly**: `--weekly` flag, 7-day deltas, 5 movers instead of 3

```bash
python app/daily_report.py --preview --output report.html [--weekly]
GMAIL_APP_PASSWORD=<pw> python app/daily_report.py --send [--to email] [--weekly]
```

---

## Setup

### Prerequisites

- Python 3.10+
- pip / venv

### Install

```bash
cd app
python3 -m venv .venv
.venv/bin/pip install flask requests pillow
```

### Initial Data Load

```bash
.venv/bin/python pelotonia_scraper.py        # Full scrape (~4 minutes)
.venv/bin/python dashboard.py --port 5050    # Start the dashboard
```

### Enable Systemd Services

```bash
systemctl --user daemon-reload
systemctl --user enable --now pelotonia-dashboard.service
systemctl --user enable --now pelotonia-scraper.timer
systemctl --user enable --now pelotonia-weekly-report.timer
```

---

## Known Issues

1. **Timer fires at 11:00 UTC (7am EDT / 6am EST)** — Not adjusted for DST.
2. **Hidden donor lists** — 83 members have raised > 0 but `is_donor_list_visible=0`, so their individual donation records can't be fetched via the API.
3. **General peloton funds gap** — The parent team's `raised` includes `general_peloton_funds` (~$18k) not attributed to individual members. Surfaced as a footnote on the Overview goals panel.
