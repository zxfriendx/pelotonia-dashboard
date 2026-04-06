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

export function DonorsTab() {
  const bundle = useDashboardStore((s) => s.bundle);
  const openModal = useDashboardStore((s) => s.openModal);

  const searchFn = useCallback(
    (d: DonorSummary, q: string) => d.donor.toLowerCase().includes(q),
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
    const headers = ['Donor', 'Total', 'Transactions'];
    const rows = filtered.map((d) => [d.donor, d.total || 0, d.cnt || 0]);
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
          placeholder="Search donors..."
        />

        <div style={{ overflowX: 'auto' }}>
          <table className={tableStyles.table}>
            <thead>
              <tr>
                <th>#</th>
                <th>Donor Name</th>
                <th className="text-right">Total Donated</th>
                <th className="text-center"># Transactions</th>
              </tr>
            </thead>
            <tbody>
              {pageData.map((d, i) => {
                const idx = (page - 1) * pageSize + i + 1;
                return (
                  <tr
                    key={`${d.donor}-${idx}`}
                    className={tableStyles.clickableRow}
                    onClick={() => handleRowClick(d.donor)}
                    title="Click to see recipients"
                  >
                    <td>{idx}</td>
                    <td>{d.donor}</td>
                    <td className="text-right">{money(d.total)}</td>
                    <td className="text-center">{d.cnt}</td>
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
