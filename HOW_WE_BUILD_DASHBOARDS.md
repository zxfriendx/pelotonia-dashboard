# How We Build Dashboards Like This

A short field guide to the architecture, choices, and habits behind the Pelotonia
dashboard — written so another team can copy the recipe, not just admire it.

---

## TL;DR — The Shape of It

```
  Data sources (APIs, web pages)
        │   scraped on a schedule
        ▼
  SQLite database  ──►  Flask API (one fat /api/bundle endpoint)
                              │
                              ▼
                   React + TypeScript SPA (Vite build)
                              │
                       served back by the same Flask app
```

One small Python backend, one modern frontend, one file-based database, packaged
in a container and deployed to Cloud Run. No Kubernetes cluster to babysit, no
managed database to pay for, no microservices. **The whole thing is small on
purpose**, and that's most of why it's good.

---

## What It's Built On

| Layer | Choice | Why |
|-------|--------|-----|
| **Frontend framework** | React 19 + TypeScript | Component reuse, type safety catches bugs before they ship |
| **Build tool** | Vite | Sub-second dev reloads, tiny optimized production bundle |
| **State** | Zustand | One tiny store, no Redux boilerplate |
| **Charts** | Chart.js + react-chartjs-2 + datalabels plugin | Canvas-based, fast, looks good, free |
| **Backend** | Flask (Python) | ~one file, serves both the API and the built frontend |
| **Database** | SQLite (a single file) | Zero-ops, fast for read-heavy dashboards, version-controllable |
| **Data collection** | Python scrapers on cron | Decoupled from serving — the app never waits on a slow API |
| **Packaging** | Docker (`python:3.12-slim`) | Reproducible, the DB is baked into the image |
| **Hosting** | GCP Cloud Run | Scales to zero, pay-per-use, one deploy command |

The dependency list is deliberately short. Frontend runtime deps: React,
Chart.js, Zustand. Backend: Flask, requests, Pillow. That's it. Every dependency
is a thing you have to learn, update, and debug — so we keep the list small.

---

## The Five Ideas That Make It Work

### 1. Separate *collecting* data from *serving* data
Scrapers run on a schedule (3×/day via cron), write to SQLite in a single atomic
transaction, and exit. The dashboard only ever **reads**. This means:
- The UI is always fast — it never waits on a third-party API.
- A flaky upstream source can't take the dashboard down.
- Data updates are an implementation detail the user never feels.

> **Takeaway for your team:** don't fetch live from slow sources on every page
> load. Pull on a schedule into your own store, and serve from that.

### 2. One endpoint, not fifty
The frontend calls a single `/api/bundle` that returns *all* the data sets in one
response. The backend caches that bundle and only rebuilds it when the database
file actually changes (mtime check). Result: most requests are served from memory,
the frontend makes one round trip, and there's no waterfall of API calls.

> **Takeaway:** for a dashboard, a few big payloads beat many small ones. Cache
> aggressively and invalidate on a signal you already have (here, file mtime).

### 3. Pick boring, file-based infrastructure where you can
SQLite is "just a file." It's checked into the workflow, baked into the container
image, and needs zero operational care. For a read-heavy analytics dashboard with
one writer (the scraper), it's not a compromise — it's the *right* tool. We avoided
a managed database entirely.

> **Takeaway:** match the tool to the load. Most internal dashboards are read-heavy
> with a single writer. You probably don't need Postgres-in-the-cloud.

### 4. TypeScript end to end on the frontend
Every data set has a typed shape (`frontend/src/types/`). When the backend's data
changes, the type errors tell you exactly what to fix in the UI before anything
reaches a user. This is the single biggest reason the dashboard rarely breaks.

### 5. Deploy with one command, automatically
`deploy-gcp.sh` builds the image and ships it to Cloud Run. It's *chained* to the
scraper in cron so a deploy only happens after fresh data is committed — no fixed
timer racing the data. The pipeline is: **scrape → commit → build → deploy**, in
that order, every time.

---

## Why It's Responsive (and Looks Good)

Responsiveness here means two things — it adapts to screen size, and it feels fast.

**Adapts to any screen.** Three deliberate CSS breakpoints:
- **900px** — multi-column grids collapse to fewer columns
- **768px** — the tab bar becomes horizontally scrollable instead of wrapping
- **600px** — full mobile layout

Plus two defensive rules that prevent the classic dashboard bug where a chart or
card blows out the layout:
- Cards use `min-width: 0; overflow: hidden` so CSS grid can't overflow
- Chart containers use `max-width: 100%`

**Feels fast.**
- Vite produces a small, code-split production bundle.
- The single cached `/api/bundle` call means one fast round trip, then everything
  is instant tab-to-tab (the data is already in the browser).
- Chart.js renders to canvas, which stays smooth even with lots of data points.

**Looks intentional.** Charts share a visual language (consistent colors, data
labels only shown when they actually fit — measured in pixels, not guessed), the
brand's real asset (the Pelotonia arrow) is used in the UI, and timestamps are
shown in friendly local time. Polish is in the small, consistent decisions.

---

## How To Copy The Recipe

1. **Start with the data.** Write a scraper/loader that pulls your sources into a
   local SQLite file on a schedule. Make its writes atomic. Get this solid first.
2. **Put a thin API in front of it.** One Flask app, one bundled read endpoint,
   cache it, invalidate on data change.
3. **Build the UI in React + TypeScript with Vite.** Type your data sets. One
   small state store (Zustand). Tabs for sections.
4. **Use one charting library consistently** rather than five fancy ones.
5. **Add the three responsive breakpoints early**, not at the end. Test on a phone.
6. **Containerize and deploy to something that scales to zero** (Cloud Run). One
   deploy script, chained after the data refresh.

The meta-lesson: **keep every layer as small as the job allows.** Small data
store, small API, short dependency list, one deploy command. The "good" feeling
users are responding to is mostly the absence of accidental complexity.

---

## File Map (where to look in this repo)

- `app/dashboard.py` — the entire backend: API + serves the frontend
- `app/*_scraper.py` — the scheduled data collectors
- `app/pelotonia_data.db` — the SQLite database (the whole data layer)
- `frontend/src/tabs/` — each dashboard tab as a React component
- `frontend/src/types/` — the typed data contracts
- `Dockerfile` / `deploy-gcp.sh` — packaging and one-command deploy
- `CLAUDE.md` — the deep technical reference for everything above
