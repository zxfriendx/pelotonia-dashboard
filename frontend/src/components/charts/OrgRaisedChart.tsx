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
import { money, moneyFull } from '../../utils/format';
import { BRAND, PARENT_TEAM_ID } from '../../types/constants';
import styles from '../../styles/chart.module.css';

ChartJS.register(CategoryScale, LinearScale, BarElement, Tooltip, Legend, ChartDataLabels);

export function OrgRaisedChart() {
  const bundle = useDashboardStore((s) => s.bundle);
  const orgs = bundle?.orgLeaderboard ?? [];

  const top15 = useMemo(
    () => [...orgs].sort((a, b) => (b.raised || 0) - (a.raised || 0)).slice(0, 15),
    [orgs],
  );

  const barColors = useMemo(
    () => top15.map((o) => (o.team_id === PARENT_TEAM_ID ? BRAND.green : '#b0b0b0')),
    [top15],
  );

  const data = useMemo(() => ({
    labels: top15.map((o) => o.name || '?'),
    datasets: [
      {
        label: '2026 Raised',
        data: top15.map((o) => o.raised || 0),
        backgroundColor: barColors,
      },
    ],
  }), [top15, barColors]);

  const options = useMemo(() => ({
    responsive: true,
    maintainAspectRatio: false,
    indexAxis: 'y' as const,
    layout: { padding: { right: 60 } },
    scales: {
      x: { ticks: { callback: (v: string | number) => money(Number(v)), font: { size: 11 } } },
      y: { ticks: { font: { size: 11 }, autoSkip: false } },
    },
    plugins: {
      legend: { display: false },
      tooltip: {
        callbacks: {
          label: (ctx: { dataset: { label?: string }; raw: unknown }) =>
            `${ctx.dataset.label}: ${moneyFull(ctx.raw as number)}`,
        },
      },
      datalabels: {
        display: ((ctx: { dataset: { data: unknown[] }; dataIndex: number }) =>
          (Number(ctx.dataset.data[ctx.dataIndex]) || 0) >= 1000) as (context: unknown) => boolean,
        color: '#333',
        font: { weight: 'bold' as const, size: 11 },
        anchor: 'end' as const,
        align: 'right' as const,
        formatter: (v: number) => '$' + Math.round(v / 1000) + 'k',
      },
    },
  }), []);

  if (!top15.length) {
    return <div style={{ textAlign: 'center', padding: 40, color: '#888' }}>No organization data</div>;
  }

  return (
    <div className={styles.chartContainerTall}>
      <Bar data={data} options={options} />
    </div>
  );
}
