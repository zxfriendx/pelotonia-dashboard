# Pelotonia Scraper — Technical Guide

## Overview

`pelotonia_scraper.py` collects team, member, donation, and route data from the Pelotonia API into a local SQLite database (`pelotonia_data.db`). It supports two modes: a full scrape and an optimized incremental scrape designed to minimize API calls as the team scales.

## API

- **Base URL**: `https://pelotonia-p3-middleware-production.azurewebsites.net/api/`
- **Authentication**: None (public API, no keys required)
- **Rate limiting**: Not documented; the scraper uses a 0.5s delay between requests (`REQUEST_DELAY`)
- **Pagination**: Header-based — requests send `Pagination-Page` and `Pagination-Limit` headers; responses include `Pagination-Total` for total record count. The scraper auto-paginates, fetching additional pages until all records are retrieved.

### Key Endpoints

| Endpoint | Returns | Used For |
|----------|---------|----------|
| `peloton/{id}` | Team detail + fundraising | Team goals, raised amounts |
| `search/pelotons?query=huntington` | Team list | Discovering sub-teams |
| `peloton/{id}/members` | Member list (paginated) | Roster, basic fundraising |
| `user/{id}` | Extended profile | Participation type, tags, story |
| `user/{id}/routes` | Route selections | Which ride/route each member chose |
| `user/{id}/donations` | Donation list (paginated) | Donor names, amounts, dates |
| `event` | Current event + rides | Ride/route catalog |
| `ride/{id}/routes` | Route details | Distance, commitment, capacity |
| `events/all` | Historical events | Year-over-year data |

## Incremental Scrape Strategy

The incremental scrape (`--incremental`) is designed to keep API calls near-constant regardless of team size. It categorizes data by volatility:

### Always refresh (fixed cost: ~34 calls)

These change frequently and are cheap to fetch:

1. **Rides & routes** (3 calls) — `event` + `ride/{id}/routes` x2. Route catalog rarely changes but is tiny.
2. **Teams** (17 calls) — 1 parent + 1 search + 15 sub-team details. Fundraising totals change daily.
3. **Member lists** (15 calls) — One paginated call per sub-team (auto-paginates if >200 members). Detects new members, team changes, and departures.

### Fetch only when needed (variable cost)

4. **Extended profiles** — Only fetched for:
   - **New members**: not in the DB before this run
   - **Stale profiles**: `first_name IS NULL` (profile fetch failed previously) or all participation flags are 0 (may be pending approval)
   - At steady state: **0 calls**

5. **Route selections** — Only fetched for members **not yet in the `member_routes` table**. Once a member's routes are stored, they're not re-fetched. Route changes after initial selection are rare.
   - At steady state: **0 calls**

6. **Donations** — Only fetched for members whose `raised` amount changed since the last scrape. The member list API returns current `raised` values, so we compare before/after to detect changes.
   - At steady state with no new donations: **0 calls**

### API call projections

| Team Size | Fixed | Profiles (new) | Routes (new) | Donations (changed) | **Total** |
|-----------|-------|----------------|--------------|---------------------|-----------|
| 300 (now) | 34 | 0 | 0 | 0 | **~34** |
| 500 | 34 | 0 | 0 | 0 | **~34** |
| 1,000 | 35 | 0 | 0 | 0 | **~35** |
| 2,000 | 36 | 0 | 0 | 0 | **~36** |

The "fixed" count grows slightly with pagination (1 extra call per 200 members in a sub-team), but the variable costs stay at zero once all members are profiled and have route data.

**During active signup periods** (e.g., 50 new members join in a day):

| | Fixed | Profiles | Routes | Donations | **Total** |
|--|-------|----------|--------|-----------|-----------|
| 50 new signups | 35 | 50 | 50 | ~5 | **~140** |

Still well within reason, and it's a one-time cost per new member.

## Member Lifecycle Handling

### New signups (pending approval)

When a member registers for the team, they may need captain approval before appearing on the roster. The scraper handles this naturally:

- **Not yet approved**: The member won't appear in `peloton/{id}/members` at all, so we don't see them.
- **Just approved**: They appear in the member list. The scraper detects them as new (not in `pre_raised`), fetches their profile and routes.
- **Incomplete profile**: Many newly-approved members have `is_rider=0, is_challenger=0, is_volunteer=0` because they haven't finalized their participation type. The scraper marks these as "stale" and re-fetches their profile on every run until the flags are set.

### Team changes

If a member moves from one sub-team to another:
- The member list scrape uses `ON CONFLICT(public_id) DO UPDATE SET team_id=excluded.team_id`, so the team change is captured automatically.
- The scraper logs: `MOVED: Jane Smith from a0s3t00000... -> a0s3t00000...`

### Cancellations / removals

If a member disappears from all team rosters:
- The scraper compares the set of members seen today vs. the set in the DB.
- Disappeared members are **logged but not deleted**: `GONE: Jane Smith (was on team a0s3t00000...)`
- Their `last_scraped` date goes stale, making them easy to query (`WHERE last_scraped < today`).
- We don't delete because disappearances can be temporary (pending re-approval, admin error, etc.).

## Pagination

The API defaults to 20 results per page. The scraper requests 200 per page and auto-paginates using the `Pagination-Total` response header:

```
Request:  Pagination-Page: 1, Pagination-Limit: 200
Response: Pagination-Total: 224
          → fetches page 2 automatically to get remaining 24
```

This is important for Consumer Regional Bank which has 224+ members.

## Database Schema

### Core tables
- **teams** (15 rows) — Team metadata + fundraising. Has `goal_override` column (added via ALTER TABLE) that persists across scraper runs.
- **members** (~311 rows) — One row per person. Basic data from member list, extended data from profile API.
- **donations** (~566 rows) — Individual donation records with donor info.
- **member_routes** (~260 rows) — Which route each member selected.
- **daily_snapshots** — One row per team per day, tracking fundraising progress over time.

### Supporting tables
- **rides** / **routes** — Ride catalog (Signature Ride, Gravel Day) and route details.
- **events** — Historical event metadata (2012-2026).
- **donor_identities** — Cross-referenced anonymous donor names.

## goal_override

The `goal_override` column on the `teams` table lets you override the API-provided goal. The scraper uses `INSERT ... ON CONFLICT DO UPDATE` that explicitly excludes `goal_override`, so manual overrides persist across runs. The dashboard reads `COALESCE(goal_override, goal)`.

To set:
```python
conn.execute("UPDATE teams SET goal_override = 6000000 WHERE parent_id IS NULL")
```

## Running

```bash
# Full scrape (all profiles, all routes, all donations — slow)
.venv/bin/python pelotonia_scraper.py

# Incremental scrape (recommended for daily use)
.venv/bin/python pelotonia_scraper.py --incremental
```

### Systemd automation
- `pelotonia-scraper.timer` — fires daily at 11:00 UTC (7am ET)
- `pelotonia-scraper.service` — runs `--incremental`, triggers GCP deploy on success
- Check: `systemctl --user status pelotonia-scraper.timer`
- Logs: `journalctl --user -u pelotonia-scraper.service`
