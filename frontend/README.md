# Frontend

The dashboard's single-page app: React 19, TypeScript, Vite, Zustand, Chart.js.
The project overview, data rules and API reference are in the
[root README](../README.md).

## Commands

```bash
npm ci            # install
npm run dev       # Vite on :5173, proxies /api to Flask on :5050
npm run build     # type-check (tsc -b) and build to dist/, which Flask serves
npm test          # Vitest (jsdom + Testing Library)
npm run lint      # ESLint
```

Run the Flask API first for `npm run dev`:
`app/.venv/bin/python app/dashboard.py --port 5050` from the repo root.

## How data loads

`store/useDashboardStore.ts` fetches `/api/bundle/core` first and renders the
Overview, KPI strip, Teams, Routes, Kids and Leaderboard. It then fetches
`/api/bundle/rest` in the background. Tabs that need rest data (Members,
Donations, Donors, Companies, Commitments) show `TabLoading` until `restLoaded`
is true. Response types live in `types/index.ts`; keep them in step with
`app/dashboard.py`.

## Where things go

| Folder | Contents |
|--------|----------|
| `tabs/` | One component per tab. `App.tsx` maps tab IDs to them. |
| `components/layout/` | Closed banner, header, KPI strip, progress bar, tab bar, footer |
| `components/charts/` | One component per chart |
| `components/modals/` | Drill-down modals, opened through the store's `openModal` and rendered by `ModalRouter` |
| `components/shared/` | Table, pagination, search bar, KPI card, loading placeholder |
| `hooks/` | `useSearch`, `usePagination` |
| `utils/` | Money and date formatting, CSV export, member-type rules, editable targets |
| `types/constants.ts` | Season dates, goals, brand colors |
| `styles/` | CSS modules; `variables.css` holds the brand tokens |

## Conventions

- `chartjs-plugin-datalabels` is registered globally. Set
  `datalabels: { display: false }` on any chart that shouldn't show labels.
- Derive arrays from the store inside `useMemo`, as in
  `useMemo(() => bundle?.teams ?? [], [bundle])`. A bare `?? []` makes a new array
  on every render and defeats memoized chart data.
- Use the brand tokens in `styles/variables.css`. They come from Pelotonia's
  official asset guidelines.
- Layout breakpoints are 900 px, 768 px and 600 px.

## Tests

Tests live in `__tests__/`, with a shared bundle fixture in
`__tests__/fixtures/bundleData.ts`. They cover the store's two-wave loading,
shared components, the Members and Leaderboard tabs, and the utilities.
