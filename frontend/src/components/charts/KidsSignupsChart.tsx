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
} from 'chart.js';
import { useDashboardStore } from '../../store/useDashboardStore';
import { BRAND } from '../../types/constants';
import styles from '../../styles/chart.module.css';

ChartJS.register(CategoryScale, LinearScale, PointElement, LineElement, Tooltip, Legend);

export function KidsSignupsChart() {
  const bundle = useDashboardStore((s) => s.bundle);
  const snapshots = bundle?.kidsSnapshots ?? [];

  const data = useMemo(() => ({
    labels: snapshots.map((s) => s.snapshot_date),
    datasets: [
      {
        label: 'Fundraisers',
        data: snapshots.map((s) => s.fundraiser_count),
        borderColor: BRAND.green,
        backgroundColor: BRAND.green,
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
          label: (ctx: { raw: unknown }) => `Fundraisers: ${(ctx.raw as number).toLocaleString()}`,
        },
      },
    },
    scales: {
      x: { ticks: { maxTicksLimit: 10, font: { size: 11 } } },
      y: { ticks: { font: { size: 11 } } },
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
