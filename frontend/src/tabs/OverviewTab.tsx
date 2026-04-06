import { useState, useCallback, useEffect } from 'react';
import { useDashboardStore } from '../store/useDashboardStore';
import { money } from '../utils/format';
import { GOALS_2026 } from '../types/constants';
import { FundraisingGrowthChart } from '../components/charts/FundraisingGrowthChart';
import { SignupTimelineChart } from '../components/charts/SignupTimelineChart';
import { ParticipantTypesChart } from '../components/charts/ParticipantTypesChart';
import { RaisedByTeamChart } from '../components/charts/RaisedByTeamChart';
import styles from '../styles/goals.module.css';
import layoutStyles from '../styles/layout.module.css';

interface GoalRowItem {
  key: string;
  label: string;
  current: number;
  target: number;
  fmt: (v: number) => string;
}

const LS_KEY = 'pelotonia-overview-targets';

function loadTargets(): Record<string, number> {
  try {
    return JSON.parse(localStorage.getItem(LS_KEY) || '{}');
  } catch {
    return {};
  }
}

function saveTargets(targets: Record<string, number>) {
  localStorage.setItem(LS_KEY, JSON.stringify(targets));
}

export function OverviewTab() {
  const bundle = useDashboardStore((s) => s.bundle);
  const [targets, setTargets] = useState<Record<string, number>>(loadTargets);

  useEffect(() => {
    saveTargets(targets);
  }, [targets]);

  const handleTargetClick = useCallback(
    (key: string, currentTarget: number, _fmt: (v: number) => string) => {
      const input = prompt(`Set new target for ${key}:`, String(currentTarget));
      if (input === null) return;
      const val = Number(input.replace(/[^0-9.]/g, ''));
      if (!isNaN(val) && val > 0) {
        setTargets((prev) => ({ ...prev, [key]: val }));
      }
    },
    [],
  );

  if (!bundle) return null;

  const { overview } = bundle;

  const goalDefaults: Record<string, number> = {
    riders: GOALS_2026.riders,
    challengers: GOALS_2026.challengers,
    volunteers: GOALS_2026.volunteers,
    raised: overview.goal || 5990023,
  };

  const goalItems: GoalRowItem[] = [
    {
      key: 'riders',
      label: 'RIDERS',
      current: overview.riders || 0,
      target: targets.riders ?? goalDefaults.riders,
      fmt: (v) => v.toLocaleString(),
    },
    {
      key: 'challengers',
      label: 'CHALLENGERS',
      current: overview.challengers || 0,
      target: targets.challengers ?? goalDefaults.challengers,
      fmt: (v) => v.toLocaleString(),
    },
    {
      key: 'volunteers',
      label: 'VOLUNTEERS',
      current: overview.volunteers || 0,
      target: targets.volunteers ?? goalDefaults.volunteers,
      fmt: (v) => v.toLocaleString(),
    },
    {
      key: 'raised',
      label: '2026 FUNDS RAISED',
      current: overview.raised || 0,
      target: targets.raised ?? goalDefaults.raised,
      fmt: (v) => '$' + v.toLocaleString(),
    },
  ];

  const gpf = overview.general_peloton_funds || 0;

  return (
    <div>
      {/* Goals Panel */}
      <div style={{ padding: '24px 32px' }}>
        <div className={styles.goalsPanel}>
          <div className={styles.goalsTitle}>
            PELOTONIA<sup>&reg;</sup> 2026
            <span className={styles.goalsAsOf}>
              {overview.last_scraped
                ? `as of ${new Date(overview.last_scraped).toLocaleString('en-US', { month: 'short', day: 'numeric', year: 'numeric', hour: 'numeric', minute: '2-digit', timeZoneName: 'short' })}`
                : ''}
            </span>
          </div>

          <div>
            {goalItems.map((g) => {
              const gp = g.target > 0 ? Math.min((g.current / g.target) * 100, 100) : 0;
              return (
                <div key={g.key} className={styles.goalRow}>
                  <div className={styles.goalRowLabel}>{g.label}</div>
                  <div className={styles.goalBarWrap}>
                    <div className={styles.goalBarLine} />
                    <div
                      className={styles.goalBarFillLine}
                      style={{ width: `${gp}%` }}
                    />
                    <div
                      className={`${styles.goalArrowWrap} ${gp > 80 ? styles.goalArrowFlipped : ''}`}
                      style={{ left: `${gp}%` }}
                    >
                      <img
                        src="/pelotonia-arrow-green.png"
                        alt=""
                        className={styles.goalArrowImg}
                      />
                      <span className={styles.goalCurrentVal}>{g.fmt(g.current)}</span>
                    </div>
                  </div>
                  <div
                    className={styles.goalTarget}
                    title="Click to edit target"
                    onClick={() => handleTargetClick(g.key, g.target, g.fmt)}
                  >
                    {g.fmt(g.target)}
                  </div>
                </div>
              );
            })}
          </div>

          {/* Scale row */}
          <div className={`${styles.goalRow} ${styles.goalsScaleRow}`}>
            <div className={styles.goalsPctLabel}>% OF GOAL</div>
            <div className={styles.goalsScaleTicks}>
              <span>0%</span>
              <span>25%</span>
              <span>50%</span>
              <span>75%</span>
              <span>100%</span>
            </div>
            <div className={styles.goalsScaleGoalLabel}>GOAL</div>
          </div>

          {gpf > 0 && (
            <div
              style={{
                fontSize: '11px',
                color: '#888',
                textAlign: 'right',
                marginTop: '4px',
                paddingRight: '4px',
                fontStyle: 'italic',
              }}
            >
              * Includes {money(gpf)} in general peloton funds not attributed to individual members
            </div>
          )}
        </div>
      </div>

      {/* Charts */}
      <div className={layoutStyles.grid2}>
        <div className={layoutStyles.card}>
          <h2 className={layoutStyles.cardTitle}>Fundraising Growth</h2>
          <FundraisingGrowthChart />
        </div>
        <div className={layoutStyles.card}>
          <h2 className={layoutStyles.cardTitle}>Participant Signups Over Time</h2>
          <SignupTimelineChart />
        </div>
      </div>

      <div className={layoutStyles.grid2}>
        <div className={layoutStyles.card}>
          <h2 className={layoutStyles.cardTitle}>Participant Types by Sub-Team</h2>
          <ParticipantTypesChart />
        </div>
        <div className={layoutStyles.card}>
          <h2 className={layoutStyles.cardTitle}>Raised by Sub-Team</h2>
          <RaisedByTeamChart />
        </div>
      </div>
    </div>
  );
}
