import { useDashboardStore } from '../../store/useDashboardStore';
import { money, pct } from '../../utils/format';

export function ProgressBar() {
  const bundle = useDashboardStore((s) => s.bundle);

  if (!bundle) return null;

  const { raised, goal } = bundle.overview;
  const percentage = goal > 0 ? Math.min(pct(raised, goal), 100) : 0;

  return (
    <div className="progress-wrap">
      <div className="progress-outer">
        <div
          className="progress-inner"
          style={{ width: `${percentage}%` }}
        />
        <div className="progress-label">
          {money(raised)} / {money(goal)} ({pct(raised, goal)}%)
        </div>
      </div>
    </div>
  );
}
