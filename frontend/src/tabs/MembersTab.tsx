import { useMemo, useCallback, useEffect, useRef, useState } from 'react';
import { useDashboardStore } from '../store/useDashboardStore';
import { money, shortTeam } from '../utils/format';
import { memberType } from '../utils/memberType';
import { useSearch } from '../hooks/useSearch';
import { usePagination } from '../hooks/usePagination';
import { downloadCSV } from '../utils/csvExport';
import { SearchBar } from '../components/shared/SearchBar';
import { Pagination } from '../components/shared/Pagination';
import type { Member } from '../types';
import tableStyles from '../styles/table.module.css';
import layoutStyles from '../styles/layout.module.css';
import kpiStyles from '../styles/kpi.module.css';

type SortCol = 'name' | 'team' | 'type' | 'years' | 'raised' | 'allTime';
type SortDir = 'asc' | 'desc';

function parseTags(tagsStr: string): string[] {
  try {
    return JSON.parse(tagsStr || '[]');
  } catch {
    return [];
  }
}

export function MembersTab() {
  const bundle = useDashboardStore((s) => s.bundle);
  const openModal = useDashboardStore((s) => s.openModal);
  const memberHighlight = useDashboardStore((s) => s.memberHighlight);
  const clearMemberHighlight = useDashboardStore((s) => s.clearMemberHighlight);
  const highlightRowRef = useRef<HTMLTableRowElement | null>(null);

  const [sortCol, setSortCol] = useState<SortCol>('raised');
  const [sortDir, setSortDir] = useState<SortDir>('desc');

  const handleSort = useCallback((col: SortCol) => {
    setSortCol((prev) => {
      if (prev === col) {
        setSortDir((d) => (d === 'asc' ? 'desc' : 'asc'));
        return col;
      }
      setSortDir(col === 'name' || col === 'team' || col === 'type' ? 'asc' : 'desc');
      return col;
    });
  }, []);

  const sortedMembers = useMemo(() => {
    if (!bundle) return [];
    const dir = sortDir === 'asc' ? 1 : -1;
    return [...bundle.members].sort((a, b) => {
      switch (sortCol) {
        case 'name': return dir * a.name.localeCompare(b.name);
        case 'team': return dir * (shortTeam(a.team_name) || '').localeCompare(shortTeam(b.team_name) || '');
        case 'type': return dir * memberType(a).localeCompare(memberType(b));
        case 'years': return dir * ((a.years_active || 0) - (b.years_active || 0));
        case 'raised': return dir * ((a.raised || 0) - (b.raised || 0));
        case 'allTime': return dir * ((a.all_time_raised || 0) - (b.all_time_raised || 0));
        default: return 0;
      }
    });
  }, [bundle, sortCol, sortDir]);

  const searchFn = useCallback(
    (m: Member, q: string) =>
      m.name.toLowerCase().includes(q) ||
      (m.team_name || '').toLowerCase().includes(q) ||
      (m.tags || '').toLowerCase().includes(q) ||
      (m.ride_type || '').toLowerCase().includes(q) ||
      (memberType(m) === 'Rider' && 'rider'.includes(q)) ||
      (memberType(m) === 'Challenger' && 'challenger'.includes(q)),
    [],
  );

  const { query, setQuery, filtered } = useSearch(sortedMembers, searchFn);
  const { page, totalPages, pageData, setPage, setPageSize, pageSize } =
    usePagination(filtered, 50);

  // Cross-tab navigation: when memberHighlight is set, apply search and highlight
  useEffect(() => {
    if (memberHighlight) {
      setQuery(memberHighlight.name);
      const timer = setTimeout(() => {
        clearMemberHighlight();
      }, 2500);
      return () => clearTimeout(timer);
    }
  }, [memberHighlight, setQuery, clearMemberHighlight]);

  // Scroll to highlighted row
  useEffect(() => {
    if (memberHighlight && highlightRowRef.current) {
      highlightRowRef.current.scrollIntoView({ behavior: 'smooth', block: 'center' });
    }
  }, [memberHighlight, pageData]);

  const handleRowClick = useCallback(
    (m: Member) => {
      openModal({
        type: 'memberDonors',
        data: { publicId: m.public_id, name: m.name },
      });
    },
    [openModal],
  );

  const handleExport = useCallback(() => {
    if (!filtered.length) return;
    const headers = [
      'Name',
      'Sub-Team',
      'Type',
      'Ride',
      'Committed',
      'Raised (2026)',
      'All-Time Raised',
      'Tags',
      'Captain',
    ];
    const rows = filtered.map((m) => [
      m.name,
      shortTeam(m.team_name),
      memberType(m),
      m.route_names || m.ride_type || '',
      m.committed_amount || 0,
      m.raised || 0,
      m.all_time_raised || 0,
      parseTags(m.tags).join(', '),
      m.is_captain ? 'Yes' : '',
    ]);
    downloadCSV(rows, headers, 'huntington-members.csv');
  }, [filtered]);

  if (!bundle) return null;

  const { donations } = bundle;
  const uniqueDonors = new Set(donations.map((d) =>
    d.anonymous_to_public
      ? (d.recognition_name || 'Anonymous')
      : (d.donor_name || d.recognition_name || 'Unknown')
  )).size;
  const membersWithDonors = new Set(donations.map((d) => d.recipient_public_id)).size;
  const avgDonorsPerMember =
    membersWithDonors > 0 ? (uniqueDonors / membersWithDonors).toFixed(1) : '0';

  return (
    <div>
      {/* KPI Cards */}
      <div className={kpiStyles.kpiStrip}>
        <div className={kpiStyles.kpi}>
          <div className={kpiStyles.value}>{sortedMembers.length.toLocaleString()}</div>
          <div className={kpiStyles.label}>Total Members</div>
        </div>
        <div className={kpiStyles.kpi}>
          <div className={kpiStyles.value}>{uniqueDonors.toLocaleString()}</div>
          <div className={kpiStyles.label}>Unique Donors</div>
        </div>
        <div className={kpiStyles.kpi}>
          <div className={kpiStyles.value}>{avgDonorsPerMember}</div>
          <div className={kpiStyles.label}>Avg Donors / Member</div>
        </div>
      </div>

      <div className={layoutStyles.grid} style={{ gridTemplateColumns: '1fr' }}>
        <div className={layoutStyles.card}>
          <div
            style={{
              display: 'flex',
              justifyContent: 'space-between',
              alignItems: 'center',
              marginBottom: '12px',
            }}
          >
            <h2 className={layoutStyles.cardTitle} style={{ marginBottom: 0 }}>
              Members ({filtered.length})
            </h2>
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

          <SearchBar
            value={query}
            onChange={setQuery}
            placeholder="Search by name, team, type, tags..."
          />

          <div style={{ overflowX: 'auto' }}>
            <table className={tableStyles.table}>
              <thead>
                <tr>
                  <th>#</th>
                  <th className={tableStyles.sortable} onClick={() => handleSort('name')}>
                    Name {sortCol === 'name' ? (sortDir === 'asc' ? '\u25B2' : '\u25BC') : ''}
                  </th>
                  <th className={tableStyles.sortable} onClick={() => handleSort('team')}>
                    Sub-Team {sortCol === 'team' ? (sortDir === 'asc' ? '\u25B2' : '\u25BC') : ''}
                  </th>
                  <th className={`text-center ${tableStyles.sortable}`} onClick={() => handleSort('type')}>
                    Type {sortCol === 'type' ? (sortDir === 'asc' ? '\u25B2' : '\u25BC') : ''}
                  </th>
                  <th>Ride</th>
                  <th className={`text-right ${tableStyles.sortable}`} onClick={() => handleSort('years')}>
                    Years {sortCol === 'years' ? (sortDir === 'asc' ? '\u25B2' : '\u25BC') : ''}
                  </th>
                  <th className={`text-right ${tableStyles.sortable}`} onClick={() => handleSort('raised')}>
                    Raised (2026) {sortCol === 'raised' ? (sortDir === 'asc' ? '\u25B2' : '\u25BC') : ''}
                  </th>
                  <th className={`text-right ${tableStyles.sortable}`} onClick={() => handleSort('allTime')}>
                    All-Time {sortCol === 'allTime' ? (sortDir === 'asc' ? '\u25B2' : '\u25BC') : ''}
                  </th>
                  <th>Tags</th>
                </tr>
              </thead>
              <tbody>
                {pageData.map((m, i) => {
                  const isHighlighted =
                    memberHighlight?.publicId === m.public_id;
                  const idx = (page - 1) * pageSize + i + 1;
                  const ptype = memberType(m);
                  const rtype = m.route_names || m.ride_type || '\u2014';
                  const tags = parseTags(m.tags);

                  return (
                    <tr
                      key={m.public_id}
                      ref={isHighlighted ? highlightRowRef : undefined}
                      className={`${tableStyles.clickableRow} ${isHighlighted ? tableStyles.highlightRow : ''}`}
                      onClick={() => handleRowClick(m)}
                      title="Click to see donations"
                    >
                      <td>{idx}</td>
                      <td>
                        {m.is_captain ? '\u2B50 ' : ''}
                        {m.name}
                      </td>
                      <td>{shortTeam(m.team_name)}</td>
                      <td className="text-center">{ptype}</td>
                      <td>{rtype}</td>
                      <td className="text-right">{m.years_active || '\u2014'}</td>
                      <td className="text-right">{money(m.raised)}</td>
                      <td className="text-right">{money(m.all_time_raised)}</td>
                      <td>
                        {m.is_cancer_survivor ? (
                          <span className={tableStyles.badgeSurvivor}>Survivor</span>
                        ) : null}
                        {m.committed_high_roller ? (
                          <span className={tableStyles.badgeHr}>High Roller</span>
                        ) : null}
                        {tags
                          .filter((t) => !t.includes('High Roller'))
                          .map((t) => (
                            <span key={t} className={tableStyles.badgeTag}>
                              {t}
                            </span>
                          ))}
                      </td>
                    </tr>
                  );
                })}
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
