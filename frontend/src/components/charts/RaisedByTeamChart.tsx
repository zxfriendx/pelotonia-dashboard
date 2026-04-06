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
import { shortTeam, money } from '../../utils/format';
import { BRAND } from '../../types/constants';
import styles from '../../styles/chart.module.css';

ChartJS.register(CategoryScale, LinearScale, BarElement, Tooltip, Legend, ChartDataLabels);

export function RaisedByTeamChart() {
  const bundle = useDashboardStore((s) => s.bundle);
  const teams = bundle?.teams ?? [];

  const sorted = useMemo(
    () => [...teams].sort((a, b) => (b.raised || 0) - (a.raised || 0)),
    [teams],
  );

  const data = useMemo(() => ({
    labels: sorted.map((t) => shortTeam(t.name)),
    datasets: [
      {
        label: '2026 Raised',
        data: sorted.map((t) => t.raised || 0),
        backgroundColor: BRAND.green,
      },
    ],
  }), [sorted]);

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
            `${ctx.dataset.label}: ${money(ctx.raw as number)}`,
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

  if (!sorted.length) {
    return <div style={{ textAlign: 'center', padding: 40, color: '#888' }}>No team data</div>;
  }

  return (
    <div className={styles.chartContainerTall}>
      <Bar data={data} options={options} />
    </div>
  );
}
