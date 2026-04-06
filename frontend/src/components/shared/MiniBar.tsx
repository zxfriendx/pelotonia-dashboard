import styles from '../../styles/table.module.css';

interface MiniBarProps {
  value: number;
  max: number;
  color?: string;
}

export function MiniBar({ value, max, color }: MiniBarProps) {
  const pct = max > 0 ? Math.min((value / max) * 100, 100) : 0;

  return (
    <span className={styles.miniBar}>
      <span
        className={styles.miniBarFill}
        style={{
          width: `${pct}%`,
          ...(color ? { background: color } : {}),
        }}
      />
    </span>
  );
}
