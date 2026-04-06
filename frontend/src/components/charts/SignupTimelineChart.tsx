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
import { BRAND } from '../../types/constants';
import styles from '../../styles/chart.module.css';

ChartJS.register(CategoryScale, LinearScale, PointElement, LineElement, Tooltip, Legend, Filler);

export function SignupTimelineChart() {
  const bundle = useDashboardStore((s) => s.bundle);
  const timeline = bundle?.signupTimeline ?? [];

  const data = useMemo(() => ({
    labels: timeline.map((e) => e.snapshot_date),
    datasets: [
      {
        label: 'Total Members',
        data: timeline.map((e) => e.members_count),
        borderColor: BRAND.tread,
        backgroundColor: 'rgba(41, 50, 45, 0.1)',
        fill: true,
        tension: 0.3,
        pointRadius: 3,
      },
      {
        label: 'Riders',
        data: timeline.map((e) => e.riders_count),
        borderColor: BRAND.green,
        backgroundColor: 'rgba(68, 214, 44, 0.1)',
        fill: true,
        tension: 0.3,
        pointRadius: 3,
      },
      {
        label: 'Challengers',
        data: timeline.map((e) => e.challengers_count),
        borderColor: BRAND.black,
        backgroundColor: 'rgba(14, 20, 17, 0.1)',
        fill: true,
        tension: 0.3,
        pointRadius: 3,
      },
      {
        label: 'Volunteers',
        data: timeline.map((e) => e.volunteers_count),
        borderColor: '#888',
        backgroundColor: 'rgba(136, 136, 136, 0.1)',
        fill: true,
        tension: 0.3,
        pointRadius: 3,
      },
    ],
  }), [timeline]);

  const options = useMemo(() => ({
    responsive: true,
    maintainAspectRatio: false,
    interaction: { mode: 'index' as const, intersect: false },
    scales: {
      y: {
        title: { display: true, text: 'Participants' },
        beginAtZero: true,
      },
      x: {
        ticks: { maxRotation: 45, autoSkip: true, maxTicksLimit: 15 },
      },
    },
    plugins: {
      datalabels: { display: false },
    },
  }), []);

  if (!timeline.length) {
    const overview = bundle?.overview;
    return (
      <div style={{ textAlign: 'center', padding: 40, color: '#888' }}>
        Signup tracking starts after the next daily scrape.
        {overview && (
          <>
            <br />
            Current: {overview.signature_riders} Signature, {overview.gravel_riders} Gravel
          </>
        )}
      </div>
    );
  }

  return (
    <div className={styles.chartContainer}>
      <Line data={data} options={options} />
    </div>
  );
}
