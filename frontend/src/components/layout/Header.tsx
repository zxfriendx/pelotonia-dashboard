import styles from '../../styles/layout.module.css';
import { useDashboardStore } from '../../store/useDashboardStore';

export function Header() {
  const bundle = useDashboardStore((s) => s.bundle);
  const lastScraped = bundle?.overview.last_scraped ?? '';

  return (
    <header className={styles.header}>
      <h1 className={styles.headerTitle}>Team Huntington Bank</h1>
      <span className={styles.headerBadge}>PELOTONIA 2026</span>
      <span className={styles.headerUpdated}>
        {lastScraped
          ? `Updated ${new Date(lastScraped).toLocaleString('en-US', { month: 'short', day: 'numeric', hour: 'numeric', minute: '2-digit', timeZoneName: 'short' })}`
          : ''}
      </span>
    </header>
  );
}
