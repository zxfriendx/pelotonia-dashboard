# Changelog

Every change since the first commit, newest first, with the date it landed.

**Baseline.** The project was first committed on **2026-03-18** as `61f41c5`: a
Flask dashboard with 11 tabs rendered as inline HTML, three scrapers (main, Kids,
org) and the daily/weekly email report. If you built the original version on
another platform, that commit is your common ancestor. To see every code change
since then:

```bash
git diff 61f41c5 HEAD -- app/          # backend and scrapers
git diff 61f41c5 HEAD -- frontend/     # the React app (did not exist at baseline)
git log --reverse --stat 61f41c5..HEAD # commit by commit, with files touched
git show <hash>                        # one change in full
```

Each entry lists its commit hashes and the files it touched. Entries that change
a number on screen give the exact rule, so you can port the logic without reading
the Python. The rules are also collected in one place in the README section
[How the numbers are computed](README.md#how-the-numbers-are-computed).

Dates are commit dates (YYYY-MM-DD). Hashes are on `master`.

---

## 2026-10-23: Correct Pelotonia's double-counted team funds

- **Scraper subtracts assigned team funds that Pelotonia counts twice** · `e7c55e3`
  - Between 2026-10-14 and 2026-10-23 Pelotonia changed each sub-team's total
    from `SUM(rider raised) + general funds` to `SUM(rider attributed) +
    general funds`. A rider's `attributed` includes team funds a captain
    assigned to them, and those funds also stay in the team's general funds,
    so they were counted twice: $702,455 by 2026-10-23. The visible effect was
    a $646K jump in two days, of which only $69,705 was new money from riders.
  - Rule, per sub-team on every scrape (`correct_team_funds_double_count()`):
    `assigned = SUM(attributed − raised)`,
    `gap = reported − SUM(raised) − general funds`. If `gap ≥ 0.5 × assigned`,
    store `raised = reported − assigned`; otherwise store the reported figure.
    The same amount comes off `all_time_raised`. The parent gets the summed
    correction only when its own figure contains it, since it can lag.
  - When Pelotonia fixes its totals, the gap falls to about zero and the
    dashboard uses their figures again without a code change.
  - New `teams` columns: `raised_reported`, `all_time_raised_reported`,
    `double_count_correction`. Added by `init_db()` on the next scrape.
  - One-time repair of `daily_snapshots` for 2026-10-14 to 2026-10-23, using
    rider data from the nearest backup.
  - Effect on 2026-10-23: Raised $6,884,759 → **$6,182,304**.
  - `/api/overview` gains `double_count_correction` and
    `raised_pelotonia_reported`. `/api/org-leaderboard` corrects the home
    team's row and adds the same two fields to it.
  - Files: `app/pelotonia_scraper.py`, `app/dashboard.py`,
    `tests/test_double_count.py` (new), `tests/test_api_overview.py`
- **ⓘ tooltip explaining the difference from pelotonia.org** · `e7c55e3`
  - Shown next to Raised (2026) and the Leaderboard's Huntington Raised only
    while a correction is active. New `InfoTip` component: opens on hover, focus
    or tap, and portals to `<body>` so flip cards can't clip it.
  - Files: `frontend/src/components/shared/InfoTip.tsx`,
    `frontend/src/components/shared/DoubleCountTip.tsx`,
    `frontend/src/styles/infotip.module.css`,
    `frontend/src/components/layout/KpiStrip.tsx`,
    `frontend/src/tabs/LeaderboardTab.tsx`, `frontend/src/types/index.ts`
- **Commitments tab separates riders' own money from team credit** · `e7c55e3`
  - New **Team Credit** column (`credited − raised`, sortable, in the CSV).
  - New KPI **Filled by Team Funds**: commitment dollars covered by team credit
    ($861,188 on 2026-10-23), with an ⓘ explanation.
  - **Surplus** now counts only riders' own money above their commitment. It
    had included team credit, which counts the team's money as rider
    over-raising.
  - API: members gain `team_credit`; the summary gains `total_team_credit` and
    `covered_by_team_funds`; `surplus_total` uses the new rule.
  - Files: `app/dashboard.py`, `frontend/src/tabs/CommitmentsTab.tsx`,
    `frontend/src/types/index.ts`

## 2026-10-20: Pelotonia Kids no longer added twice; back to 3 scrapes a day

- **Stop adding Pelotonia Kids on top of the official total** · `da0b60c`
  - On 2026-10-20 Pelotonia started counting the Kids campaign in the parent
    team's general peloton funds. The parent's `raised` and `all_time_raised`
    both rose $201,897 overnight while the sub-teams rose $45,266. The $156,681
    difference matches the Kids total of $155,355.
  - The dashboard had been adding Kids itself (since 2026-07-28 and
    2026-08-13), so Kids was now counted twice: on the Raised (2026) and
    All-Time cards and on the Leaderboard's home-team row.
  - Rule now: show the official reconstruction as is. Keep the
    "incl. $X Pelotonia Kids" note, since the money is inside the total.
    `kids_raised` stays in `/api/overview` and on the Leaderboard row as an
    annotation only.
  - Files: `app/dashboard.py`, `frontend/src/components/layout/KpiStrip.tsx`,
    `tests/test_api_orgs.py`
- **Schedule back to 3× a day** (cron, not in git). Credit-card pledges are
  charged from 2026-10-20, and the money posts over several weeks. The banner now
  reads "Pledged gifts are still being charged and posted. Data updates three
  times a day through November 14, 2026." The Nov 14 stop is unchanged.
  File: `frontend/src/components/layout/ClosedBanner.tsx`
- `daily_report.py` no longer loads a second `.env` from a sibling
  `pelotonia-kids` folder that existed only on the original host.

## 2026-10-20: Public release prep

- **Code and config cleanup for a public repo** · `9e86092`
  - `deploy-gcp.sh` no longer contains a personal account. `GCP_PROJECT`,
    `GCP_REGION` and `PELOTONIA_GCP_ACCOUNT` come from the environment or `.env`.
  - New `.env.example` lists every setting.
  - `.env` and `.claude/` are excluded from Cloud Build uploads and the Docker
    build context. Before this, `.env` was uploaded to the Cloud Build source
    bucket on every deploy (it never reached the image).
  - The Dockerfile installs the pinned `app/requirements.txt` instead of
    unpinned `flask requests pillow`. Removed the unused `psycopg` packages.
  - Lint is clean (ruff F/E9, ESLint): dead variables in `daily_report.py`, an
    unused parameter in `OverviewTab.tsx`, memoized empty-array fallbacks in 8
    charts. `RouteMembersModal` now keys its fetch result by route, so a previous
    route's members no longer flash while the next one loads.
  - New test for the credited commitment rule.
  - `.dockerignore` matches `node_modules` at any depth (`18b40a4`).
  - Files: `.dockerignore .env.example .gcloudignore .gitignore Dockerfile
    deploy-gcp.sh app/daily_report.py app/pelotonia_scraper.py
    app/requirements.txt frontend/src/components/charts/*
    frontend/src/components/modals/RouteMembersModal.tsx
    frontend/src/tabs/OverviewTab.tsx tests/test_api_commitments.py`
- **Docs for handoff** · this commit: README rewritten, this changelog added,
  `frontend/README.md` replaced (it was the Vite template), personal paths and
  names removed from `CLAUDE.md`.

## 2026-10-20: Commitments: sub-$1 shortfalls count as met

- `30ad59f` · `app/dashboard.py`
- Rule: `shortfall = committed − credited`; if `shortfall < 1`, treat it as `0`.
- Why: Pelotonia marks $1,249.67 against a $1,250 commitment as met. A full audit
  of all 2,886 committed members against the API's `committedMet` flag matched
  every member except one, which looks like a manual waiver ($0 on $100).

## 2026-10-18: Fundraising closed: banner, Commitments fix, donation pruning

- **"Fundraising closed" banner** · `0b317de`
  - A green banner above the header once `FUNDRAISING_CLOSE` (2026-10-15) has
    passed. Second line: "Data updates once a day through November 14" (three
    times a day from 2026-10-20), then "Totals are final as of November 14"
    after `DATA_FINAL`.
  - Files: `frontend/src/components/layout/ClosedBanner.tsx` (new),
    `frontend/src/App.tsx`, `frontend/src/styles/layout.module.css`,
    `frontend/src/types/constants.ts`
- **Commitments measured against credited, not raised** · `7039367`
  - Rule: `credited = max(members.raised, members.attributed)`. The shortfall,
    "% fulfilled", "$0 Credited" and surplus all use credited.
  - `attributed` (from the team roster endpoint) adds team funds Pelotonia
    assigns to a member. Pelotonia's `committedMet` flag follows `attributed`;
    `raised` alone disagreed for 1,130 of 2,886 members.
  - Effect on 2026-10-18 data: members below commitment 1,709 → 583; shortfall
    $1.21M → $372.5K.
  - The table gains a sortable **Credited** column, and the CSV gains a
    Credited field. The trend chart now skips `pending` donations and is titled
    "(Personal Donations Only)", because team credits carry no date.
  - API: `/api/commitment-gap` members gain `credited`; the summary gains
    `total_credited`.
  - Files: `app/dashboard.py`, `frontend/src/tabs/CommitmentsTab.tsx`,
    `frontend/src/types/index.ts`
- **Scraper deletes donations the API no longer lists** · `f53f7fb`
  - Bug: `scrape_donations` only ever inserted. Refunded, reversed or moved gifts
    stayed forever. One member held $15K of records against $5K raised.
  - Rule: after fetching a member's donation list, delete that member's stored
    rows whose `opportunity_id` is not in the list. Only prune when the list is
    complete and non-empty. `api_get(..., strict=True)` returns `None` if any
    page fails, so a partial list can't wipe history.
  - New CLI flag `--reconcile-donations` re-fetches every visible member.
    `--trueup` now runs it weekly. The first run on 2026-10-20 removed 167 stale
    rows.
  - Files: `app/pelotonia_scraper.py`, `CLAUDE.md`
- **Post-close schedule** (cron, not in git): one scrape a day (3× again from 2026-10-20) through
  2026-11-14, then none. See README § Scheduled jobs.

## 2026-09-09: Daily email compares the last complete day

- `8eaf5ba` · `app/daily_report.py`
- Bug: today's snapshot row is written by the ~11:00 UTC scrape, so it holds
  overnight activity only. The email compared that against yesterday's full day.
- Rule (daily mode only): if the latest snapshot is today's, use yesterday's row
  as "latest" and the day before as "previous". The Report tab already did this.

## 2026-09-08: Deploy pins its gcloud account

- `bff5815` · `deploy-gcp.sh`
- A gcloud configuration switch for another project made every deploy fail, and
  the public site sat on day-old data. The script now sets
  `CLOUDSDK_CORE_ACCOUNT`. Made configurable on 2026-10-20.

## 2026-09-02: Docs: brand section

- `4606847`, `db0a554`, merged in `0efce86` · `CLAUDE.md`
- One Brand section naming the official Pelotonia kit as the source of the palette.

## 2026-08-25: Commitments tab; countdown rolls to Gravel Day

- **New Commitments tab (12th tab)** · `c5e57db`
  - Who hasn't met their fundraising commitment. Four KPIs (outstanding
    shortfall, members below, $0 count, surplus). A dual-axis trend chart. A
    Below / Met / All filter, search, a sortable table with a High Roller badge,
    donation modals and CSV export.
  - New endpoint `/api/commitment-gap` (bundle key `commitmentGap`, loaded in the
    "rest" wave).
  - Trend rule: replay donations day by day against current commitments. For
    each member, `shortfall -= min(amount, max(commit − cumulative_before, 0))`.
    A member leaves the "below" count on the day their cumulative crosses the
    commitment.
  - Superseded on 2026-10-18: compare against credited, not raised.
  - Files: `app/dashboard.py`, `frontend/src/App.tsx`,
    `frontend/src/components/charts/CommitmentGapChart.tsx`,
    `frontend/src/components/layout/TabBar.tsx`,
    `frontend/src/store/useDashboardStore.ts`,
    `frontend/src/tabs/CommitmentsTab.tsx`, `frontend/src/types/*`,
    `tests/test_api_bundle.py`, `tests/test_api_commitments.py`
