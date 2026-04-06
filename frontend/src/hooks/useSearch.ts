import { useState, useMemo } from 'react';

export function useSearch<T>(data: T[], searchFn: (item: T, query: string) => boolean) {
  const [query, setQuery] = useState('');

  const filtered = useMemo(() => {
    if (!query.trim()) return data;
    const q = query.trim().toLowerCase();
    return data.filter(item => searchFn(item, q));
  }, [data, query, searchFn]);

  return { query, setQuery, filtered };
}
