import { useMemo, useCallback } from 'react';
import { useDashboardStore } from '../store/useDashboardStore';
import { money } from '../utils/format';
import { RouteFundraisingChart } from '../components/charts/RouteFundraisingChart';
import type { Route } from '../types';
import tableStyles from '../styles/table.module.css';
import layoutStyles from '../styles/layout.module.css';
import chartStyles from '../styles/chart.module.css';

export function RoutesTab() {
  const bundle = useDashboardStore((s) => s.bundle);
  const openModal = useDashboardStore((s) => s.openModal);

  const { sigRoutes, grvRoutes } = useMemo(() => {
    if (!bundle) return { sigRoutes: [], grvRoutes: [] };
    return {
      sigRoutes: bundle.routes.filter((r) => r.ride_type === 'signature'),
      grvRoutes: bundle.routes.filter((r) => r.ride_type === 'gravel'),
    };
  }, [bundle]);

  const handleRouteClick = useCallback(
    (route: Route) => {
      openModal({
        type: 'routeMembers',
        data: { routeId: route.id, routeName: route.name },
      });
    },
    [openModal],
  );

  if (!bundle) return null;

  const sigTotal = sigRoutes.length > 0 ? sigRoutes[0].ride_total_signups : 0;
  const grvTotal = grvRoutes.length > 0 ? grvRoutes[0].ride_total_signups : 0;

  return (
    <div>
      {/* Summary cards */}
      <div className={layoutStyles.grid2}>
        <div className={layoutStyles.card}>
          <h2 className={layoutStyles.cardTitle}>Signature Ride Signups</h2>
          <div style={{ fontSize: '48px', fontWeight: 800, color: 'var(--forest)' }}>
            {sigTotal || '\u2014'}
          </div>
          <div style={{ fontSize: '12px', color: '#666', textTransform: 'uppercase' }}>
            Team Members Registered
          </div>
          <div style={{ fontSize: '13px', color: '#888', marginTop: '4px' }}>
            Ride Weekend: August 1-2, 2026
          </div>
        </div>
        <div className={layoutStyles.card}>
          <h2 className={layoutStyles.cardTitle}>Gravel Day Signups</h2>
          <div style={{ fontSize: '48px', fontWeight: 800, color: 'var(--forest)' }}>
            {grvTotal || '\u2014'}
          </div>
          <div style={{ fontSize: '12px', color: '#666', textTransform: 'uppercase' }}>
            Team Members Registered
          </div>
          <div style={{ fontSize: '13px', color: '#888', marginTop: '4px' }}>
            Gravel Day: October 3, 2026
          </div>
        </div>
      </div>

      {/* Signature Route Table */}
      <div className={layoutStyles.grid} style={{ gridTemplateColumns: '1fr' }}>
        <div className={layoutStyles.card}>
          <h2 className={layoutStyles.cardTitle}>2026 Signature Ride Routes</h2>
          <div style={{ overflowX: 'auto' }}>
            <RouteTable routes={sigRoutes} onRouteClick={handleRouteClick} />
          </div>
        </div>
      </div>

      {/* Gravel Route Table */}
      <div className={layoutStyles.grid} style={{ gridTemplateColumns: '1fr' }}>
        <div className={layoutStyles.card}>
          <h2 className={layoutStyles.cardTitle}>2026 Gravel Day Routes</h2>
          <div style={{ overflowX: 'auto' }}>
            <RouteTable routes={grvRoutes} onRouteClick={handleRouteClick} />
          </div>
        </div>
      </div>

      {/* Route fundraising chart placeholder */}
      <div className={layoutStyles.grid} style={{ gridTemplateColumns: '1fr' }}>
        <div className={layoutStyles.card}>
          <h2 className={layoutStyles.cardTitle}>Route Fundraising: Raised vs Committed</h2>
          <div className={chartStyles.chartContainerTall}>
            <RouteFundraisingChart />
          </div>
        </div>
      </div>
    </div>
  );
}

function RouteTable({
  routes,
  onRouteClick,
}: {
  routes: Route[];
  onRouteClick: (r: Route) => void;
}) {
  const totals = useMemo(() => {
    let signups = 0,
      raised = 0,
      committed = 0;
    routes.forEach((r) => {
      signups += r.signups || 0;
      raised += r.route_raised || 0;
      committed += r.route_committed || 0;
    });
    return { signups, raised, committed };
  }, [routes]);

  return (
    <table className={tableStyles.table}>
      <thead>
        <tr>
          <th>Route</th>
          <th className="text-right">Distance</th>
          <th className="text-right">Commitment</th>
          <th className="text-center">Signups</th>
          <th className="text-right">Raised</th>
          <th className="text-right">Committed</th>
          <th>Start/End</th>
        </tr>
      </thead>
      <tbody>
        {routes.map((r) => {
          const loc = r.starting_city || '\u2014';
          const locStr =
            r.ending_city && r.ending_city !== r.starting_city
              ? `${loc} \u2192 ${r.ending_city}`
              : loc;
          return (
            <tr
              key={r.id}
              className={tableStyles.routeRow}
              onClick={() => onRouteClick(r)}
              title="Click to see members on this route"
            >
              <td>{r.name}</td>
              <td className="text-right">{r.distance} mi</td>
              <td className="text-right">{money(r.fundraising_commitment)}</td>
              <td className="text-center">{r.signups || '\u2014'}</td>
              <td className="text-right">
                {r.route_raised ? money(r.route_raised) : '\u2014'}
              </td>
              <td className="text-right">
                {r.route_committed ? money(r.route_committed) : '\u2014'}
              </td>
              <td>{locStr}</td>
            </tr>
          );
        })}
      </tbody>
      <tfoot>
        <tr className={tableStyles.totalsRow}>
          <td>Total</td>
          <td />
          <td />
          <td className="text-center">{totals.signups}</td>
          <td className="text-right">{money(totals.raised)}</td>
          <td className="text-right">{money(totals.committed)}</td>
          <td />
        </tr>
      </tfoot>
    </table>
  );
}
