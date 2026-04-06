import { useState, useMemo } from 'react';

interface PaginationResult<T> {
  page: number;
  totalPages: number;
  pageData: T[];
  setPage: (p: number) => void;
  setPageSize: (s: number) => void;
  pageSize: number;
}

export function usePagination<T>(data: T[], defaultPageSize = 25): PaginationResult<T> {
  const [page, setPage] = useState(1);
  const [pageSize, setPageSize] = useState(defaultPageSize);

  const totalPages = Math.max(1, Math.ceil(data.length / pageSize));
  const safePage = Math.min(page, totalPages);

  const pageData = useMemo(() => {
    const start = (safePage - 1) * pageSize;
    return data.slice(start, start + pageSize);
  }, [data, safePage, pageSize]);

  return {
    page: safePage,
    totalPages,
    pageData,
    setPage: (p: number) => setPage(Math.max(1, Math.min(p, totalPages))),
    setPageSize: (s: number) => { setPageSize(s); setPage(1); },
    pageSize,
  };
}
