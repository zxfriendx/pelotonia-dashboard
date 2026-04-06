import styles from '../../styles/layout.module.css';

interface KpiCardProps {
  label: string;
  value: string;
  subtitle?: string;
}

export function KpiCard({ label, value, subtitle }: KpiCardProps) {
  return (
    <div className={styles.card} style={{ textAlign: 'center', padding: '16px' }}>
      <div style={{ fontSize: '13px', color: '#888', marginBottom: '4px' }}>{label}</div>
      <div style={{ fontSize: '28px', fontWeight: 700 }}>{value}</div>
      {subtitle && (
        <div style={{ fontSize: '11px', color: '#aaa', marginTop: '4px' }}>{subtitle}</div>
      )}
    </div>
  );
}
