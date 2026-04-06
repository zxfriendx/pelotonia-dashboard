import { moneyShort } from '../../utils/format';
import { REGISTRATION_OPEN, RIDE_WEEKEND, FUNDRAISING_CLOSE } from '../../types/constants';
import styles from '../../styles/infographic.module.css';

interface SummaryCardsProps {
  survivors: number;
  highRollers: number;
  avgDonation: number;
}

export function SummaryCards({ survivors, highRollers, avgDonation }: SummaryCardsProps) {
  const now = new Date();
  const regDay = Math.max(1, Math.ceil((now.getTime() - REGISTRATION_OPEN.getTime()) / 86400000) + 1);
  const daysToRide = Math.max(0, Math.ceil((RIDE_WEEKEND.getTime() - now.getTime()) / 86400000));
  const daysToClose = Math.max(0, Math.ceil((FUNDRAISING_CLOSE.getTime() - now.getTime()) / 86400000));

  const cards = [
    { value: String(survivors), label: 'Cancer Survivors' },
    { value: String(highRollers), label: 'High Rollers' },
    { value: daysToRide > 0 ? String(daysToRide) : 'Ride Day!', label: 'Days to Ride Weekend' },
    { value: String(daysToClose), label: 'Days to Fundraising Close' },
    { value: moneyShort(Math.round(avgDonation)), label: 'Avg Donation' },
    { value: `Day ${regDay}`, label: 'of Campaign' },
  ];

  return (
    <div className={styles.infographicSummary}>
      {cards.map((c, i) => (
        <div key={i} className={styles.summaryCard}>
          <div className={styles.summaryValue}>{c.value}</div>
          <div className={styles.summaryLabel}>{c.label}</div>
        </div>
      ))}
    </div>
  );
}
