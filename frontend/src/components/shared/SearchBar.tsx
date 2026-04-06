import { useCallback } from 'react';

interface SearchBarProps {
  value: string;
  onChange: (value: string) => void;
  placeholder?: string;
}

export function SearchBar({ value, onChange, placeholder = 'Search...' }: SearchBarProps) {
  const handleClear = useCallback(() => onChange(''), [onChange]);

  return (
    <div style={{ display: 'flex', gap: '8px', marginBottom: '12px' }}>
      <input
        className="search-bar"
        value={value}
        onChange={(e) => onChange(e.target.value)}
        placeholder={placeholder}
        style={{ marginBottom: 0, flex: 1 }}
      />
      {value && (
        <button
          onClick={handleClear}
          style={{
            padding: '6px 14px',
            border: '1px solid #ddd',
            borderRadius: '6px',
            background: '#fff',
            cursor: 'pointer',
            fontSize: '13px',
            color: '#666',
            whiteSpace: 'nowrap',
          }}
          title="Clear filter"
        >
          &times; Clear
        </button>
      )}
    </div>
  );
}
