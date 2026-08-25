import { useMemo } from 'react';
import { Chart } from 'react-chartjs-2';
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
import { money, moneyFull } from '../../utils/format';
import { BRAND } from '../../types/constants';
import styles from '../../styles/chart.module.css';

ChartJS.register(CategoryScale, LinearScale, PointElement, LineElement, Tooltip, Legend, Filler);

export function CommitmentGapChart() {
  const timeline = useDashboardStore((s) => s.bundle?.commitmentGap?.timeline ?? []);

  const data = useMemo(() => ({
    labels: timeline.map((t) => t.date),
    datasets: [
      {
        type: 'line' as const,
        label: 'Outstanding shortfall ($)',
        data: timeline.map((t) => t.shortfall),
        borderColor: '#c0392b',
        backgroundColor: 'rgba(192, 57, 43, 0.08)',
        fill: true,
        tension: 0.3,
        pointRadius: 0,
        yAxisID: 'y',
      },
      {
        type: 'line' as const,
        label: 'Members below commitment',
        data: timeline.map((t) => t.below_count),
        borderColor: BRAND.forest,
        backgroundColor: BRAND.forest,
        fill: false,
        tension: 0.3,
        pointRadius: 0,
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
        title: { display: true, text: 'Shortfall' },
        ticks: { callback: (v: string | number) => money(Number(v)) },
      },
      y1: {
        position: 'right' as const,
        grid: { drawOnChartArea: false },
        title: { display: true, text: 'Members below' },
      },
      x: {
        ticks: { maxRotation: 45, autoSkip: true, maxTicksLimit: 15 },
      },
    },
    plugins: {
      datalabels: { display: false },
      tooltip: {
        callbacks: {
          label: (ctx: { dataset: { label?: string; yAxisID?: string }; raw: unknown }) =>
            ctx.dataset.yAxisID === 'y'
              ? `${ctx.dataset.label}: ${moneyFull(ctx.raw as number)}`
              : `${ctx.dataset.label}: ${ctx.raw}`,
        },
      },
    },
  }), []);

  if (!timeline.length) {
    return <div style={{ textAlign: 'center', padding: 40, color: '#888' }}>No commitment timeline data yet</div>;
  }

  return (
    <div className={styles.chartContainer}>
      <Chart type="line" data={data} options={options} />
    </div>
  );
}
