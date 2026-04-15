import { useCallback } from 'react';
import { useDashboardStore } from '../store/useDashboardStore';
import { money } from '../utils/format';
import { useSearch } from '../hooks/useSearch';
import { usePagination } from '../hooks/usePagination';
import { downloadCSV } from '../utils/csvExport';
import { SearchBar } from '../components/shared/SearchBar';
import { Pagination } from '../components/shared/Pagination';
import type { DonorSummary } from '../types';
import tableStyles from '../styles/table.module.css';
import layoutStyles from '../styles/layout.module.css';

function formatDate(iso: string | null): string {
  if (!iso) return '—';
  const d = new Date(iso);
  if (isNaN(d.getTime())) return '—';
  return d.toLocaleDateString('en-US', { month: 'short', day: 'numeric', year: 'numeric' });
}

function splitAffiliations(raw: string | null): string[] {
  if (!raw) return [];
  return raw.split(',').map((s) => s.trim()).filter(Boolean);
}

export function DonorsTab() {
  const bundle = useDashboardStore((s) => s.bundle);
  const openModal = useDashboardStore((s) => s.openModal);

  const searchFn = useCallback(
    (d: DonorSummary, q: string) =>
      d.donor.toLowerCase().includes(q) ||
      (d.affiliations ?? '').toLowerCase().includes(q),
    [],
  );

  const donors = bundle?.donors ?? [];
  const { query, setQuery, filtered } = useSearch(donors, searchFn);
  const { page, totalPages, pageData, setPage, setPageSize, pageSize } =
    usePagination(filtered, 50);

  const handleRowClick = useCallback(
    (donorName: string) => {
      openModal({
        type: 'donorRecipients',
        data: { donorName },
      });
    },
    [openModal],
  );

  const handleExport = useCallback(() => {
    if (!filtered.length) return;
    const headers = [
      'Donor',
      'Affiliation / Company',
      'Total',
      'Transactions',
      'Recipients',
      'First Donation',
      'Last Donation',
    ];
    const rows = filtered.map((d) => [
      d.donor,
      d.affiliations ?? '',
      d.total || 0,
      d.cnt || 0,
      d.recipient_count || 0,
      d.first_donation ?? '',
      d.last_donation ?? '',
    ]);
    downloadCSV(rows, headers, 'huntington-donors.csv');
  }, [filtered]);

  if (!bundle) return null;

  return (
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
            Donors ({filtered.length})
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
          placeholder="Search donors or company..."
        />

        <div style={{ overflowX: 'auto' }}>
          <table className={tableStyles.table}>
            <thead>
              <tr>
                <th>#</th>
                <th>Donor Name</th>
                <th>Affiliation / Company</th>
                <th className="text-right">Total Donated</th>
                <th className="text-center"># Transactions</th>
                <th className="text-center">Recipients</th>
                <th className="text-right">Last Donation</th>
              </tr>
            </thead>
            <tbody>
              {pageData.map((d, i) => {
                const idx = (page - 1) * pageSize + i + 1;
                const affiliations = splitAffiliations(d.affiliations);
                const shown = affiliations.slice(0, 2).join(', ');
                const extra = affiliations.length > 2 ? ` +${affiliations.length - 2} more` : '';
                return (
                  <tr
                    key={`${d.donor}-${idx}`}
                    className={tableStyles.clickableRow}
                    onClick={() => handleRowClick(d.donor)}
                    title="Click to see recipients"
                  >
                    <td>{idx}</td>
                    <td>{d.donor}</td>
                    <td
                      style={{ color: affiliations.length ? 'inherit' : '#bbb' }}
                      title={affiliations.join(', ')}
                    >
                      {affiliations.length ? `${shown}${extra}` : '—'}
                    </td>
                    <td className="text-right">{money(d.total)}</td>
                    <td className="text-center">{d.cnt}</td>
                    <td className="text-center">{d.recipient_count}</td>
                    <td className="text-right">{formatDate(d.last_donation)}</td>
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
  );
}