- **Countdown rolls forward** · `370f716`
  - `nextRideEvent()` returns Ride Weekend (Aug 1–2) until it has passed, then
    Gravel Day (Oct 3). Labels read "Days to Gravel Day" / "To Gravel".
  - Files: `frontend/src/types/constants.ts`,
    `frontend/src/tabs/InfographicsTab/*`

## 2026-08-13: Kids money in the top bar and Leaderboard; org collapse guard

- **All-Time Raised card includes Pelotonia Kids** · `89f56f9`
  - Same treatment as the Raised (2026) card: add the current Kids campaign
    amount and show "incl. $X Pelotonia Kids".
  - File: `frontend/src/components/layout/KpiStrip.tsx`
- **Leaderboard folds Kids into the home team; guard against API collapses** ·
  `72abaf6`
  - `/api/org-leaderboard` adds the latest `kids_snapshots.estimated_amount_raised` to the
    home team's `raised` and `all_time_raised`, then re-sorts.
  - Guard in `org_scraper.py`: if an org's fresh `raised` is below half its
    previous snapshot, keep the previous values and log `GUARD`. The API once
    returned an empty member list for the home team, which collapsed $4.5M to
    $117K.
  - Files: `app/dashboard.py`, `app/org_scraper.py`,
    `frontend/src/tabs/LeaderboardTab.tsx`, `frontend/src/types/index.ts`,
    `tests/conftest.py`, `tests/test_api_orgs.py`, `GEMINI.md`

