import { useMemo } from 'react';
import { useDashboardStore } from '../../store/useDashboardStore';
import { shortTeam, moneyShort } from '../../utils/format';
import { computeSmartTargets } from '../../utils/targets';
import { MiniBar } from '../../components/shared/MiniBar';
import tableStyles from '../../styles/table.module.css';

export function GoalsTable() {
  const bundle = useDashboardStore((s) => s.bundle);

  const { rows, totals } = useMemo(() => {
    if (!bundle) return { rows: [], totals: null };

    const targets = computeSmartTargets(bundle);
    const sorted = [...bundle.teamBreakdown].sort((a, b) => (b.total || 0) - (a.total || 0));

    let totR = 0, totRG = 0, totC = 0, totCG = 0, totV = 0, totVG = 0;
    let totFunds = 0, totCommit = 0, totFG = 0;

    const rows = sorted.map((t) => {
      const tgt = targets[t.name] || { riders: 0, challengers: 0, volunteers: 0, funds: 0 };
      const r = t.riders || 0, c = t.challengers || 0, v = t.volunteers || 0;
      const rg = tgt.riders || 0, cg = tgt.challengers || 0, vg = tgt.volunteers || 0;
      const funds = t.total_raised || 0;
      const committed = t.total_committed || 0;
      const fg = tgt.funds || 0;
      const fundPct = fg > 0 ? Math.round((funds / fg) * 100) : 0;

      totR += r; totRG += rg; totC += c; totCG += cg; totV += v; totVG += vg;
      totFunds += funds; totCommit += committed; totFG += fg;

      return { name: t.name, r, rg, c, cg, v, vg, funds, committed, fg, fundPct };
    });

    const allFundPct = totFG > 0 ? Math.round((totFunds / totFG) * 100) : 0;

    return {
      rows,
      totals: { totR, totRG, totC, totCG, totV, totVG, totFunds, totCommit, totFG, allFundPct },
    };
  }, [bundle]);

  if (!rows.length) return null;

  return (
    <div style={{ padding: '0 24px 24px', overflowX: 'auto' }}>
      <h3 style={{ fontSize: 16, fontWeight: 700, color: '#00471F', marginBottom: 12 }}>
        2026 Goals &amp; Progress
      </h3>
      <table className={tableStyles.table}>
        <thead>
          <tr>
            <th>Sub-Team</th>
            <th style={{ textAlign: 'center' }}>Riders</th>
            <th style={{ textAlign: 'center' }}>Goal</th>
            <th style={{ textAlign: 'center' }}>Chall</th>
            <th style={{ textAlign: 'center' }}>Goal</th>
            <th style={{ textAlign: 'center' }}>Vol</th>
            <th style={{ textAlign: 'center' }}>Goal</th>
            <th style={{ textAlign: 'right' }}>Raised</th>
            <th style={{ textAlign: 'right' }}>Committed</th>
            <th style={{ textAlign: 'right' }}>Fund Goal</th>
            <th style={{ textAlign: 'center' }}>%</th>
          </tr>
        </thead>
        <tbody>
          {rows.map((row) => (
            <tr key={row.name}>
              <td>{shortTeam(row.name)}</td>
              <GoalCells current={row.r} goal={row.rg} />
              <GoalCells current={row.c} goal={row.cg} />
              <GoalCells current={row.v} goal={row.vg} />
              <td style={{ textAlign: 'right' }}>{moneyShort(row.funds)}</td>
              <td style={{ textAlign: 'right' }}>{moneyShort(row.committed)}</td>
              <td style={{ textAlign: 'right' }}>{row.fg ? moneyShort(row.fg) : '—'}</td>
              <td style={{ textAlign: 'center' }}>{row.fundPct}%</td>
            </tr>
          ))}
        </tbody>
        {totals && (
          <tfoot>
            <tr className={tableStyles.totalsRow}>
              <td>TOTAL</td>
              <td style={{ textAlign: 'center' }}>{totals.totR}</td>
              <td style={{ textAlign: 'center' }}>{totals.totRG}</td>
              <td style={{ textAlign: 'center' }}>{totals.totC}</td>
              <td style={{ textAlign: 'center' }}>{totals.totCG}</td>
              <td style={{ textAlign: 'center' }}>{totals.totV}</td>
              <td style={{ textAlign: 'center' }}>{totals.totVG}</td>
              <td style={{ textAlign: 'right' }}>{moneyShort(totals.totFunds)}</td>
              <td style={{ textAlign: 'right' }}>{moneyShort(totals.totCommit)}</td>
              <td style={{ textAlign: 'right' }}>{moneyShort(totals.totFG)}</td>
              <td style={{ textAlign: 'center' }}>{totals.allFundPct}%</td>
            </tr>
          </tfoot>
        )}
      </table>
    </div>
  );
}

function GoalCells({ current, goal }: { current: number; goal: number }) {
  if (!goal) {
    return (
      <>
        <td className={tableStyles.goalCell} style={{ textAlign: 'center' }}>—</td>
        <td className={tableStyles.goalCell} style={{ textAlign: 'center' }}>—</td>
      </>
    );
  }
  const pct = Math.round((current / goal) * 100);
  return (
    <>
      <td className={tableStyles.goalCell} style={{ textAlign: 'center', whiteSpace: 'nowrap' }}>
        <span className={pct >= 100 ? tableStyles.goalOver : tableStyles.goalUnder}>
          {current}
        </span>
        {' '}
        <MiniBar value={current} max={goal} />
      </td>
      <td className={tableStyles.goalCell} style={{ textAlign: 'center' }}>{goal}</td>
    </>
  );
}
