interface TabLoadingProps {
  /** Human label for the dataset, e.g. "donations". */
  label: string;
  /** If the background fetch failed, the error message. */
  error?: string | null;
}

/**
 * Placeholder shown by heavy tabs while the second-wave (/api/bundle/rest)
 * payload is still loading, so they don't briefly read as "no data".
 */
export function TabLoading({ label, error }: TabLoadingProps) {
  return (
    <div
      style={{
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'center',
        padding: '60px 20px',
        color: error ? '#c00' : '#888',
      }}
    >
      {error ? `Failed to load ${label}: ${error}` : `Loading ${label}…`}
    </div>
  );
}
