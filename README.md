# Pelotonia Team Dashboard

A fundraising analytics dashboard for one [Pelotonia](https://www.pelotonia.org)
team. Pelotonia is a cycling event in Columbus, Ohio; every dollar riders raise
funds cancer research at The Ohio State University Comprehensive Cancer Center.

This repo was built for **Team Huntington Bank**, a "super peloton" of 14
sub-teams and about 4,200 members. It has three parts:

1. **Scrapers** pull public data from Pelotonia's API, the Pelotonia Kids
   (PledgeIt) campaign page, and about 55 other large teams for a leaderboard.
   They write everything to one SQLite file.
2. **A Flask API** reads that file and serves it as JSON.
3. **A React single-page app** shows it in 12 tabs. A daily email report sends a
   summary with a PNG infographic.

Production runs as one container on Google Cloud Run, with the database baked
into the image and redeployed after each scrape.

> **Season status (2026).** Fundraising closed on **2026-10-15**. The site shows
> a banner saying so. Credit-card pledges are charged from 2026-10-20, so
> scraping continues 3× a day through **2026-11-14**, then stops, and the data
> is final. See
> [Scheduled jobs](#scheduled-jobs) and
> [Starting a new season](#starting-a-new-season-or-another-team).

### Other docs

| File | What it covers |
|------|----------------|
| [CHANGELOG.md](CHANGELOG.md) | Every change since the first commit, dated, with commit hashes and the exact rules. Start here if you are porting features to another codebase. |
| [app/SCRAPER.md](app/SCRAPER.md) | Scraper internals: API calls, pagination, incremental logic. |
| [HOW_WE_BUILD_DASHBOARDS.md](HOW_WE_BUILD_DASHBOARDS.md) | The design approach behind the stack, written for teams who want to copy it. |
| [CLAUDE.md](CLAUDE.md) | A dense reference written for AI coding assistants. It doubles as a detailed spec. `GEMINI.md` points to it. |

---

## Contents

- [Architecture](#architecture)
- [Quick start](#quick-start)
- [Configuration](#configuration)
- [Repository layout](#repository-layout)
- [Data sources](#data-sources)
- [Scrapers](#scrapers)
- [Database](#database)
- [How the numbers are computed](#how-the-numbers-are-computed)
- [Dashboard](#dashboard)
- [API reference](#api-reference)
- [Frontend](#frontend)
- [Email reports](#email-reports)
- [Testing and linting](#testing-and-linting)
- [Deployment](#deployment)
- [Scheduled jobs](#scheduled-jobs)
- [Starting a new season or another team](#starting-a-new-season-or-another-team)
- [Known issues and limitations](#known-issues-and-limitations)
- [Data and privacy](#data-and-privacy)
- [Branches and history](#branches-and-history)

---

## Architecture

```
 Pelotonia API ──┐
 PledgeIt page ──┼──► scrapers (Python, cron) ──► SQLite (app/pelotonia_data.db)
 Org endpoints ──┘                                        │
                                                          ▼
                                  Flask (app/dashboard.py) ── JSON ──► React SPA
                                     │ also serves frontend/dist/      (frontend/)
                                     ▼
                     daily_report.py ──► HTML email + PNG (SMTP)

 Deploy: scrape && deploy-gcp.sh ──► Cloud Build ──► Cloud Run (DB baked into image)
```

Design choices worth knowing before you change anything:

- **SQLite is the only datastore.** The scrapers are the only writers. Every
  scrape commits in **one transaction at the end**, so the dashboard never sees
  half a scrape. WAL mode and a 30 s busy timeout let Flask read during a scrape.
- **One payload, two waves.** The frontend loads `/api/bundle/core` (about
  17 KB gzipped) for the first screen, then `/api/bundle/rest` (members,
  donations, donors, companies, commitments) in the background.
- **The cache key is the database file's mtime.** Flask rebuilds and re-gzips
  the bundle only when the DB file changes. Otherwise it serves the cached bytes.
- **The image carries the data.** Cloud Run has no volume, so each deploy bakes
  the current DB into a new image. The scrape and the deploy are chained (`&&`),
  so a deploy never ships a DB that is mid-write or a day old.

---

## Quick start

### Prerequisites

- Python 3.12 (3.10+ works)
- Node.js 20 and npm
- `sqlite3` CLI (optional, for poking at the data)

### 1. Install

```bash
git clone <this repo> pelotonia-dashboard
cd pelotonia-dashboard

python3 -m venv app/.venv
app/.venv/bin/pip install -r app/requirements.txt

(cd frontend && npm ci && npm run build)   # builds frontend/dist/

cp .env.example .env                       # only needed for email and deploy
```

### 2. Load data

The database is not in git. Build it with a full scrape:

```bash
app/.venv/bin/python app/pelotonia_scraper.py   # full scrape of the team
app/.venv/bin/python app/pledgeit_scraper.py    # Pelotonia Kids stats (seconds)
app/.venv/bin/python app/org_scraper.py         # leaderboard of ~55 orgs
```

The scraper waits 0.5 s between API calls. With about 4,200 members, a full
scrape makes over 10,000 calls (profiles, routes and donations for each member),
so expect it to take a couple of hours. Small teams finish in minutes. Later runs
use `--incremental`, which needs about 34 calls when nothing has changed.

### 3. Run

```bash
app/.venv/bin/python app/dashboard.py --port 5050
# open http://localhost:5050/
```

### Frontend development with hot reload

```bash
app/.venv/bin/python app/dashboard.py --port 5050   # terminal 1: API
(cd frontend && npm run dev)                        # terminal 2: Vite on :5173
```

Vite proxies `/api` to Flask on port 5050 (`frontend/vite.config.ts`). Open
http://localhost:5173/.

---

## Configuration

All settings are environment variables. Scripts also load a `.env` file in the
repo root (see [.env.example](.env.example)). `.env` is git-ignored and is
excluded from Cloud Build uploads and the Docker build context.

| Variable | Used by | Default | Purpose |
|----------|---------|---------|---------|
| `PELOTONIA_DB` | all scripts | `app/pelotonia_data.db` | SQLite path. Set to a volume path on Kubernetes. |
| `GMAIL_SENDER` | `daily_report.py` | — | Sender address for reports. |
| `GMAIL_APP_PASSWORD` | `daily_report.py` | — | Gmail [app password](https://support.google.com/accounts/answer/185833) for SMTP. |
| `REPORT_RECIPIENT` | `daily_report.py` | — | Default recipient. `--to` overrides it. |
| `REPORT_SENDER_NAME` | `daily_report.py` | `Pelotonia Dashboard` | Display name on the email. |
| `GCP_PROJECT` | `deploy-gcp.sh` | `pelotonia-dashboard` | GCP project ID. |
| `GCP_REGION` | `deploy-gcp.sh` | `us-central1` | Cloud Run and Artifact Registry region. |
| `PELOTONIA_GCP_ACCOUNT` | `deploy-gcp.sh` | unset | gcloud account to deploy as. Set it; see [Deployment](#deployment). |

Team-specific and season-specific values are constants in the code.
See [Starting a new season or another team](#starting-a-new-season-or-another-team).

---

## Repository layout

```
pelotonia-dashboard/
├── app/
│   ├── pelotonia_scraper.py   Main scraper: teams, members, profiles, routes, donations
│   ├── pledgeit_scraper.py    Pelotonia Kids aggregate stats (stdlib only)
│   ├── org_scraper.py         Leaderboard: ~55 parent orgs + participant counts (stdlib only)
│   ├── dashboard.py           Flask API + static file server
│   ├── daily_report.py        Daily/weekly email: HTML body + Pillow-rendered PNG
│   ├── requirements.txt       Pinned Python dependencies
│   └── SCRAPER.md             Scraper technical guide
├── frontend/                  React + TypeScript + Vite app (see Frontend below)
├── tests/                     pytest suite for the Flask API (fixture DB in conftest.py)
├── k8s/                       Draft Kubernetes manifests (not used in production)
├── Dockerfile                 Multi-stage: Node builds frontend, Python serves it
├── deploy-gcp.sh              Cloud Build + Cloud Run deploy
├── .env.example               Every setting, documented
├── CHANGELOG.md               Dated history of every change
└── CLAUDE.md / GEMINI.md      Reference for AI coding assistants
```

---

## Data sources

All sources are public and need no login.

### Pelotonia API

Base URL: `https://pelotonia-p3-middleware-production.azurewebsites.net/api`

Pagination is header-based. Send `Pagination-Page` and `Pagination-Limit`; read
`Pagination-Total` from the response. `api_get()` in `pelotonia_scraper.py`
follows pages automatically.

| Endpoint | Returns |
|----------|---------|
| `peloton/{id}` | A team: name, captain, story, `fundraising` (raised, goal, `generalPelotonFunds`) |
| `peloton/{id}/members` | The team's roster. Individuals carry `raised`, `attributed` and `commitmentAmount`; sub-teams carry `membersCount > 0`. |
| `search/pelotons?query=…` | Team search (used to find the sub-teams) |
| `event`, `ride/{id}/routes` | The current year's rides and routes |
| `events/all` | Metadata for every past year |
| `user/{publicId}` | A member's profile: participant types, tags, `fundraising` (`raised`, `attributed`, `committedAmount`, `committedMet`, `allTimeRaised`) |
| `user/{publicId}/donations` | Donations a member received (paginated) |
| `user/{publicId}/routes` | Routes a member picked |
| `ticker` | Pelotonia-wide totals: `currentYearRaised`, `totalParticipants`, `allTimeRaised` |

### Pelotonia Kids (PledgeIt)

`pledgeit_scraper.py` fetches the campaign page (`CAMPAIGN_URL`), extracts the
`__NEXT_DATA__` JSON, and reads the campaign from the Apollo cache. It stores
aggregates only: fundraiser count, amount raised, goal and team count.

---

## Scrapers

### `pelotonia_scraper.py` — the team

```bash
python app/pelotonia_scraper.py                       # full scrape
python app/pelotonia_scraper.py --incremental         # daily: only what changed
python app/pelotonia_scraper.py --trueup              # weekly: incremental + reconcile everything
python app/pelotonia_scraper.py --reconcile-donations  # re-fetch all donations, delete removed ones
python app/pelotonia_scraper.py --backfill-donations   # members with raised > 0 but no donation rows
python app/pelotonia_scraper.py --summary             # print a DB summary, no scraping
python app/pelotonia_scraper.py --export-csv          # dump tables to CSV
# also: --teams-only, --team-id <id>, --skip-donations, --skip-profiles, --db <path>
```

| Mode | What it fetches | Typical cost |
|------|-----------------|--------------|
| full | everything for every member | 10,000+ calls at today's size |
| `--incremental` | rides, routes, teams and rosters every time. Profiles only for new members, untyped members, or profiles older than 7 days. Routes for new and refreshed members. Donations only for members whose `raised` changed. | ~34 calls when stable |
| `--trueup` | incremental, then: soft-prune members the roster stopped returning, re-fetch every profile, rebuild every member's routes, reconcile every member's donations | ~3 hours |

How the main scraper behaves:

- **One transaction per run.** Nothing is visible until the final commit.
- **Soft-prune, never delete members.** Departed members keep their row (donations
  reference it) but lose `team_id`, their type flags and their routes.
- **Donations are authoritative per member.** When a member's donation list is
  fetched completely, stored rows missing from it are deleted. A failed page
  returns nothing, so a partial list never deletes anything.
- **Prior-year routes are skipped.** Only routes in the current `routes` table
  are stored.
- **Daily snapshot.** Each run upserts one `daily_snapshots` row per team for
  today.

### `org_scraper.py` — the leaderboard

```bash
python app/org_scraper.py                         # all orgs + participant counts
python app/org_scraper.py --summary               # print the leaderboard
python app/org_scraper.py --skip-profiles         # totals only (fast)
python app/org_scraper.py --refresh-all-profiles  # ignore the 14-day profile cache
```

- The org list is the `ORGS` dict at the top of the file (Pelotonia peloton IDs).
- An org's `raised` is rebuilt from its sub-teams. See
  [How the numbers are computed](#how-the-numbers-are-computed).
- Rider, challenger and volunteer counts come from walking each org's sub-team
  tree (max depth 4) and reading every member's profile. Profiles are cached in
  `org_member_profiles` for 14 days.
- **Collapse guard:** if an org's new `raised` is under half its last snapshot,
  the last values are kept and a `GUARD` line is logged. The API has returned
  empty member lists before.

### `pledgeit_scraper.py` — Pelotonia Kids

```bash
python app/pledgeit_scraper.py            # scrape
python app/pledgeit_scraper.py --summary  # print the latest snapshot
```

---

## Database

SQLite in WAL mode. Each scraper creates the tables it needs on first run.

| Table | One row per | Notes |
|-------|-------------|-------|
| `teams` | team (parent and its sub-teams) | `raised`, `goal`, `goal_override` (manual, never overwritten), `general_peloton_funds`, `members_count` |
| `members` | person ever seen on a roster | see the key columns below |
| `donations` | gift (`opportunity_id`) | `recipient_public_id`, `amount`, `date`, `pending`, `anonymous_to_public`, `donor_name`, `recognition_name` |
| `donor_identities` | anonymous recognition name | Guesses who an anonymous donor is from their other gifts. Not shown in the UI. |
| `rides`, `routes` | ride / route | current year only; `fundraising_commitment` per route |
| `member_routes` | member × route | rebuilt weekly by `--trueup` |
| `daily_snapshots` | team × day | `raised`, `members_count`, rider/challenger/volunteer counts (parent only) |
| `events` | past Pelotonia year | participants, dates |
| `kids_snapshots` | day | Pelotonia Kids aggregates |
| `org_snapshots` | org × day | leaderboard history with participant counts |
| `org_member_profiles` | org member | participant-type cache for the leaderboard |

### Key `members` columns

| Column | Source | Meaning |
|--------|--------|---------|
| `public_id` | roster | Pelotonia rider ID (the primary key) |
| `team_id` | roster | sub-team; `NULL` once soft-pruned |
| `raised` | roster | money given to this member directly |
| `attributed` | roster | `raised` plus team funds Pelotonia assigned to the member |
| `commitment_amount` | roster | commitment as the roster reports it |
| `committed_amount` | profile | commitment as the profile reports it (used by the Commitments tab) |
| `committed_high_roller` | profile | High Roller commitment flag |
| `is_rider`, `is_challenger`, `is_volunteer` | profile | participant types |
| `is_donor_list_visible` | profile | if 0, donations can't be fetched |
| `first_scraped` | scraper | first time seen ("Signed Up" in the UI) |

---

## How the numbers are computed

These rules came from comparing the dashboard against Pelotonia's own figures.
If you port the dashboard, port these rules. Each one fixed a visible error.

**1. Team "Raised" (the headline number).**
`official = SUM(sub-team teams.raised) + parent.general_peloton_funds`.
Never use the parent team's own `raised` field: the API sometimes stops summing
sub-teams and drops it to a few thousand dollars. `org_scraper.py` uses the same
reconstruction for every org, so the Leaderboard matches the top bar.

**2. Members vs team-level money.**
`tracked = SUM(members.raised)` and `team-level = official − tracked`. Team-level
money is corporate or private gifts credited to a team, not to a person. Every
"Funds Raised" figure shows "$X from members + $Y team-level". For a sub-team,
`official` is that sub-team's own `teams.raised`, corrected by rule 2a.

**2a. Pelotonia's double-counted team funds.**
A captain can assign a team's general funds to riders. That raises each rider's
`attributed` above their own `raised`, and the money also stays in the team's
general funds. From 2026-10-14 (a few small sub-teams) to 2026-10-23 (all of
them), Pelotonia changed its sub-team total from `SUM(rider raised) + general
funds` to `SUM(rider attributed) + general funds`. Its own `totalRaisedByMembers`
field equals `SUM(rider attributed)`. Assigned money is therefore counted twice:
$702,455 on 2026-10-23.

`correct_team_funds_double_count()` in `pelotonia_scraper.py` handles this on
every scrape, for each sub-team:

```
assigned = SUM(rider attributed − rider raised)
gap      = reported total − SUM(rider raised) − general funds
if assigned ≥ $1 and gap ≥ 0.5 × assigned:  raised = reported − assigned
else:                                        raised = reported
```

The API's figures are kept in `teams.raised_reported` and
`all_time_raised_reported`, and the amount subtracted in
`double_count_correction`. The parent gets the summed correction only when its
own figure contains it, since it can lag its sub-teams by a day. When Pelotonia
fixes its totals, `gap` falls to about zero and the reported figures are used
again with no code change. An ⓘ next to Raised explains the difference from
pelotonia.org, and it shows only while a correction is active. The Leaderboard
corrects the home team's row; other orgs are shown as Pelotonia reports them,
because their riders aren't scraped.

**3. Pelotonia Kids.**
Kids money is raised on a separate platform (PledgeIt). Since 2026-10-20,
Pelotonia adds it to the parent team's general peloton funds, so rule 1 already
includes it. The Raised (2026) and All-Time cards and the home team's
Leaderboard row only note "incl. $X Pelotonia Kids"; they don't add it. Before
that date Pelotonia left Kids out, and the dashboard added it itself. Check this
each season: if the parent's total jumps by the Kids amount, it is included.

**4. Commitments.**
`credited = max(raised, attributed)` and `shortfall = committed_amount − credited`.
If `shortfall < 1`, the commitment counts as met. Pelotonia counts team funds
assigned to a rider (`attributed`) toward the commitment and ignores gaps under
$1. An audit of all 2,886 committed members on 2026-10-18 found this rule matches
the API's `committedMet` flag for every member but one apparent manual waiver.
Only on-team members with `committed_amount > 0` are included. The tab splits
credited into the rider's own **Raised** and **Team Credit** (`credited −
raised`, assigned team funds). "Filled by Team Funds" is the commitment dollars
team credit covered. "Surplus" counts only riders' own money above their
commitment, so team funds aren't counted twice there either.

**5. Commitment trend chart.**
Settled (non-pending) donations are replayed day by day against today's
commitments. Team credits have no date, and members with hidden donor lists have
no donation rows, so the chart's last point sits above the real shortfall. The
chart is labelled "Personal Donations Only".

**6. Fundraising Growth chart.**
The chart is a cumulative sum of donation rows, so it runs below the official
total for the same reasons. It is footnoted.

**7. Member type.**
Rider > Challenger > Volunteer > (untyped but has a route → Rider) > (on a team
but untyped → "Registered") > (off-team → "—"). See
`frontend/src/utils/memberType.ts`.

**8. First-year riders.** Count riders only, not every member type.

**9. Daily deltas.** Snapshots are end-of-day, but the morning scrape writes
today's row with overnight activity only. In daily mode, both the Report tab and
the email compare the last complete day: if the newest snapshot is today's, they
use yesterday as "latest".

---

## Dashboard

### Top of page

- **"Fundraising closed" banner** once `FUNDRAISING_CLOSE` has passed
  (`components/layout/ClosedBanner.tsx`).
- **KPI strip:** three flip cards (Raised 2026, All-Time Raised, Members) that
  flip to Pelotonia-wide totals from the ticker API. Five plain cards: First Year
  Riders, Signature Riders, Gravel Riders, Cancer Survivors, High Rollers.
- **Progress bar** toward the team funds goal.

### Tabs

| Tab | What it shows |
|-----|---------------|
| Overview | Goals panel (riders, challengers, volunteers, funds; targets editable and saved in the browser), Fundraising Growth, signups over time, participant types and raised by sub-team |
| Teams | Goals and progress for every sub-team, plus the two sub-team charts |
| Routes & Events | Signature Ride and Gravel Day signups, raised vs committed per route, route tables with member drill-downs |
| Members | Searchable, sortable table of every member: Rider ID, type, years, raised, all-time, signed-up date. CSV export. Click a row for their donations. |
| Donors | Donors ranked by total given, with company affiliation, recipient count and first/last gift. Click for recipients. |
| Companies | Corporate donors (by recognition name) with drill-down |
| Donations | Searchable donation feed |
| Commitments | Who is below their commitment: four KPIs, trend chart, Below/Met/All table with Credited column, CSV export |
| Infographics | Thermometer cards per team, countdown, prior-year comparison |
| Daily Report | The email report as a web page, with daily/weekly toggle and sub-team filter |
| Pelotonia Kids | Kids campaign KPIs and two trend charts |
| Leaderboard | ~55 large teams ranked by raised, with rider counts and a top-15 chart |

Rows link across tabs: a top fundraiser opens the Members tab filtered to them; a
member, donor, route or company opens a detail modal.

---

## API reference

All endpoints are `GET` and return JSON. The frontend uses only the three bundle
endpoints; the rest serve one dataset each, for debugging and ad-hoc queries.

| Endpoint | Bundle key | Wave |
|----------|-----------|------|
| `/api/bundle` | everything below | — |
| `/api/bundle/core` | the core keys | 1 |
| `/api/bundle/rest` | `members donations donors companies orgSnapshots commitmentGap` | 2 |
| `/api/overview` | `overview` — raised (official), `raised_tracked`, `raised_team_level`, `kids_raised`, goal, counts | core |
| `/api/teams` | `teams` | core |
| `/api/fundraising-timeline` | `timeline` | core |
| `/api/top-fundraisers` | `fundraisers` | core |
| `/api/team-breakdown` | `teamBreakdown` — per sub-team types, committed, `official_raised`, `team_level_raised` | core |
| `/api/commitment-tiers` | `commitTiers` | core |
| `/api/ride-type-breakdown` | `rideTypes` | core |
| `/api/routes` | `routes` | core |
| `/api/signup-timeline` | `signupTimeline` | core |
| `/api/events` | `events` | core |
| `/api/snapshots/teams` | `subteamSnapshots` | core |
| `/api/kids-overview` | `kidsOverview` | core |
| `/api/kids-snapshots` | `kidsSnapshots` | core |
| `/api/org-leaderboard` | `orgLeaderboard` | core |
| (ticker, cached in `.ticker_cache.json`) | `ticker` | core |
| `/api/members` | `members` | rest |
| `/api/donations` | `donations` | rest |
| `/api/top-donors` | `donors` | rest |
| `/api/companies` | `companies` | rest |
| `/api/org-snapshots` | `orgSnapshots` | rest |
| `/api/commitment-gap` | `commitmentGap` — `summary`, `members` (with `credited`), `timeline` | rest |
| `/api/snapshots` | parent-team daily snapshots | — |
| `/api/route-members/<route_id>` | members on one route (used by the route modal) | — |

Bundle responses are gzipped once per database change and cached in memory.
Built assets under `/assets/` are served `immutable`; `index.html` is `no-cache`.

---

## Frontend

React 19, TypeScript, Vite, Zustand for state, Chart.js with
`chartjs-plugin-datalabels`, CSS modules, Vitest with Testing Library.

```
frontend/src/
├── App.tsx               Layout and tab switch
├── api/client.ts         fetch helpers
├── store/                Zustand store: loads core, then rest; modal state
├── tabs/                 One component per tab (InfographicsTab/ is a folder)
├── components/
│   ├── layout/           Banner, header, KPI strip, progress bar, tab bar, footer
│   ├── charts/           One component per chart
│   ├── modals/           Drill-down modals and ModalRouter
│   └── shared/           Table, pagination, search, KPI card, loading placeholder
├── hooks/                useSearch, usePagination
├── utils/                Formatting, CSV export, member type, editable targets
├── types/                API types (index.ts) and constants (dates, goals, brand)
└── styles/               variables.css holds the brand tokens
```

Conventions:

- **Datalabels are registered globally.** Every chart must set
  `datalabels: { display: false }` unless it wants labels.
- **Brand colors** live in `styles/variables.css` and `BRAND` in
  `types/constants.ts`. They come from Pelotonia's official asset guidelines;
  don't invent new ones.
- **Breakpoints:** 900 px (grids collapse), 768 px (tab bar scrolls), 600 px
  (phone).
- **Editable targets** (goals panel, infographics) are saved in `localStorage`
  per browser.
- Timestamps display in the viewer's time zone, e.g. "Oct 18, 11:00 AM EDT".

---

## Email reports

`app/daily_report.py` builds an HTML email and a 680 px PNG infographic (Pillow).
It shows four cards (funds, riders, challengers, volunteers) with day-over-day or
week-over-week change, top movers, and a sub-team table. It sends via Gmail SMTP.

```bash
python app/daily_report.py --preview --output report.html   # write HTML, don't send
python app/daily_report.py --send                           # to REPORT_RECIPIENT
python app/daily_report.py --send --to someone@example.com --weekly
```

`--weekly` uses 7-day deltas and five movers instead of three.

---

## Testing and linting

```bash
app/.venv/bin/python -m pytest tests     # 70 API tests on a fixture database
(cd frontend && npm test)                # 71 Vitest tests
(cd frontend && npm run lint)            # ESLint
(cd frontend && npm run build)           # includes tsc type-check
uvx ruff check --select F,E9 app tests   # optional Python lint
```

The API tests build a small SQLite database in `tests/conftest.py` and never
touch the network or the real DB.

---

## Deployment

### Google Cloud Run (production)

```bash
bash deploy-gcp.sh
```

The script runs `gcloud builds submit` to build the Dockerfile, then
`gcloud run deploy` (256 MiB, at most 2 instances, public). The image contains
`app/` (including `pelotonia_data.db`) and the built frontend, so **each deploy
publishes the current data**. Set `PELOTONIA_GCP_ACCOUNT`. Without it, gcloud
uses whichever account is active on the machine. In September 2026 another
project's configuration left the wrong account active, deploys failed, and the
site served day-old data until someone noticed.

One-time GCP setup: enable Cloud Build, Artifact Registry and Cloud Run, then
create an Artifact Registry Docker repository named `pelotonia` in the region.

### Kubernetes (draft)

`k8s/` holds a Deployment and Service, a daily scraper CronJob, and a
PersistentVolumeClaim, so the DB lives on a volume instead of in the image. Set
`PELOTONIA_DB=/data/pelotonia_data.db`. These manifests have not run in
production.

### Running Flask in production

`dashboard.py` uses Flask's built-in server, which is fine for one Cloud Run
instance. The bundle cache is a plain dict without a lock. Add one before running
under a multi-threaded server such as Gunicorn with threads.

---

## Scheduled jobs

Production runs from cron on a small Linux host. The scrape and deploy share one
line so the deploy waits for the scrape to commit.

**Campaign season** (March to mid-October):

```cron
# Scrape and deploy 3x a day: 7am, 1pm, 7pm ET
0 11,17,23 * * * cd /path/to/pelotonia-dashboard && app/.venv/bin/python app/pelotonia_scraper.py --incremental && app/.venv/bin/python app/pledgeit_scraper.py && app/.venv/bin/python app/org_scraper.py && bash deploy-gcp.sh >> scraper.log 2>&1
# Weekly true-up, Sunday 01:00 UTC (takes ~3 hours)
0 1 * * 0 cd /path/to/pelotonia-dashboard && app/.venv/bin/python app/pelotonia_scraper.py --trueup && bash deploy-gcp.sh >> scraper.log 2>&1
# Emails: daily at 11:30 UTC, weekly on Thursdays
30 11 * * * cd /path/to/pelotonia-dashboard && set -a && . ./.env && set +a && app/.venv/bin/python app/daily_report.py --send >> scraper.log 2>&1
35 11 * * 4 cd /path/to/pelotonia-dashboard && set -a && . ./.env && set +a && app/.venv/bin/python app/daily_report.py --send --weekly >> scraper.log 2>&1
```

**After fundraising closes** (the 2026 setup): keep scraping while pledged gifts
are charged, then stop. Pelotonia began charging credit-card pledges on
2026-10-20, five days after the close, and money posts for several weeks after.
The schedule stays 3× a day. Both lines start with a date guard, so nothing runs
after 2026-11-14:

```cron
0 11,17,23 * * * [ "$(date -u +\%Y\%m\%d)" -le 20261114 ] && { cd ... && ... && bash deploy-gcp.sh; } >> scraper.log 2>&1
0 1 * * 0    [ "$(date -u +\%Y\%m\%d)" -le 20261114 ] && { cd ... && ... --trueup && bash deploy-gcp.sh; } >> scraper.log 2>&1
```

Cron times are UTC and don't shift for daylight saving (11:00 UTC is 7am EDT and
6am EST). Never run two scrapes at once; the true-up's 3-hour run is why it
starts at 01:00.

---

## Starting a new season or another team

Season dates, goals and the team ID are constants in code. Change these:

| What | Where |
|------|-------|
| Parent team ID | `PARENT_TEAM_ID` in `app/pelotonia_scraper.py`, `app/dashboard.py`, `app/daily_report.py` |
| Sub-team search term | `search/pelotons?query=huntington` in `scrape_teams()` (`app/pelotonia_scraper.py`) |
| Team name in text | "Team Huntington Bank" strings in `daily_report.py`, `dashboard.py` and the frontend header |
| Kids campaign | `CAMPAIGN_URL` in `app/pledgeit_scraper.py` |
| Leaderboard orgs | `ORGS` in `app/org_scraper.py` |
| Season dates | `REGISTRATION_OPEN`, `RIDE_WEEKEND`, `GRAVEL_DAY`, `FUNDRAISING_CLOSE`, `DATA_FINAL` in `frontend/src/types/constants.ts`; `CAMPAIGN_START`, `RIDE_DAY` in `app/daily_report.py` |
| Goals | `GOALS_2026` and `GOALS_2026_SUBTEAMS` in `frontend/src/types/constants.ts`; `GOALS` and `GOALS_SUBTEAMS` in `app/daily_report.py` |
| Prior-year total | `LAST_YEAR_TOTAL` in `frontend/src/types/constants.ts` |
| Year labels | "2026" in the header badge and KPI labels |

For a new season, start with a fresh database. Last season's members, donations
and snapshots would otherwise mix with the new ones. The scrapers create the
tables on first run. Keep the old file as an archive.

---

## Known issues and limitations

1. **Hidden donor lists.** About 350 on-team members raised money but hide their
   donor list, so their gifts can't be fetched. Their totals are right; their
   individual donations are missing from the Donations, Donors and Companies
   tabs and the trend charts.
2. **Trend charts run below the official totals** (rules 5 and 6 above).
3. **Ghost members.** Pelotonia's roster endpoint keeps returning some members
   whose profile says they have no team (left, or re-registered under a new
   ID). The true-up only prunes members who drop off the roster, so these stay.
   64 were found in July 2026. Pelotonia was asked about it; no fix is applied.
   A candidate fix: soft-prune any member whose profile `peloton` is null.
4. **Sub-team snapshots have no type counts.** Only the parent row records
   riders, challengers and volunteers per day, so sub-team type deltas are
   approximate.
5. **No volunteer goals per sub-team.** The Teams tab volunteer goal shows 0.
6. **Bundle cache has no lock** (see [Deployment](#deployment)).
7. **The data goes stale on its own after the season.** The cron guard stops
   scraping, but the dates in `constants.ts` must be updated by hand each year.
8. **Double-count correction relies on rider data.** Rule 2a needs this
   scrape's rider `raised` and `attributed`. Snapshots from 2026-10-14 to
   2026-10-22 were repaired once, using rider data from the nearest backup. The
   parent team's own daily snapshot still wobbles on days its Pelotonia figure
   lagged its sub-teams; the headline is built from sub-teams and is unaffected.

---

## Data and privacy

Everything here comes from public Pelotonia and PledgeIt pages, but the database
gathers it in one place: member names, amounts, and donor names on gifts that
weren't marked anonymous.

- The database, CSV exports, logs and `.env` are git-ignored, and have never been
  committed.
- The deployed site is public and serves the full database contents through the
  API. Put it behind authentication if that is not what you want.
- `donor_identities` (built by `build_donor_identities()` in the main scraper)
  tries to infer who gave anonymous gifts. Nothing displays it. Consider dropping
  it before running this for a team that didn't ask for it.
- Be polite to Pelotonia's API: keep `REQUEST_DELAY` (0.5 s) and don't run
  scrapers in parallel.

---

## Branches and history

`master` is the mainline and what production deploys. The full history is in
[CHANGELOG.md](CHANGELOG.md).

- The mainline was once named `alloydb-migration`. A move to PostgreSQL/AlloyDB
  started in April 2026 and was abandoned, but feature work kept landing on that
  branch. It was renamed to `master` in July 2026 without rewriting any commits.
- `archive/alloydb-postgres-wip` holds the abandoned migration (one commit,
  `7eb778e`, never deployed).
- `archive/superseded-may-fixes` holds five May 2026 commits whose changes were
  re-done on the mainline in `6e781d1`. It is kept for the record only.

Don't build on `archive/*`.
