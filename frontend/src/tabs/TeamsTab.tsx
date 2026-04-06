import { useMemo } from 'react';
import { useDashboardStore } from '../store/useDashboardStore';
import { shortTeam, moneyShort } from '../utils/format';
import { GOALS_2026_SUBTEAMS } from '../types/constants';
import { ParticipantTypesChart } from '../components/charts/ParticipantTypesChart';
import { RaisedByTeamChart } from '../components/charts/RaisedByTeamChart';
import tableStyles from '../styles/table.module.css';
import layoutStyles from '../styles/layout.module.css';
import chartStyles from '../styles/chart.module.css';
import type { TeamBreakdown, Team } from '../types';

interface ComputedRow {
  name: string;
  riders: number;
  ridersGoal: number;
  challengers: number;
  challengersGoal: number;
  volunteers: number;
  volunteersGoal: number;
  raised: number;
  committed: number;
  fundGoal: number;
  fundPct: number;
}

export function TeamsTab() {
  const bundle = useDashboardStore((s) => s.bundle);

  const { rows, totals } = useMemo(() => {
    if (!bundle) return { rows: [], totals: null };

    const { teamBreakdown, teams } = bundle;

    // Build a team raised lookup
    const teamRaisedMap: Record<string, number> = {};
    teams.forEach((t: Team) => {
      teamRaisedMap[t.name] = t.raised;
    });

    const sorted = [...teamBreakdown].sort(
      (a: TeamBreakdown, b: TeamBreakdown) => (b.total || 0) - (a.total || 0),
    );

    let totR = 0,
      totRG = 0,
      totC = 0,
      totCG = 0,
      totV = 0,
      totVG = 0,
      totFunds = 0,
      totCommit = 0,
      totFG = 0;

    const computed: ComputedRow[] = sorted.map((t) => {
      const sn = shortTeam(t.name);
      const goals = GOALS_2026_SUBTEAMS[sn] || { riders: 0, challengers: 0, funds: 0 };
      const r = t.riders || 0;
      const c = t.challengers || 0;
      const v = t.volunteers || 0;
      const rg = goals.riders || 0;
      const cg = goals.challengers || 0;
      const vg = 0; // Volunteer goals not in GOALS_2026_SUBTEAMS
      const funds = t.total_raised || 0;
      const committed = t.total_committed || 0;
      const fg = goals.funds || 0;
      const fundPct = fg > 0 ? Math.round((funds / fg) * 100) : 0;

      totR += r;
      totRG += rg;
      totC += c;
      totCG += cg;
      totV += v;
      totVG += vg;
      totFunds += funds;
      totCommit += committed;
      totFG += fg;

      return { name: t.name, riders: r, ridersGoal: rg, challengers: c, challengersGoal: cg, volunteers: v, volunteersGoal: vg, raised: funds, committed, fundGoal: fg, fundPct };
    });

    const allFundPct = totFG > 0 ? Math.round((totFunds / totFG) * 100) : 0;

    return {
      rows: computed,
      totals: {
        riders: totR,
        ridersGoal: totRG,
        challengers: totC,
        challengersGoal: totCG,
        volunteers: totV,
        volunteersGoal: totVG,
        raised: totFunds,
        committed: totCommit,
        fundGoal: totFG,
        fundPct: allFundPct,
      },
    };
  }, [bundle]);

  if (!bundle) return null;

  return (
    <div>
      <div className={layoutStyles.grid} style={{ gridTemplateColumns: '1fr' }}>
        <div className={layoutStyles.card}>
          <h2 className={layoutStyles.cardTitle}>2026 Goals &amp; Progress by Sub-Team</h2>
          <div style={{ overflowX: 'auto' }}>
            <table className={tableStyles.table}>
              <thead>
                <tr>
                  <th>Sub-Team</th>
                  <th className="text-center">Riders</th>
                  <th className="text-center">Goal</th>
                  <th className="text-center">Challengers</th>
                  <th className="text-center">Goal</th>
                  <th className="text-center">Volunteers</th>
                  <th className="text-center">Goal</th>
                  <th className="text-right">Raised</th>
                  <th className="text-right">Committed</th>
                  <th className="text-right">Fund Goal</th>
                  <th className="text-center">%</th>
                </tr>
              </thead>
              <tbody>
                {rows.map((row) => (
                  <tr key={row.name}>
                    <td>{shortTeam(row.name)}</td>
                    <GoalCell current={row.riders} goal={row.ridersGoal} />
                    <GoalCell current={row.challengers} goal={row.challengersGoal} />
                    <GoalCell current={row.volunteers} goal={row.volunteersGoal} />
                    <td className="text-right">{moneyShort(row.raised)}</td>
                    <td className="text-right">{moneyShort(row.committed)}</td>
                    <td className="text-right">{moneyShort(row.fundGoal)}</td>
                    <td className="text-center">{row.fundPct}%</td>
                  </tr>
                ))}
              </tbody>
              {totals && (
                <tfoot>
                  <tr className={tableStyles.totalsRow}>
                    <td>TOTAL</td>
                    <td className="text-center">{totals.riders}</td>
                    <td className="text-center">{totals.ridersGoal}</td>
                    <td className="text-center">{totals.challengers}</td>
                    <td className="text-center">{totals.challengersGoal}</td>
                    <td className="text-center">{totals.volunteers}</td>
                    <td className="text-center">{totals.volunteersGoal}</td>
                    <td className="text-right">{moneyShort(totals.raised)}</td>
                    <td className="text-right">{moneyShort(totals.committed)}</td>
                    <td className="text-right">{moneyShort(totals.fundGoal)}</td>
                    <td className="text-center">{totals.fundPct}%</td>
                  </tr>
                </tfoot>
              )}
            </table>
          </div>
        </div>
      </div>

      {/* Charts */}
      <div className={layoutStyles.grid2}>
        <div className={layoutStyles.card}>
          <h2 className={layoutStyles.cardTitle}>Participant Types by Sub-Team</h2>
          <div className={chartStyles.chartContainerTall}>
            <ParticipantTypesChart />
          </div>
        </div>
        <div className={layoutStyles.card}>
          <h2 className={layoutStyles.cardTitle}>Raised by Sub-Team</h2>
          <div className={chartStyles.chartContainerTall}>
            <RaisedByTeamChart />
          </div>
        </div>
      </div>
    </div>
  );
}

function MiniBar({ current, goal }: { current: number; goal: number }) {
  if (!goal || goal <= 0) return null;
  const pctVal = Math.min(Math.round((current / goal) * 100), 100);
  return (
    <span className={tableStyles.miniBar}>
      <span className={tableStyles.miniBarFill} style={{ width: `${pctVal}%` }} />
    </span>
  );
}

function GoalCell({ current, goal }: { current: number; goal: number }) {
  const pctVal = goal > 0 ? Math.round((current / goal) * 100) : 0;
  const cls = pctVal >= 100 ? tableStyles.goalOver : tableStyles.goalUnder;
  return (
    <>
      <td className={`text-center ${tableStyles.goalCell}`}>
        <span className={cls}>{current}</span>
        {goal > 0 && <MiniBar current={current} goal={goal} />}
      </td>
      <td className={`text-center ${tableStyles.goalCell}`}>{goal}</td>
    </>
  );
}
