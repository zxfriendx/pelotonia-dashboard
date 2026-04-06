import { useState, useCallback } from 'react';
import styles from '../../styles/kpi.module.css';
import { useDashboardStore } from '../../store/useDashboardStore';
import { money, pct } from '../../utils/format';

interface FlipCardProps {
  frontValue: string;
  frontLabel: string;
  backValue: string;
  backLabel: string;
  shareText?: string;
}

function FlipCard({ frontValue, frontLabel, backValue, backLabel, shareText }: FlipCardProps) {
  const [flipped, setFlipped] = useState(false);

  const toggle = useCallback(() => setFlipped((f) => !f), []);

  return (
    <div
      className={`${styles.kpiFlip} ${flipped ? styles.flipped : ''}`}
      onClick={toggle}
    >
      <span className={styles.kpiFlipHint}>&#x21c4;</span>
      <div className={styles.kpiInner}>
        <div className={styles.kpiFront}>
          <div className={styles.value}>{frontValue}</div>
          <div className={styles.label}>{frontLabel}</div>
        </div>
        <div className={styles.kpiBack}>
          <div className={styles.value}>{backValue}</div>
          <div className={styles.label}>{backLabel}</div>
          {shareText && <div className={styles.kpiShare}>{shareText}</div>}
        </div>
      </div>
    </div>
  );
}

interface SimpleKpiProps {
  value: string;
  label: string;
}

function SimpleKpi({ value, label }: SimpleKpiProps) {
  return (
    <div className={styles.kpi}>
      <div className={styles.value}>{value}</div>
      <div className={styles.label}>{label}</div>
    </div>
  );
}

export function KpiStrip() {
  const bundle = useDashboardStore((s) => s.bundle);

  if (!bundle) return null;

  const { overview, ticker } = bundle;
  const raised = overview.raised;
  const goal = overview.goal;
  const allTime = overview.all_time_raised;

  const pelRaised = ticker?.pelotonia_total_raised ?? 0;
  const pelMembers = ticker?.pelotonia_member_count ?? 0;
  const pelAllTime = ticker?.pelotonia_all_time_raised ?? 0;
  const tickerAvailable = pelRaised > 0;

  const raisedSharePct = pelRaised > 0 ? pct(raised, pelRaised) : 0;
  const membersSharePct = pelMembers > 0 ? pct(overview.members_count, pelMembers) : 0;

  return (
    <div className={styles.kpiStrip}>
      <FlipCard
        frontValue={money(raised)}
        frontLabel={`Raised (2026)${goal ? ` of ${money(goal)}` : ''}`}
        backValue={tickerAvailable ? money(pelRaised) : 'N/A'}
        backLabel="All Pelotonia"
        shareText={tickerAvailable ? `${raisedSharePct}% of total` : undefined}
      />
      <FlipCard
        frontValue={money(allTime)}
        frontLabel="All-Time Raised"
        backValue={pelAllTime > 0 ? money(pelAllTime) : 'N/A'}
        backLabel="All Pelotonia"
      />
      <FlipCard
        frontValue={overview.members_count.toLocaleString()}
        frontLabel="Members"
        backValue={tickerAvailable ? pelMembers.toLocaleString() : 'N/A'}
        backLabel="All Pelotonia"
        shareText={tickerAvailable ? `${membersSharePct}% of total` : undefined}
      />
      <SimpleKpi value={overview.first_year.toLocaleString()} label="First Year Riders" />
      <SimpleKpi value={overview.signature_riders.toLocaleString()} label="Signature Riders" />
      <SimpleKpi value={overview.gravel_riders.toLocaleString()} label="Gravel Riders" />
      <SimpleKpi value={overview.cancer_survivors.toLocaleString()} label="Cancer Survivors" />
      <SimpleKpi value={overview.high_rollers.toLocaleString()} label="High Rollers" />
    </div>
  );
}
