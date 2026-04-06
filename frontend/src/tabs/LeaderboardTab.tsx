import { useState, useMemo, useCallback } from 'react';
import { useDashboardStore } from '../store/useDashboardStore';
import { money, pct } from '../utils/format';
import { PARENT_TEAM_ID, BRAND } from '../types/constants';
import { type Column } from '../components/shared/DataTable';
import { OrgRaisedChart } from '../components/charts/OrgRaisedChart';
import type { OrgSnapshot } from '../types';
import kpiStyles from '../styles/kpi.module.css';
import layoutStyles from '../styles/layout.module.css';

export function LeaderboardTab() {
  const orgs = useDashboardStore((s) => s.bundle?.orgLeaderboard ?? []);
  const [sortKey, setSortKey] = useState('raised');
  const [sortDir, setSortDir] = useState<'asc' | 'desc'>('desc');

  const handleSort = useCallback((key: string) => {
    if (key === sortKey) {
      setSortDir((d) => (d === 'asc' ? 'desc' : 'asc'));
    } else {
      setSortKey(key);
      setSortDir(key === 'name' ? 'asc' : 'desc');
    }
  }, [sortKey]);

  const sorted = useMemo(() => {
    const data = orgs.map((o, i) => ({ ...o, rank: i + 1, pctGoal: o.goal > 0 ? (o.raised / o.goal) * 100 : 0 }));
    return [...data].sort((a, b) => {
      let va: string | number = (a as Record<string, unknown>)[sortKey] as string | number;
      let vb: string | number = (b as Record<string, unknown>)[sortKey] as string | number;
      if (sortKey === 'name') {
        va = String(va || '').toLowerCase();
        vb = String(vb || '').toLowerCase();
      }
      if (va < vb) return sortDir === 'asc' ? -1 : 1;
      if (va > vb) return sortDir === 'asc' ? 1 : -1;
      return 0;
    });
  }, [orgs, sortKey, sortDir]);

  // KPIs
  const totalMembers = useMemo(() => orgs.reduce((s, o) => s + (o.members_count || 0), 0), [orgs]);
  const totalRaised = useMemo(() => orgs.reduce((s, o) => s + (o.raised || 0), 0), [orgs]);
  const huntington = useMemo(() => orgs.find((o) => o.team_id === PARENT_TEAM_ID), [orgs]);
  const huntingtonRank = useMemo(() => {
    const byRaised = [...orgs].sort((a, b) => (b.raised || 0) - (a.raised || 0));
    const idx = byRaised.findIndex((o) => o.team_id === PARENT_TEAM_ID);
    return idx >= 0 ? idx + 1 : '—';
  }, [orgs]);

  const huntingtonPct = totalRaised > 0 && huntington
    ? pct(huntington.raised || 0, totalRaised)
    : 0;

  type OrgRow = OrgSnapshot & { rank: number; pctGoal: number };

  const columns: Column<OrgRow>[] = useMemo(() => [
    { key: 'rank', label: '#', render: (_r, i) => i + 1 },
    { key: 'name', label: 'Organization', render: (r) => r.name || '—' },
    { key: 'members_count', label: 'Members', align: 'right', render: (r) => (r.members_count || 0).toLocaleString() },
    { key: 'sub_team_count', label: 'Sub-Teams', align: 'right', render: (r) => (r.sub_team_count || 0).toLocaleString() },
    { key: 'raised', label: 'Raised', align: 'right', render: (r) => money(r.raised || 0) },
    { key: 'goal', label: 'Goal', align: 'right', render: (r) => (r.goal > 0 ? money(r.goal) : '—') },
    { key: 'pctGoal', label: '% of Goal', align: 'right', render: (r) => (r.goal > 0 ? r.pctGoal.toFixed(1) + '%' : '—') },
    { key: 'all_time_raised', label: 'All-Time', align: 'right', render: (r) => money(r.all_time_raised || 0) },
  ], []);

  if (!orgs.length) {
    return (
      <div style={{ textAlign: 'center', padding: 40, color: '#888' }}>
        Organization tracking starts after running org_scraper.py
      </div>
    );
  }

  return (
    <div>
      {/* KPI Strip */}
      <div className={kpiStyles.kpiStrip}>
        <div className={kpiStyles.kpi}>
          <div className={kpiStyles.value}>{huntingtonRank}</div>
          <div className={kpiStyles.label}>Huntington Rank</div>
        </div>
        <div className={kpiStyles.kpi}>
          <div className={kpiStyles.value}>{money(huntington?.raised || 0)}</div>
          <div className={kpiStyles.label}>Huntington Raised</div>
        </div>
        <div className={kpiStyles.kpi}>
          <div className={kpiStyles.value}>{huntingtonPct}%</div>
          <div className={kpiStyles.label}>% of Pelotonia Total</div>
        </div>
        <div className={kpiStyles.kpi}>
          <div className={kpiStyles.value}>{totalMembers.toLocaleString()}</div>
          <div className={kpiStyles.label}>Total Members</div>
        </div>
      </div>

      {/* Table */}
      <div className={layoutStyles.card} style={{ margin: '0 24px 24px', overflowX: 'auto' }}>
        <div className={layoutStyles.cardTitle}>Organization Leaderboard</div>
        <table style={{ width: '100%', borderCollapse: 'collapse', fontSize: 13 }}>
          <thead>
            <tr>
              {columns.map((col) => (
                <th
                  key={col.key}
                  style={{
                    textAlign: (col.align ?? 'left') as 'left' | 'right' | 'center',
                    padding: '6px 8px',
                    borderBottom: `2px solid ${BRAND.green}`,
                    fontSize: 11,
                    textTransform: 'uppercase',
                    fontWeight: 600,
                    color: BRAND.forest,
                    cursor: 'pointer',
                    userSelect: 'none',
                  }}
                  onClick={() => handleSort(col.key)}
                >
                  {col.label}
                  {sortKey === col.key ? (sortDir === 'asc' ? ' \u25B2' : ' \u25BC') : ''}
                </th>
              ))}
            </tr>
          </thead>
          <tbody>
            {sorted.map((o, i) => {
              const isH = o.team_id === PARENT_TEAM_ID;
              return (
                <tr
                  key={o.team_id}
                  style={{
                    background: isH ? '#e8fce4' : undefined,
                    fontWeight: isH ? 700 : undefined,
                  }}
                >
                  {columns.map((col) => (
                    <td
                      key={col.key}
                      style={{
                        textAlign: (col.align ?? 'left') as 'left' | 'right' | 'center',
                        padding: '6px 8px',
                        borderBottom: '1px solid #eee',
                      }}
                    >
                      {col.render ? col.render(o, i) : String((o as Record<string, unknown>)[col.key] ?? '')}
                    </td>
                  ))}
                </tr>
              );
            })}
          </tbody>
        </table>
      </div>

      {/* Bar Chart */}
      <div className={layoutStyles.card} style={{ margin: '0 24px 24px' }}>
        <div className={layoutStyles.cardTitle}>Top 15 Organizations by 2026 Raised</div>
        <OrgRaisedChart />
      </div>
    </div>
  );
}
