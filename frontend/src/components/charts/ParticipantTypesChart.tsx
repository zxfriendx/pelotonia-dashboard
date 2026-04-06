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
import { shortTeam } from '../../utils/format';
import { BRAND } from '../../types/constants';
import styles from '../../styles/chart.module.css';

ChartJS.register(CategoryScale, LinearScale, BarElement, Tooltip, Legend, ChartDataLabels);

export function ParticipantTypesChart() {
  const bundle = useDashboardStore((s) => s.bundle);
  const breakdown = bundle?.teamBreakdown ?? [];

  const sorted = useMemo(
    () => [...breakdown].sort((a, b) => (b.total || 0) - (a.total || 0)),
    [breakdown],
  );

  const data = useMemo(() => ({
    labels: sorted.map((t) => shortTeam(t.name)),
    datasets: [
      {
        label: 'Riders',
        data: sorted.map((t) => t.riders),
        backgroundColor: BRAND.green,
      },
      {
        label: 'Challengers',
        data: sorted.map((t) => t.challengers),
        backgroundColor: BRAND.black,
      },
      {
        label: 'Registered Only',
        data: sorted.map((t) => (t.total || 0) - (t.riders || 0) - (t.challengers || 0) - (t.volunteers || 0)),
        backgroundColor: '#bbb',
      },
    ],
  }), [sorted]);

  const options = useMemo(() => ({
    responsive: true,
    maintainAspectRatio: false,
    indexAxis: 'y' as const,
    scales: {
      x: { stacked: true },
      y: { stacked: true, ticks: { font: { size: 11 }, autoSkip: false } },
    },
    plugins: {
      datalabels: {
        display: ((ctx: { chart: { ctx: CanvasRenderingContext2D; scales: Record<string, { getPixelForValue: (v: number) => number }>; data: { datasets: { data: unknown[] }[] } }; dataset: { data: unknown[] }; dataIndex: number }) => {
          const val = Number(ctx.dataset.data[ctx.dataIndex]) || 0;
          if (val < 1) return false;
          // Use the x-scale to get actual pixel width of this segment
          const xScale = ctx.chart.scales.x;
          if (!xScale) return false;
          const segmentPx = Math.abs(xScale.getPixelForValue(val) - xScale.getPixelForValue(0));
          const canvas = ctx.chart.ctx;
          canvas.font = 'bold 11px sans-serif';
          const textPx = canvas.measureText(String(val)).width;
          return textPx + 10 <= segmentPx;
        }) as (context: unknown) => boolean,
        color: ((ctx: { datasetIndex: number }) =>
          ctx.datasetIndex === 1 ? '#fff' : '#000') as (context: unknown) => string,
        font: { weight: 'bold' as const, size: 11 },
        anchor: 'center' as const,
        align: 'center' as const,
      },
    },
  }), []);

  if (!sorted.length) {
    return <div style={{ textAlign: 'center', padding: 40, color: '#888' }}>No team breakdown data</div>;
  }

  return (
    <div className={styles.chartContainerTall}>
      <Bar data={data} options={options} />
    </div>
  );
}
