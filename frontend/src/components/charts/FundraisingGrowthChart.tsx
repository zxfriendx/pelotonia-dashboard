import { useMemo } from 'react';
import { Chart } from 'react-chartjs-2';
import {
  Chart as ChartJS,
  CategoryScale,
  LinearScale,
  PointElement,
  LineElement,
  BarElement,
  Tooltip,
  Legend,
  Filler,
} from 'chart.js';
import { useDashboardStore } from '../../store/useDashboardStore';
import { money, moneyFull } from '../../utils/format';
import { BRAND } from '../../types/constants';
import styles from '../../styles/chart.module.css';

ChartJS.register(CategoryScale, LinearScale, PointElement, LineElement, BarElement, Tooltip, Legend, Filler);

export function FundraisingGrowthChart() {
  const bundle = useDashboardStore((s) => s.bundle);
  const timeline = bundle?.timeline ?? [];

  const data = useMemo(() => ({
    labels: timeline.map((t) => t.date),
    datasets: [
      {
        type: 'line' as const,
        label: 'Cumulative ($)',
        data: timeline.map((t) => t.cumulative),
        borderColor: BRAND.green,
        backgroundColor: 'rgba(68, 214, 44, 0.1)',
        fill: true,
        tension: 0.3,
        pointRadius: 3,
        yAxisID: 'y',
      },
      {
        type: 'bar' as const,
        label: 'Daily ($)',
        data: timeline.map((t) => t.daily_amount),
        borderColor: BRAND.forest,
        backgroundColor: BRAND.forest,
        yAxisID: 'y1',
      },
    ],
  }), [timeline]);

  const options = useMemo(() => ({
    responsive: true,
    maintainAspectRatio: false,
    interaction: { mode: 'index' as const, intersect: false },
    scales: {
      y: {
        position: 'left' as const,
        title: { display: true, text: 'Cumulative' },
        ticks: {
          callback: (v: string | number) => money(Number(v)),
        },
      },
      y1: {
        position: 'right' as const,
        grid: { drawOnChartArea: false },
        title: { display: true, text: 'Daily' },
        ticks: {
          callback: (v: string | number) => money(Number(v)),
        },
      },
      x: {
        ticks: { maxRotation: 45, autoSkip: true, maxTicksLimit: 15 },
      },
    },
    plugins: {
      datalabels: { display: false },
      tooltip: {
        callbacks: {
          label: (ctx: { dataset: { label?: string }; raw: unknown }) =>
            `${ctx.dataset.label}: ${moneyFull(ctx.raw as number)}`,
        },
      },
    },
  }), []);

  if (!timeline.length) {
    return <div style={{ textAlign: 'center', padding: 40, color: '#888' }}>No donation timeline data yet</div>;
  }

  return (
    <div className={styles.chartContainer}>
      <Chart type="bar" data={data} options={options} />
    </div>
  );
}
