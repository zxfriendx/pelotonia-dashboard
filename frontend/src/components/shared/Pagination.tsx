interface PaginationProps {
  page: number;
  totalPages: number;
  pageSize: number;
  setPage: (p: number) => void;
  setPageSize: (s: number) => void;
}

export function Pagination({ page, totalPages, pageSize, setPage, setPageSize }: PaginationProps) {
  return (
    <div className="pagination">
      <button disabled={page <= 1} onClick={() => setPage(page - 1)}>
        &laquo; Prev
      </button>
      <span className="page-info">
        Page {page} of {totalPages}
      </span>
      <div className="page-size-wrap">
        <select
          value={pageSize}
          onChange={(e) => setPageSize(Number(e.target.value))}
        >
          <option value={10}>10</option>
          <option value={25}>25</option>
          <option value={50}>50</option>
        </select>
      </div>
      <button disabled={page >= totalPages} onClick={() => setPage(page + 1)}>
        Next &raquo;
      </button>
    </div>
  );
}