## 2026-08-03: Pinned Python dependencies

- `3a21c40` · `app/requirements.txt` (new)
- There was no dependency manifest. `pip freeze` of the working venv.

## 2026-07-28: Leaderboard covers 55 orgs; top bar includes Kids

- `3b8913d`
- `ORGS` in `org_scraper.py` grew from 31 to 55 after a sweep of the full
  Pelotonia peloton list. It now includes Team Chipotle and 23 other parent or
  standalone orgs.
- The Raised (2026) KPI adds the current Kids campaign total and shows
  "incl. $X Pelotonia Kids". `/api/overview` exposes `kids_raised`.
- Repaired the backend test suite (stale since the June bundle split) and two
  frontend tests.
- Files: `app/dashboard.py`, `app/org_scraper.py`,
  `frontend/src/components/layout/KpiStrip.tsx`, `frontend/src/types/index.ts`,
  tests, docs

## 2026-07-27: True-up rebuilds every member's routes weekly

- `a8db8ad` · `app/pelotonia_scraper.py`, docs
- Route selections were frozen after first fetch: a rider who switched routes
  kept the old one for five months. `--trueup` now deletes all `member_routes`
  and re-fetches routes for every on-team member.

## 2026-07-24: Branch cleanup

- `eb78071` · `README.md`
- The mainline branch was renamed from `alloydb-migration` to `master`. Two dead
  ends are parked under `archive/*`. See README § Branches.

