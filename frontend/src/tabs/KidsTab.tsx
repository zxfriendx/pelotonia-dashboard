import { useDashboardStore } from '../store/useDashboardStore';
import { money, pct } from '../utils/format';
import { KidsRaisedChart } from '../components/charts/KidsRaisedChart';
import { KidsSignupsChart } from '../components/charts/KidsSignupsChart';
import kpiStyles from '../styles/kpi.module.css';
import layoutStyles from '../styles/layout.module.css';

export function KidsTab() {
  const kidsOverview = useDashboardStore((s) => s.bundle?.kidsOverview ?? null);
  const kidsSnapshots = useDashboardStore((s) => s.bundle?.kidsSnapshots ?? []);

  if (!kidsOverview) {
    return (
      <div style={{ textAlign: 'center', padding: 40, color: '#888' }}>
        No Pelotonia Kids data available
      </div>
    );
  }

  const progressPct = pct(kidsOverview.estimated_amount_raised, kidsOverview.monetary_goal);

  return (
    <div>
      {/* KPI Cards */}
      <div className={kpiStyles.kpiStrip}>
        <div className={kpiStyles.kpi}>
          <div className={kpiStyles.value}>{kidsOverview.fundraiser_count.toLocaleString()}</div>
          <div className={kpiStyles.label}>Fundraisers</div>
        </div>
        <div className={kpiStyles.kpi}>
          <div className={kpiStyles.value}>{money(kidsOverview.estimated_amount_raised)}</div>
          <div className={kpiStyles.label}>Raised</div>
        </div>
        <div className={kpiStyles.kpi}>
          <div className={kpiStyles.value}>{money(kidsOverview.monetary_goal)}</div>
          <div className={kpiStyles.label}>Goal</div>
        </div>
        <div className={kpiStyles.kpi}>
          <div className={kpiStyles.value}>{progressPct}%</div>
          <div className={kpiStyles.label}>Progress</div>
        </div>
        <div className={kpiStyles.kpi}>
          <div className={kpiStyles.value}>{kidsOverview.team_count.toLocaleString()}</div>
          <div className={kpiStyles.label}>Teams</div>
        </div>
      </div>

      {/* Charts */}
      {kidsSnapshots.length > 0 && (
        <div className={layoutStyles.grid2}>
          <div className={layoutStyles.card}>
            <div className={layoutStyles.cardTitle}>Raised Over Time</div>
            <KidsRaisedChart />
          </div>
          <div className={layoutStyles.card}>
            <div className={layoutStyles.cardTitle}>Fundraisers Over Time</div>
            <KidsSignupsChart />
          </div>
        </div>
      )}
    </div>
  );
}
