import { useMemo } from 'react';
import { Bar } from 'react-chartjs-2';
import {
  Chart as ChartJS,
  CategoryScale,
  LinearScale,
  BarElement,
  Tooltip,
  Legend,
} from 'chart.js';
import ChartDataLabels from 'chartjs-plugin-datalabels';
import { useDashboardStore } from '../../store/useDashboardStore';
import { money } from '../../utils/format';
import { BRAND } from '../../types/constants';
import styles from '../../styles/chart.module.css';

ChartJS.register(CategoryScale, LinearScale, BarElement, Tooltip, Legend, ChartDataLabels);

export function RouteFundraisingChart() {
  const bundle = useDashboardStore((s) => s.bundle);
  const routes = bundle?.routes ?? [];

  const sorted = useMemo(
    () => [...routes].filter((r) => (r.route_raised || 0) > 0 || (r.route_committed || 0) > 0)
      .sort((a, b) => (b.route_raised || 0) - (a.route_raised || 0)),
    [routes],
  );

  const data = useMemo(() => ({
    labels: sorted.map((r) => r.name),
    datasets: [
      {
        label: 'Raised',
        data: sorted.map((r) => r.route_raised || 0),
        backgroundColor: BRAND.green,
      },
      {
        label: 'Committed',
        data: sorted.map((r) => r.route_committed || 0),
        backgroundColor: BRAND.forest,
      },
    ],
  }), [sorted]);

  const options = useMemo(() => ({
    responsive: true,
    maintainAspectRatio: false,
    scales: {
      y: { ticks: { callback: (v: string | number) => money(Number(v)), font: { size: 11 } } },
      x: { ticks: { font: { size: 11 }, autoSkip: false, maxRotation: 45, minRotation: 30 } },
    },
    plugins: {
      legend: { position: 'top' as const },
      tooltip: {
        callbacks: {
          label: (ctx: { dataset: { label?: string }; raw: unknown }) =>
            `${ctx.dataset.label}: ${money(ctx.raw as number)}`,
        },
      },
      datalabels: { display: false },
    },
  }), []);

  if (!sorted.length) {
    return <div style={{ textAlign: 'center', padding: 40, color: '#888' }}>No route fundraising data</div>;
  }

  return (
    <div className={styles.chartContainerTall}>
      <Bar data={data} options={options} />
    </div>
  );
}
