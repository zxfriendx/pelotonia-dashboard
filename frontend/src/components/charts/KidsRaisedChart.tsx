import { useMemo } from 'react';
import { Line } from 'react-chartjs-2';
import {
  Chart as ChartJS,
  CategoryScale,
  LinearScale,
  PointElement,
  LineElement,
  Tooltip,
  Legend,
  Filler,
} from 'chart.js';
import { useDashboardStore } from '../../store/useDashboardStore';
import { money } from '../../utils/format';
import { BRAND } from '../../types/constants';
import styles from '../../styles/chart.module.css';

ChartJS.register(CategoryScale, LinearScale, PointElement, LineElement, Tooltip, Legend, Filler);

export function KidsRaisedChart() {
  const bundle = useDashboardStore((s) => s.bundle);
  const snapshots = bundle?.kidsSnapshots ?? [];

  const data = useMemo(() => ({
    labels: snapshots.map((s) => s.snapshot_date),
    datasets: [
      {
        label: 'Raised',
        data: snapshots.map((s) => s.estimated_amount_raised),
        borderColor: BRAND.green,
        backgroundColor: 'rgba(68, 214, 44, 0.1)',
        fill: true,
        tension: 0.3,
        pointRadius: snapshots.length > 30 ? 0 : 3,
        pointHoverRadius: 4,
      },
    ],
  }), [snapshots]);

  const options = useMemo(() => ({
    responsive: true,
    maintainAspectRatio: false,
    plugins: {
      datalabels: { display: false },
      legend: { display: false },
      tooltip: {
        callbacks: {
          label: (ctx: { raw: unknown }) => money(ctx.raw as number),
        },
      },
    },
    scales: {
      x: { ticks: { maxTicksLimit: 10, font: { size: 11 } } },
      y: { ticks: { callback: (v: string | number) => money(Number(v)), font: { size: 11 } } },
    },
  }), []);

  if (!snapshots.length) {
    return <div style={{ textAlign: 'center', padding: 40, color: '#888' }}>No kids snapshot data</div>;
  }

  return (
    <div className={styles.chartContainer}>
      <Line data={data} options={options} />
    </div>
  );
}
