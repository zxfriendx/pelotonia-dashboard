import { useMemo, useCallback } from 'react';
import { useDashboardStore } from '../store/useDashboardStore';
import { useSearch } from '../hooks/useSearch';
import { usePagination } from '../hooks/usePagination';
import { SearchBar } from '../components/shared/SearchBar';
import { Pagination } from '../components/shared/Pagination';
import { ExportButton } from '../components/shared/ExportButton';
import { moneyFull, shortTeam } from '../utils/format';
import type { Donation } from '../types';
import tableStyles from '../styles/table.module.css';
import layoutStyles from '../styles/layout.module.css';

function donorDisplay(d: Donation): string {
  if (d.anonymous_to_public) return d.recognition_name || 'Anonymous';
  return d.donor_name || d.recognition_name || '—';
}

function downloadCSV(rows: string[][], headers: string[], filename: string) {
  const escape = (v: string) => {
    const s = String(v ?? '');
    return s.includes(',') || s.includes('"') || s.includes('\n')
      ? '"' + s.replace(/"/g, '""') + '"'
      : s;
  };
  const lines = [headers.map(escape).join(',')];
  rows.forEach((r) => lines.push(r.map(escape).join(',')));
  const blob = new Blob([lines.join('\n')], { type: 'text/csv;charset=utf-8;' });
  const a = document.createElement('a');
  a.href = URL.createObjectURL(blob);
  a.download = filename;
  a.click();
  URL.revokeObjectURL(a.href);
}

const searchFn = (d: Donation, q: string) => {
  const donor = donorDisplay(d).toLowerCase();
  const recipient = (d.recipient_name || '').toLowerCase();
  const team = (d.team_name || '').toLowerCase();
  return donor.includes(q) || recipient.includes(q) || team.includes(q);
};

export function DonationsTab() {
  const donations = useDashboardStore((s) => s.bundle?.donations ?? []);

  const sorted = useMemo(
    () => [...donations].sort((a, b) => {
      const da = a.date || '';
      const db = b.date || '';
      return db.localeCompare(da);
    }),
    [donations],
  );

  const { query, setQuery, filtered } = useSearch(sorted, searchFn);
  const { page, totalPages, pageData, setPage, setPageSize, pageSize } = usePagination(filtered);

  const handleExport = useCallback(() => {
    if (!filtered.length) return;
    const headers = ['Date', 'Donor', 'Recipient', 'Team', 'Amount'];
    const rows = filtered.map((d) => [
      d.date ? d.date.substring(0, 10) : '',
      donorDisplay(d),
      d.recipient_name || '',
      shortTeam(d.team_name),
      String(d.amount || 0),
    ]);
    downloadCSV(rows, headers, 'huntington-donations.csv');
  }, [filtered]);

  return (
    <div>
      <div style={{ display: 'flex', alignItems: 'center', gap: 12, marginBottom: 12, flexWrap: 'wrap' }}>
        <div style={{ flex: 1, minWidth: 200 }}>
          <SearchBar value={query} onChange={setQuery} placeholder="Search donations..." />
        </div>
        <ExportButton onClick={handleExport} />
      </div>
      <div className={layoutStyles.card} style={{ overflowX: 'auto' }}>
        <table className={tableStyles.table}>
          <thead>
            <tr>
              <th>Date</th>
              <th>Donor</th>
              <th>Recipient</th>
              <th>Team</th>
              <th style={{ textAlign: 'right' }}>Amount</th>
            </tr>
          </thead>
          <tbody>
            {pageData.map((d) => (
              <tr key={d.opportunity_id}>
                <td>{d.date ? d.date.substring(0, 10) : '—'}</td>
                <td>
                  {d.anonymous_to_public
                    ? <i>{d.recognition_name || 'Anonymous'}</i>
                    : (d.donor_name || d.recognition_name || '—')}
                </td>
                <td>{d.recipient_name || '—'}</td>
                <td>{shortTeam(d.team_name)}</td>
                <td style={{ textAlign: 'right' }}>{moneyFull(d.amount)}</td>
              </tr>
            ))}
            {pageData.length === 0 && (
              <tr>
                <td colSpan={5} style={{ textAlign: 'center', color: '#888', padding: 24 }}>
                  No donations found
                </td>
              </tr>
            )}
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
  );
}
