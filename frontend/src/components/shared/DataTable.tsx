import { useCallback, type ReactNode } from 'react';
import styles from '../../styles/table.module.css';

export interface Column<T> {
  key: string;
  label: string;
  align?: 'left' | 'center' | 'right';
  render?: (row: T, index: number) => ReactNode;
}

interface DataTableProps<T> {
  columns: Column<T>[];
  data: T[];
  onRowClick?: (row: T) => void;
  sortKey?: string;
  sortDir?: 'asc' | 'desc';
  onSort?: (key: string) => void;
  rowKey: (row: T) => string;
  highlightRowKey?: string | null;
}

export function DataTable<T>({
  columns,
  data,
  onRowClick,
  sortKey,
  sortDir,
  onSort,
  rowKey,
  highlightRowKey,
}: DataTableProps<T>) {
  const handleHeaderClick = useCallback(
    (key: string) => {
      if (onSort) onSort(key);
    },
    [onSort],
  );

  const sortIndicator = (key: string) => {
    if (sortKey !== key) return '';
    return sortDir === 'asc' ? ' \u25B2' : ' \u25BC';
  };

  return (
    <table className={styles.table}>
      <thead>
        <tr>
          {columns.map((col) => (
            <th
              key={col.key}
              className={onSort ? styles.sortable : undefined}
              style={{ textAlign: col.align ?? 'left' }}
              onClick={() => handleHeaderClick(col.key)}
            >
              {col.label}
              {sortIndicator(col.key)}
            </th>
          ))}
        </tr>
      </thead>
      <tbody>
        {data.map((row, idx) => {
          const key = rowKey(row);
          const isHighlighted = highlightRowKey != null && key === highlightRowKey;
          return (
            <tr
              key={key}
              className={`${onRowClick ? styles.clickableRow : ''} ${isHighlighted ? styles.highlightRow : ''}`}
              onClick={onRowClick ? () => onRowClick(row) : undefined}
              data-public-id={key}
            >
              {columns.map((col) => (
                <td key={col.key} style={{ textAlign: col.align ?? 'left' }}>
                  {col.render
                    ? col.render(row, idx)
                    : String((row as Record<string, unknown>)[col.key] ?? '')}
                </td>
              ))}
            </tr>
          );
        })}
      </tbody>
    </table>
  );
}
