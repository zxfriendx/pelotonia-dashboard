import { useMemo, useCallback, useState } from 'react';
import { useDashboardStore } from '../store/useDashboardStore';
import { money, shortTeam } from '../utils/format';
import { useSearch } from '../hooks/useSearch';
import { usePagination } from '../hooks/usePagination';
import { downloadCSV } from '../utils/csvExport';
import { SearchBar } from '../components/shared/SearchBar';
import { Pagination } from '../components/shared/Pagination';
import { TabLoading } from '../components/shared/TabLoading';
import { CommitmentGapChart } from '../components/charts/CommitmentGapChart';
import type { CommitmentMember } from '../types';
import tableStyles from '../styles/table.module.css';
import layoutStyles from '../styles/layout.module.css';
import kpiStyles from '../styles/kpi.module.css';

type SortCol = 'name' | 'team' | 'committed' | 'raised' | 'shortfall' | 'pct';
type SortDir = 'asc' | 'desc';
type Filter = 'below' | 'all' | 'met';

export function CommitmentsTab() {
  const gap = useDashboardStore((s) => s.bundle?.commitmentGap);
  const restLoaded = useDashboardStore((s) => s.restLoaded);
  const restError = useDashboardStore((s) => s.restError);
  const openModal = useDashboardStore((s) => s.openModal);

  const [filter, setFilter] = useState<Filter>('below');
  const [sortCol, setSortCol] = useState<SortCol>('shortfall');
  const [sortDir, setSortDir] = useState<SortDir>('desc');

  const handleSort = useCallback((col: SortCol) => {
    setSortCol((prev) => {
      if (prev === col) {
        setSortDir((d) => (d === 'asc' ? 'desc' : 'asc'));
        return col;
      }
      setSortDir(col === 'name' || col === 'team' ? 'asc' : 'desc');
      return col;
    });
  }, []);

  const rows = useMemo(() => {
    const all = gap?.members ?? [];
    const subset =
      filter === 'below' ? all.filter((m) => m.shortfall > 0)
      : filter === 'met' ? all.filter((m) => m.shortfall === 0)
      : all;
    const dir = sortDir === 'asc' ? 1 : -1;
    return [...subset].sort((a, b) => {
      switch (sortCol) {
        case 'name': return dir * a.name.localeCompare(b.name);
        case 'team': return dir * (shortTeam(a.team_name || '') || '').localeCompare(shortTeam(b.team_name || '') || '');
        case 'committed': return dir * (a.committed_amount - b.committed_amount);
        case 'raised': return dir * (a.raised - b.raised);
        case 'shortfall': return dir * (a.shortfall - b.shortfall);
        case 'pct': return dir * (a.pct_fulfilled - b.pct_fulfilled);
        default: return 0;
      }
    });
  }, [gap, filter, sortCol, sortDir]);

  const searchFn = useCallback(
    (m: CommitmentMember, q: string) =>
      m.name.toLowerCase().includes(q) ||
      (m.public_id || '').toLowerCase().includes(q) ||
      (m.team_name || '').toLowerCase().includes(q),
    [],
  );
  const { query, setQuery, filtered } = useSearch(rows, searchFn);
  const { page, totalPages, pageData, setPage, setPageSize, pageSize } =
    usePagination(filtered, 50);

  const handleRowClick = useCallback(
    (m: CommitmentMember) => {
      openModal({ type: 'memberDonors', data: { publicId: m.public_id, name: m.name } });
    },
    [openModal],
  );

  const handleExport = useCallback(() => {
    if (!filtered.length) return;
    downloadCSV(
      filtered.map((m) => [
        m.public_id, m.name, shortTeam(m.team_name || '') || '',
        m.committed_amount, m.raised, m.shortfall, m.pct_fulfilled,
        m.committed_high_roller ? 'Yes' : '',
      ]),
      ['Rider ID', 'Name', 'Sub-Team', 'Committed', 'Raised', 'Shortfall', '% Fulfilled', 'High Roller'],
      'commitment-gap.csv',
    );
  }, [filtered]);

  if (!restLoaded) return <TabLoading label="commitments" error={restError} />;
  if (!gap) return <div style={{ textAlign: 'center', padding: 40, color: '#888' }}>No commitment data</div>;

  const s = gap.summary;

  return (
    <div>
      {/* KPI Cards */}
      <div className={kpiStyles.kpiStrip}>
        <div className={kpiStyles.kpi}>
          <div className={kpiStyles.value}>{money(s.shortfall_total)}</div>
          <div className={kpiStyles.label}>Outstanding Shortfall</div>
        </div>
        <div className={kpiStyles.kpi}>
          <div className={kpiStyles.value}>{s.below_count.toLocaleString()}</div>
          <div className={kpiStyles.label}>Below Commitment (of {s.committed_members.toLocaleString()})</div>
        </div>
        <div className={kpiStyles.kpi}>
          <div className={kpiStyles.value}>{s.zero_count.toLocaleString()}</div>
          <div className={kpiStyles.label}>$0 Raised</div>
        </div>
        <div className={kpiStyles.kpi}>
          <div className={kpiStyles.value}>{money(s.surplus_total)}</div>
          <div className={kpiStyles.label}>Surplus (Over-Raised)</div>
        </div>
      </div>

      <div className={layoutStyles.grid} style={{ gridTemplateColumns: '1fr' }}>
        <div className={layoutStyles.card}>
          <div className={layoutStyles.cardTitle}>Shortfall Over Time</div>
          <CommitmentGapChart />
          <div style={{ fontSize: 12, color: '#888', fontStyle: 'italic', marginTop: 8 }}>
            Reconstructed from record-by-record donations against current commitments, so the
            latest point runs above the authoritative shortfall ({money(s.shortfall_total)}) —
            donations to members with hidden donor lists aren&apos;t individually recorded.
          </div>
        </div>

        <div className={layoutStyles.card}>
          <div
            style={{
              display: 'flex',
              justifyContent: 'space-between',
              alignItems: 'center',
              marginBottom: '12px',
              flexWrap: 'wrap',
              gap: 8,
            }}
          >
            <h2 className={layoutStyles.cardTitle} style={{ marginBottom: 0 }}>
              Members ({filtered.length.toLocaleString()})
            </h2>
            <div style={{ display: 'flex', gap: 8, alignItems: 'center' }}>
              {(['below', 'met', 'all'] as Filter[]).map((f) => (
                <button
                  key={f}
                  onClick={() => setFilter(f)}
                  style={{
                    padding: '6px 14px',
                    border: '1px solid #ddd',
                    borderRadius: '6px',
                    background: filter === f ? '#1a5632' : '#fff',
                    color: filter === f ? '#fff' : '#333',
                    cursor: 'pointer',
                    fontSize: '13px',
                  }}
                >
                  {f === 'below' ? 'Below Commitment' : f === 'met' ? 'Met / Exceeded' : 'All'}
                </button>
              ))}
              <button
                onClick={handleExport}
                style={{
                  padding: '6px 14px',
                  border: '1px solid #ddd',
                  borderRadius: '6px',
                  background: '#fff',
                  cursor: 'pointer',
                  fontSize: '13px',
                }}
              >
                Export CSV
              </button>
            </div>
          </div>

          <SearchBar
            value={query}
            onChange={setQuery}
            placeholder="Search by name, rider ID, team..."
          />

          <div style={{ overflowX: 'auto' }}>
            <table className={tableStyles.table}>
              <thead>
                <tr>
                  <th>#</th>
                  <th className={tableStyles.sortable} onClick={() => handleSort('name')}>
                    Name {sortCol === 'name' ? (sortDir === 'asc' ? '▲' : '▼') : ''}
                  </th>
                  <th className={tableStyles.sortable} onClick={() => handleSort('team')}>
                    Sub-Team {sortCol === 'team' ? (sortDir === 'asc' ? '▲' : '▼') : ''}
                  </th>
                  <th className={`text-right ${tableStyles.sortable}`} onClick={() => handleSort('committed')}>
                    Committed {sortCol === 'committed' ? (sortDir === 'asc' ? '▲' : '▼') : ''}
                  </th>
                  <th className={`text-right ${tableStyles.sortable}`} onClick={() => handleSort('raised')}>
                    Raised {sortCol === 'raised' ? (sortDir === 'asc' ? '▲' : '▼') : ''}
                  </th>
                  <th className={`text-right ${tableStyles.sortable}`} onClick={() => handleSort('shortfall')}>
                    Shortfall {sortCol === 'shortfall' ? (sortDir === 'asc' ? '▲' : '▼') : ''}
                  </th>
                  <th className={`text-right ${tableStyles.sortable}`} onClick={() => handleSort('pct')}>
                    % Fulfilled {sortCol === 'pct' ? (sortDir === 'asc' ? '▲' : '▼') : ''}
                  </th>
                </tr>
              </thead>
              <tbody>
                {pageData.map((m, i) => (
                  <tr
                    key={m.public_id}
                    onClick={() => handleRowClick(m)}
                    style={{ cursor: 'pointer' }}
                  >
                    <td>{(page - 1) * pageSize + i + 1}</td>
                    <td>
                      {m.name}
                      {m.committed_high_roller ? (
                        <span style={{ marginLeft: 6, fontSize: 11, color: '#b8860b', fontWeight: 700 }}>HR</span>
                      ) : null}
                    </td>
                    <td>{shortTeam(m.team_name || '') || '—'}</td>
                    <td className="text-right">{money(m.committed_amount)}</td>
                    <td className="text-right">{money(m.raised)}</td>
                    <td className="text-right" style={{ color: m.shortfall > 0 ? '#c0392b' : '#1a5632', fontWeight: 600 }}>
                      {m.shortfall > 0 ? money(m.shortfall) : '✓ met'}
                    </td>
                    <td className="text-right">{m.pct_fulfilled.toFixed(0)}%</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>

          <Pagination
            page={page}
            totalPages={totalPages}
            pageSize={pageSize}
            setPage={setPage}
            setPageSize={setPageSize}
          />
        </div>
      </div>
    </div>
  );
}
