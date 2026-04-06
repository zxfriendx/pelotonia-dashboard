import { useCallback } from 'react';
import { useDashboardStore } from '../store/useDashboardStore';
import { money } from '../utils/format';
import { useSearch } from '../hooks/useSearch';
import { usePagination } from '../hooks/usePagination';
import { downloadCSV } from '../utils/csvExport';
import { SearchBar } from '../components/shared/SearchBar';
import { Pagination } from '../components/shared/Pagination';
import type { CompanySummary } from '../types';
import tableStyles from '../styles/table.module.css';
import layoutStyles from '../styles/layout.module.css';

export function CompaniesTab() {
  const bundle = useDashboardStore((s) => s.bundle);
  const openModal = useDashboardStore((s) => s.openModal);

  const searchFn = useCallback(
    (c: CompanySummary, q: string) => c.company.toLowerCase().includes(q),
    [],
  );

  const companies = bundle?.companies ?? [];
  const { query, setQuery, filtered } = useSearch(companies, searchFn);
  const { page, totalPages, pageData, setPage, setPageSize, pageSize } =
    usePagination(filtered, 50);

  const handleRowClick = useCallback(
    (companyName: string) => {
      openModal({
        type: 'companyDetail',
        data: { companyName },
      });
    },
    [openModal],
  );

  const handleExport = useCallback(() => {
    if (!filtered.length) return;
    const headers = ['Company', 'Total', 'Donors', 'Recipients', 'Transactions'];
    const rows = filtered.map((c) => [
      c.company,
      c.total || 0,
      c.donor_count || 0,
      c.recipient_count || 0,
      c.donation_count || 0,
    ]);
    downloadCSV(rows, headers, 'huntington-companies.csv');
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
            Companies ({filtered.length})
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
          placeholder="Search companies..."
        />

        <div style={{ overflowX: 'auto' }}>
          <table className={tableStyles.table}>
            <thead>
              <tr>
                <th>#</th>
                <th>Company</th>
                <th className="text-right">Total</th>
                <th className="text-center">Donors</th>
                <th className="text-center">Recipients</th>
                <th className="text-center">Transactions</th>
              </tr>
            </thead>
            <tbody>
              {pageData.map((c, i) => {
                const idx = (page - 1) * pageSize + i + 1;
                return (
                  <tr
                    key={`${c.company}-${idx}`}
                    className={tableStyles.clickableRow}
                    onClick={() => handleRowClick(c.company)}
                    title="Click to see donations"
                  >
                    <td>{idx}</td>
                    <td>{c.company}</td>
                    <td className="text-right">{money(c.total)}</td>
                    <td className="text-center">{c.donor_count}</td>
                    <td className="text-center">{c.recipient_count}</td>
                    <td className="text-center">{c.donation_count}</td>
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
