import styles from '../../styles/layout.module.css';
import { FUNDRAISING_CLOSE, DATA_FINAL } from '../../types/constants';

const DAY_MS = 86400000;

function longDate(d: Date): string {
  return d.toLocaleDateString('en-US', { month: 'long', day: 'numeric', year: 'numeric' });
}

export function ClosedBanner() {
  const now = new Date();
  // Fundraising runs through the end of the close day.
  if (now.getTime() < FUNDRAISING_CLOSE.getTime() + DAY_MS) return null;

  const dataFinal = now.getTime() >= DATA_FINAL.getTime() + DAY_MS;

  return (
    <div className={styles.closedBanner} role="status">
      <strong>Fundraising for Pelotonia 2026 closed on {longDate(FUNDRAISING_CLOSE)}.</strong>{' '}
      {dataFinal
        ? `Totals are final as of ${longDate(DATA_FINAL)}.`
        : `Late gifts are still posting. Data updates once a day through ${longDate(DATA_FINAL)}.`}
    </div>
  );
}