## 2026-07-17: Rider ID column; reconstructed org totals; "Registered" type

- **Members tab: Rider ID column** · `3d10bee`
  - Shows `members.public_id` (the Pelotonia rider ID). Sortable, searchable and
    in the CSV.
  - File: `frontend/src/tabs/MembersTab.tsx`
- **Leaderboard uses reconstructed org totals; "Registered" member type** ·
  `dd9c1db`
  - `org_scraper.py` stores `raised = SUM(direct child raised) +
    generalPelotonFunds` (`reconstruct_raised()`), not the API's raw
    `fundraising.raised`. That is the same rule as the top bar.
  - Member type order: Rider > Challenger > Volunteer > untyped but has a route →
    Rider > on a team but untyped → **Registered** > off-team → "—".
  - Files: `app/org_scraper.py`, `frontend/src/utils/memberType.ts`, `CLAUDE.md`

## 2026-06-26: Scraper skips prior-year routes

- `5395a23` · `app/pelotonia_scraper.py`
- A member with a 2025 route selected broke the foreign key and aborted the whole
  atomic scrape. Routes not in the current `routes` table are now skipped with a
  warning.

## 2026-06-24: Faster first load

- **Gzip and immutable caching** · `4e4108a` · `app/dashboard.py`
  - `/api/bundle` is gzipped once per DB change and cached (8.35 MB → 846 KB).
    JS and CSS are gzipped per response. `/assets/*` get
    `Cache-Control: immutable`. `index.html` stays `no-cache`.
- **Two-wave loading: `/api/bundle/core` then `/api/bundle/rest`** · `b4c7529`
  - Core (about 17 KB gzipped) holds what the first screen needs. Rest holds
    members, donations, donors, companies, org snapshots and the commitment gap.
    Tabs that need rest data show a loading placeholder until it arrives.
    `/api/bundle` still returns everything.
  - Files: `app/dashboard.py`, `frontend/src/api/client.ts`,
    `frontend/src/store/useDashboardStore.ts`,
    `frontend/src/components/shared/TabLoading.tsx`, four tab files, tests

## 2026-06-03: Official team total = members + team-level

- **All "Funds Raised" surfaces** · `b8c32a8`
  - Rules (see README § How the numbers are computed):
    - Org official = `SUM(sub-team raised) + parent.general_peloton_funds`. Never
      the parent's own `raised`, which the API sometimes collapses.
    - Sub-team official = the sub-team's own `teams.raised`.
    - tracked = `SUM(members.raised)`; team-level = official − tracked.
    - Display "$X from members + $Y team-level" under the total.
  - API: `/api/overview` gains `raised_tracked` and `raised_team_level`. Team
    breakdown rows gain `official_raised` and `team_level_raised`.
  - Files: `app/dashboard.py`, `app/daily_report.py`,
    `frontend/src/tabs/OverviewTab.tsx`, `frontend/src/tabs/InfographicsTab/*`,
    `frontend/src/types/index.ts`, `tests/test_api_overview.py`
