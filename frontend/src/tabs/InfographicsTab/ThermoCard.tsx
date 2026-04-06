import { useEffect, useRef } from 'react';
import styles from '../../styles/infographic.module.css';

interface Chip {
  v: string;
  l: string;
}

interface ThermoCardProps {
  label: string;
  current: number;
  goal: number;
  format: (v: number) => string;
  chips: Chip[];
  daysLeft: number;
  expected: number;
  deadline?: string;
}

export function ThermoCard({
  label,
  current,
  goal,
  format,
  chips,
  daysLeft,
  expected,
  deadline,
}: ThermoCardProps) {
  const fillRef = useRef<HTMLDivElement>(null);
  const pctValue = goal > 0 ? (current / goal) * 100 : 0;
  const fillPct = Math.min(pctValue, 100);
  const ahead = pctValue > expected;

  useEffect(() => {
    const el = fillRef.current;
    if (!el) return;
    // Start at 0 width, then animate to target
    el.style.width = '0%';
    requestAnimationFrame(() => {
      setTimeout(() => {
        el.style.width = `${fillPct}%`;
      }, 50);
    });
  }, [fillPct]);

  return (
    <div className={styles.thermoCard}>
      <div className={styles.thermoCardHeader}>
        <div className={styles.thermoLabel}>{label}</div>
        <div className={styles.pctBadge}>{pctValue.toFixed(1)}%</div>
      </div>
      <div className={styles.thermoValue}>{format(current)}</div>
      <div className={styles.thermoGoal}>
        of <strong>{goal > 0 ? format(goal) : '—'}</strong> goal
      </div>
      <div className={styles.thermoBarWrap}>
        <div className={styles.thermoBarBg}>
          <div ref={fillRef} className={styles.thermoBarFill} style={{ width: 0 }} />
        </div>
        <div className={styles.thermoMilestones}>
          <div className={styles.thermoMilestone} style={{ left: '25%' }}>25%</div>
          <div className={styles.thermoMilestone} style={{ left: '50%' }}>50%</div>
          <div className={styles.thermoMilestone} style={{ left: '75%' }}>75%</div>
        </div>
      </div>
      <div className={styles.statChips}>
        {chips.map((c, i) => (
          <div key={i} className={styles.statChip}>
            <div className={styles.statChipVal}>{c.v}</div>
            <div className={styles.statChipLabel}>{c.l}</div>
          </div>
        ))}
      </div>
      <div className={styles.paceRow}>
        <span className={ahead ? styles.paceAhead : styles.paceBehind} />
        <span>{ahead ? 'Ahead of pace' : 'Building momentum'}</span>
        <span style={{ color: '#bbb' }}>{daysLeft}d left</span>
      </div>
      {deadline && (
        <div style={{ marginTop: 8, fontSize: 11, color: '#aaa', fontStyle: 'italic' }}>
          {deadline}
        </div>
      )}
    </div>
  );
}
