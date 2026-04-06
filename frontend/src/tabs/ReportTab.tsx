import { useState, useMemo } from 'react';
import { useDashboardStore } from '../store/useDashboardStore';
import { money, moneyShort, shortTeam } from '../utils/format';
import {
  BRAND,
  REGISTRATION_OPEN,
  RIDE_WEEKEND,
  GOALS_2026,
  GOALS_2026_SUBTEAMS,
} from '../types/constants';
import tableStyles from '../styles/table.module.css';

function deltaSpan(val: number, isMoney: boolean) {
  if (val > 0) {
    return (
      <span style={{ color: BRAND.green, fontWeight: 700 }}>
        +{isMoney ? moneyShort(val) : val.toLocaleString()}
      </span>
    );
  }
  if (val < 0) {
    return (
      <span style={{ color: '#e74c3c', fontWeight: 700 }}>
        -{isMoney ? moneyShort(Math.abs(val)) : Math.abs(val).toLocaleString()}
      </span>
    );
  }
  return <span style={{ color: '#888' }}>&mdash;</span>;
}

export function ReportTab() {
  const bundle = useDashboardStore((s) => s.bundle);
  const [period, setPeriod] = useState<'daily' | 'weekly'>('daily');
  const [subteamFilter, setSubteamFilter] = useState('__all__');

  const isWeekly = period === 'weekly';
  const lookbackDays = isWeekly ? 7 : 1;
  const filterAll = subteamFilter === '__all__';

  const teamOptions = useMemo(
    () => bundle?.teamBreakdown.map((t) => t.name) ?? [],
    [bundle],
  );

  const computed = useMemo(() => {
    if (!bundle) return null;
    const { overview, teamBreakdown, signupTimeline, subteamSnapshots } = bundle;

    const filteredTeam = !filterAll ? teamBreakdown.find((t) => t.name === subteamFilter) : null;

    const snap = signupTimeline || [];
    const today = snap.length ? snap[snap.length - 1] : null;
    let compare = null;
    if (snap.length > lookbackDays) {
      compare = snap[snap.length - 1 - lookbackDays];
    } else if (snap.length > 1) {
      compare = snap[0];
    }

    // Sub-team deltas
    const stSnaps = subteamSnapshots || [];
    const dates = [...new Set(stSnaps.map((s) => s.snapshot_date))].sort();
    const latestDate = dates.length ? dates[dates.length - 1] : null;
    let compareDate: string | null = null;
    if (dates.length > lookbackDays) {
      compareDate = dates[dates.length - 1 - lookbackDays];
    } else if (dates.length > 1) {
      compareDate = dates[0];
    }

    const moversMap: Record<string, {
      raised_now?: number; raised_prev?: number;
      members_now?: number; members_prev?: number;
    }> = {};

    stSnaps.forEach((s) => {
      if (s.snapshot_date === latestDate) {
        if (!moversMap[s.team_name]) moversMap[s.team_name] = {};
        moversMap[s.team_name].raised_now = s.raised || 0;
        moversMap[s.team_name].members_now = s.members_count || 0;
      }
      if (compareDate && s.snapshot_date === compareDate) {
        if (!moversMap[s.team_name]) moversMap[s.team_name] = {};
        moversMap[s.team_name].raised_prev = s.raised || 0;
        moversMap[s.team_name].members_prev = s.members_count || 0;
      }
    });

    let raisedDelta = 0, membersDelta = 0, ridersDelta = 0, challDelta = 0, volDelta = 0;
    if (!filterAll && moversMap[subteamFilter]) {
      const d = moversMap[subteamFilter];
      raisedDelta = (d.raised_now || 0) - (d.raised_prev || 0);
      membersDelta = (d.members_now || 0) - (d.members_prev || 0);
      ridersDelta = membersDelta;
    } else if (filterAll && today && compare) {
      raisedDelta = (today.raised || 0) - (compare.raised || 0);
      membersDelta = (today.members_count || 0) - (compare.members_count || 0);
      if ((compare.riders_count || 0) > 0) {
        ridersDelta = (today.riders_count || 0) - (compare.riders_count || 0);
        challDelta = (today.challengers_count || 0) - (compare.challengers_count || 0);
        volDelta = (today.volunteers_count || 0) - (compare.volunteers_count || 0);
      } else {
        ridersDelta = membersDelta;
      }
    }

    const movers = Object.entries(moversMap)
      .map(([name, d]) => ({
        name,
        raised_delta: (d.raised_now || 0) - (d.raised_prev || 0),
        members_delta: (d.members_now || 0) - (d.members_prev || 0),
      }))
      .filter((m) => m.raised_delta > 0)
      .sort((a, b) => b.raised_delta - a.raised_delta)
      .slice(0, isWeekly ? 5 : 3);

    let riders: number, challengers: number, volunteers: number, membersTotal: number;
    let highRollers: number, survivors: number, firstYear: number;
    let raised: number, goal: number, committed: number, hrCommitted: number, stdCommitted: number;
    let ridersGoal: number, challGoal: number, volGoal: number;

    if (filteredTeam) {
      riders = filteredTeam.riders || 0;
      challengers = filteredTeam.challengers || 0;
      volunteers = filteredTeam.volunteers || 0;
      membersTotal = filteredTeam.total || 0;
      highRollers = filteredTeam.high_rollers || 0;
      survivors = filteredTeam.survivors || 0;
      firstYear = filteredTeam.first_year || 0;
      raised = filteredTeam.total_raised || 0;
      const sn = shortTeam(subteamFilter);
      const stGoals = GOALS_2026_SUBTEAMS[sn] || {};
      goal = stGoals.funds || 0;
      committed = filteredTeam.total_committed || 0;
      hrCommitted = filteredTeam.hr_committed || 0;
      stdCommitted = filteredTeam.std_committed || 0;
      ridersGoal = stGoals.riders || riders;
      challGoal = stGoals.challengers || challengers;
      volGoal = volunteers || 1;
    } else {
      riders = overview.riders || 0;
      challengers = overview.challengers || 0;
      volunteers = overview.volunteers || 0;
      membersTotal = overview.members_count || 0;
      highRollers = overview.high_rollers || 0;
      survivors = overview.cancer_survivors || 0;
      firstYear = overview.first_year || 0;
      raised = overview.raised || 0;
      goal = overview.goal || 6000000;
      committed = overview.total_committed || 0;
      hrCommitted = overview.hr_committed || 0;
      stdCommitted = overview.std_committed || 0;
      ridersGoal = GOALS_2026.riders;
      challGoal = GOALS_2026.challengers;
      volGoal = GOALS_2026.volunteers;
    }

    return {
      raisedDelta, membersDelta, ridersDelta, challDelta, volDelta,
      movers, riders, challengers, volunteers, membersTotal,
      highRollers, survivors, firstYear, raised, goal,
      committed, hrCommitted, stdCommitted,
      ridersGoal, challGoal, volGoal,
      teamBreakdown,
    };
  }, [bundle, subteamFilter, lookbackDays, filterAll, isWeekly]);

  if (!bundle || !computed) return null;

  const now = new Date();
  const campaignDay = Math.max(Math.floor((now.getTime() - REGISTRATION_OPEN.getTime()) / 86400000), 0);
  const daysToRide = Math.max(Math.floor((RIDE_WEEKEND.getTime() - now.getTime()) / 86400000), 0);

  const {
    raisedDelta, membersDelta, ridersDelta, challDelta, volDelta,
    movers, riders, challengers, volunteers, membersTotal,
    highRollers, survivors, firstYear, raised, goal,
    committed, hrCommitted, stdCommitted,
    ridersGoal, challGoal, volGoal,
  } = computed;

  const fundsPct = goal > 0 ? Math.min((raised / goal) * 100, 100) : 0;
  const ridersPct = ridersGoal > 0 ? Math.min((riders / ridersGoal) * 100, 100) : 0;
  const challPct = challGoal > 0 ? Math.min((challengers / challGoal) * 100, 100) : 0;
  const volPct = volGoal > 0 ? Math.min((volunteers / volGoal) * 100, 100) : 0;

  const periodLabel = isWeekly ? 'Weekly Report' : 'Daily Report';
  const teamLabel = filterAll ? 'Team Huntington' : shortTeam(subteamFilter);

  let dateStr: string;
  if (isWeekly) {
    const ws = new Date(now.getTime() - 7 * 86400000);
    dateStr = `Week of ${ws.toLocaleDateString('en-US', { month: 'short', day: 'numeric' })} - ${now.toLocaleDateString('en-US', { month: 'short', day: 'numeric' })}, ${now.getFullYear()}`;
  } else {
    dateStr = now.toLocaleDateString('en-US', { weekday: 'long', month: 'long', day: 'numeric', year: 'numeric' });
  }

  return (
    <div>
      {/* Controls */}
      <div style={{ display: 'flex', gap: 12, marginBottom: 16, flexWrap: 'wrap', alignItems: 'center' }}>
        <div style={{ display: 'flex', gap: 4 }}>
          <button
            onClick={() => setPeriod('daily')}
            style={{
              padding: '6px 16px', borderRadius: 6, border: '1px solid #ddd', cursor: 'pointer',
              background: period === 'daily' ? BRAND.forest : '#fff',
              color: period === 'daily' ? '#fff' : '#333',
              fontWeight: 600,
            }}
          >
            Daily
          </button>
          <button
            onClick={() => setPeriod('weekly')}
            style={{
              padding: '6px 16px', borderRadius: 6, border: '1px solid #ddd', cursor: 'pointer',
              background: period === 'weekly' ? BRAND.forest : '#fff',
              color: period === 'weekly' ? '#fff' : '#333',
              fontWeight: 600,
            }}
          >
            Weekly
          </button>
        </div>
        <select
          value={subteamFilter}
          onChange={(e) => setSubteamFilter(e.target.value)}
          style={{ padding: '6px 12px', borderRadius: 6, border: '2px solid ' + BRAND.forest, fontWeight: 600, color: BRAND.forest }}
        >
          <option value="__all__">All Sub-Teams</option>
          {teamOptions.map((name) => (
            <option key={name} value={name}>{shortTeam(name)}</option>
          ))}
        </select>
      </div>

      {/* Report card */}
      <div style={{ maxWidth: 640, margin: '0 auto', background: '#f4f5f7', borderRadius: 12, overflow: 'hidden' }}>
        {/* Header */}
        <div style={{
          background: `linear-gradient(135deg, ${BRAND.forest}, ${BRAND.black})`,
          padding: '24px 28px', textAlign: 'center', borderRadius: '12px 12px 0 0',
        }}>
          <div style={{ fontSize: 22, fontWeight: 800, color: BRAND.green, marginBottom: 4 }}>
            {teamLabel} {periodLabel}
          </div>
          <div style={{ fontSize: 13, color: 'rgba(255,255,255,0.6)' }}>
            {dateStr} &middot; Day {campaignDay} of Campaign
          </div>
        </div>

        {/* Summary bar */}
        <div style={{
          background: BRAND.forest, padding: '12px 16px',
          display: 'flex', justifyContent: 'center', gap: 8, flexWrap: 'nowrap',
          overflowX: 'auto',
        }}>
          {[
            { val: money(raised), label: 'Raised', delta: deltaSpan(raisedDelta, true) },
            { val: money(goal), label: 'Goal', delta: null },
            { val: membersTotal.toLocaleString(), label: 'Members', delta: deltaSpan(membersDelta, false) },
            { val: String(highRollers), label: 'High Rollers', delta: null },
            { val: String(survivors), label: 'Survivors', delta: null },
            { val: String(firstYear), label: '1st Year', delta: null },
          ].map((item, i) => (
            <div key={i} style={{ textAlign: 'center', padding: '4px 6px', whiteSpace: 'nowrap', minWidth: 0 }}>
              <div style={{ fontSize: 18, fontWeight: 800, color: i === 1 ? 'rgba(255,255,255,0.8)' : BRAND.green }}>
                {item.val}
              </div>
              <div style={{ fontSize: 9, color: 'rgba(255,255,255,0.5)', textTransform: 'uppercase' }}>
                {item.label} {item.delta}
              </div>
            </div>
          ))}
        </div>

        {/* KPI Cards */}
        <div style={{ padding: '16px 12px 0' }}>
          <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 8 }}>
            <ReportKpiCard
              label="Funds Raised"
              value={money(raised)}
              goalStr={money(goal)}
              pctVal={fundsPct}
              delta={deltaSpan(raisedDelta, true)}
              chips={[
                ['Committed', moneyShort(committed)],
                ['High Rollers', moneyShort(hrCommitted)],
                ['Standard', moneyShort(stdCommitted)],
              ]}
            />
            <ReportKpiCard
              label="Riders"
              value={riders.toLocaleString()}
              goalStr={ridersGoal.toLocaleString()}
              pctVal={ridersPct}
              delta={deltaSpan(ridersDelta, false)}
              chips={[
                ['Day', String(campaignDay)],
                ['To Ride', daysToRide + 'd'],
                ['1st Year', String(firstYear)],
              ]}
            />
            <ReportKpiCard
              label="Challengers"
              value={challengers.toLocaleString()}
              goalStr={challGoal.toLocaleString()}
              pctVal={challPct}
              delta={deltaSpan(challDelta, false)}
              chips={[
                ['Day', String(campaignDay)],
                ['To Ride', daysToRide + 'd'],
                ['Total', membersTotal.toLocaleString()],
              ]}
            />
            <ReportKpiCard
              label="Volunteers"
              value={volunteers.toLocaleString()}
              goalStr={volGoal.toLocaleString()}
              pctVal={volPct}
              delta={deltaSpan(volDelta, false)}
              chips={[
                ['Day', String(campaignDay)],
                ['To Ride', daysToRide + 'd'],
                ['Total', membersTotal.toLocaleString()],
              ]}
            />
          </div>
        </div>

        {/* Top Movers */}
        {movers.length > 0 && (
          <div style={{ padding: '0 16px', marginTop: 24 }}>
            <div style={{ fontSize: 16, fontWeight: 700, color: BRAND.forest, marginBottom: 8 }}>
              {isWeekly ? 'Top Movers This Week' : 'Top Movers Today'}
            </div>
            <table className={tableStyles.table}>
              <thead>
                <tr>
                  <th>Sub-Team</th>
                  <th style={{ textAlign: 'right' }}>Raised</th>
                  <th style={{ textAlign: 'right' }}>Members</th>
                </tr>
              </thead>
              <tbody>
                {movers.map((m) => (
                  <tr key={m.name}>
                    <td>{shortTeam(m.name)}</td>
                    <td style={{ textAlign: 'right' }}>{deltaSpan(m.raised_delta, true)}</td>
                    <td style={{ textAlign: 'right' }}>{deltaSpan(m.members_delta, false)}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}

        {/* Participation by Sub-Team */}
        <div style={{ padding: '16px 16px 24px' }}>
          <div style={{ fontSize: 16, fontWeight: 700, color: BRAND.forest, marginBottom: 8 }}>
            Participation by Sub-Team
          </div>
          <div style={{ fontSize: '12px' }}>
            <table className={tableStyles.table} style={{ tableLayout: 'auto', width: '100%' }}>
              <thead>
                <tr>
                  <th style={{ maxWidth: 120 }}>Sub-Team</th>
                  <th style={{ textAlign: 'center' }}>Riders</th>
                  <th style={{ textAlign: 'center' }}>Chall</th>
                  <th style={{ textAlign: 'center' }}>Vol</th>
                  <th style={{ textAlign: 'center' }}>1st Yr</th>
                  <th style={{ textAlign: 'center' }}>Total</th>
                  <th style={{ textAlign: 'right' }}>Raised</th>
                  <th style={{ textAlign: 'right' }}>Goal</th>
                  <th style={{ textAlign: 'right' }}>Cmtd</th>
                  <th style={{ textAlign: 'center' }}>%</th>
                </tr>
              </thead>
              <tbody>
                {(filterAll
                  ? [...bundle.teamBreakdown].sort((a, b) => (b.total_committed || 0) - (a.total_committed || 0))
                  : bundle.teamBreakdown.filter((t) => t.name === subteamFilter)
                ).map((t) => {
                  const sn = shortTeam(t.name);
                  const stGoals = GOALS_2026_SUBTEAMS[sn] || {};
                  const fundGoal = stGoals.funds || 0;
                  const fundPctVal = fundGoal ? Math.round(((t.total_raised || 0) / fundGoal) * 100) + '%' : '—';
                  return (
                    <tr key={t.name}>
                      <td style={{ maxWidth: 120 }}>{sn}</td>
                      <td style={{ textAlign: 'center' }}>{t.riders || 0}</td>
                      <td style={{ textAlign: 'center' }}>{t.challengers || 0}</td>
                      <td style={{ textAlign: 'center' }}>{t.volunteers || 0}</td>
                      <td style={{ textAlign: 'center', color: '#888' }}>{t.first_year || 0}</td>
                      <td style={{ textAlign: 'center', fontWeight: 600 }}>{t.total || 0}</td>
                      <td style={{ textAlign: 'right', fontWeight: 600, color: BRAND.forest }}>{moneyShort(t.total_raised || 0)}</td>
                      <td style={{ textAlign: 'right', color: '#888' }}>{fundGoal ? moneyShort(fundGoal) : '—'}</td>
                      <td style={{ textAlign: 'right', fontWeight: 600, color: BRAND.forest }}>{moneyShort(t.total_committed || 0)}</td>
                      <td style={{ textAlign: 'center', color: '#888' }}>{fundPctVal}</td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
        </div>
      </div>
    </div>
  );
}

function ReportKpiCard({
  label,
  value,
  goalStr,
  pctVal,
  delta,
  chips,
}: {
  label: string;
  value: string;
  goalStr: string;
  pctVal: number;
  delta: React.ReactNode;
  chips: [string, string][];
}) {
  const barColor = pctVal >= 10 ? BRAND.green : '#6EF056';

  return (
    <div style={{
      background: '#fff', borderRadius: 12, border: '1px solid #e8ece9', overflow: 'hidden',
    }}>
      <div style={{ height: 3, background: `linear-gradient(90deg, ${BRAND.forest}, ${BRAND.green})` }} />
      <div style={{ padding: '20px 20px 16px' }}>
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
          <div style={{ fontSize: 11, textTransform: 'uppercase', letterSpacing: 1, color: '#888', fontWeight: 600 }}>
            {label}
          </div>
          <div style={{
            fontSize: 13, fontWeight: 800, color: BRAND.forest,
            background: 'rgba(68,214,44,0.1)', padding: '2px 8px', borderRadius: 12,
          }}>
            {pctVal.toFixed(1)}%
          </div>
        </div>
        <div style={{ fontSize: 36, fontWeight: 800, color: BRAND.forest, lineHeight: 1.1, marginTop: 8 }}>
          {value}
        </div>
        <div style={{ fontSize: 12, color: '#aaa', marginTop: 4 }}>
          of <b style={{ color: '#666' }}>{goalStr}</b> goal {delta}
        </div>
        <div style={{
          marginTop: 14, height: 10, borderRadius: 5, background: '#e8ece9', overflow: 'hidden',
        }}>
          <div style={{
            height: '100%', width: `${pctVal.toFixed(1)}%`, borderRadius: 5,
            background: `linear-gradient(90deg, ${BRAND.forest}, ${barColor})`,
          }} />
        </div>
        <div style={{ display: 'flex', gap: 4, marginTop: 12 }}>
          {chips.map(([l, v], i) => (
            <div key={i} style={{
              flex: 1, textAlign: 'center', padding: '6px 2px',
              background: '#f7f8f9', borderRadius: 6,
            }}>
              <div style={{ fontSize: 14, fontWeight: 800, color: BRAND.forest }}>{v}</div>
              <div style={{ fontSize: 9, color: '#999', textTransform: 'uppercase', letterSpacing: 0.3, marginTop: 1 }}>{l}</div>
            </div>
          ))}
        </div>
      </div>
    </div>
  );
}