- **Report tab uses the same breakdown** · `3dbc91e` ·
  `frontend/src/tabs/ReportTab.tsx`

## 2026-05-30: Org participant counts, weekly true-up, signup dates

- `6e781d1`
  - `org_scraper.py` counts riders, challengers and volunteers per org. It walks
    each org's sub-team tree (max depth 4), then reads each member profile's
    `participantTypes`. Profiles are cached in `org_member_profiles` for 14 days.
    New flags: `--skip-profiles` and `--refresh-all-profiles`.
  - `pelotonia_scraper.py`: `members.first_scraped` records when a member first
    appeared (shown as "Signed Up"). New `--trueup` mode soft-prunes members the
    roster no longer returns: clear `team_id`, zero the type flags, drop their
    routes, keep the row so donation history survives. It then re-fetches every
    profile.
  - Overview `raised` = sum of sub-team raised + parent general peloton funds.
  - Frontend: Signed Up column on Members, Riders column on Leaderboard, funds
    goal shown as `$XK`, Fundraising Growth footnote. The Report tab falls back to
    yesterday's snapshot in daily mode.
  - Absorbs the five May commits parked on `archive/superseded-may-fixes`.
- `d38a368`: docs: scheduling is cron only (systemd timers retired; they were
  double-running jobs).

## 2026-04-16: Anonymous corporate donors

- `4eea828` · `app/dashboard.py`
- Donations with `donor_name = 'Anonymous'` but a company `recognition_name` are
  grouped under the company instead of "Anonymous"
  (`COALESCE(NULLIF(NULLIF(donor_name, ''), 'Anonymous'), recognition_name, 'Anonymous')`).

## 2026-04-15: Donors tab: company affiliation and richer stats

- `019133e`
- Donors are grouped by `donor_name`, with the corporate `recognition_name` shown
  as an affiliation column. New recipient count and first and last donation
  dates. A hidden `LIMIT 25` was removed, so pagination walks the full list.
- Files: `app/dashboard.py`, `frontend/src/tabs/DonorsTab.tsx`,
  `frontend/src/components/modals/DonorRecipientsModal.tsx`,
  `frontend/src/types/index.ts`

## 2026-04-10: Mobile goals layout; scrape → deploy chained 3×/day

- `dd501be`
- The goals-panel arrow no longer mirrors past 80% progress. New 600 px
  breakpoint.
- Cron now chains scrape `&&` deploy and runs 3× a day. Before, the deploy fired
  on a timer and usually shipped the previous day's data.

## 2026-04-06: React frontend replaces the inline HTML dashboard

- `c9ae5ff` (102 files), `71de230` (favicon)
- New `frontend/`: a React + TypeScript + Vite single-page app, built to
  `frontend/dist/` and served by Flask's catch-all route. Zustand store, Chart.js
  with the datalabels plugin, CSS modules, Vitest tests.
- Data labels sized in canvas pixels. Dual-axis Fundraising Growth chart.
  Vertical route bars. Signup lines per participant type. Pelotonia arrow on the
  goals panel. Sortable member columns.
- Ticker API mapping: `currentYearRaised → pelotonia_total_raised`,
  `totalParticipants → pelotonia_member_count`,
  `allTimeRaised → pelotonia_all_time_raised`. Cached to `.ticker_cache.json`.
- SQLite `busy_timeout` so the scraper and Flask can share the file.
- Multi-stage Dockerfile: Node builds the frontend, Python serves it.

## 2026-03-26: Reporting accuracy

- `69105f3`
- `daily_snapshots` gains `riders_count`, `challengers_count` and
  `volunteers_count`, so deltas are tracked per type.
- First-year count includes riders only (it had counted every member type).
- Parent snapshot uses the API's `members_count`, not `COUNT(*)` from `members`.
- Fixed a crash on `captain: null`. `org_scraper.py` retries and skips runs below
  a minimum org count.
- Files: `app/daily_report.py`, `app/dashboard.py`, `app/org_scraper.py`,
  `app/pelotonia_scraper.py`

## 2026-03-18: Baseline

- `61f41c5`: initial commit. See the top of this file.
