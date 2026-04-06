import type { BundleData, TeamTargets } from '../types';
import { shortTeam } from './format';
import { GOALS_2026, GOALS_2026_SUBTEAMS, LAST_YEAR_SUBTEAMS, LAST_YEAR_TOTAL } from '../types/constants';

export function computeSmartTargets(bundle: BundleData): Record<string, TeamTargets> {
  const { teamBreakdown } = bundle;

  const allTargets: TeamTargets = {
    funds: null,
    riders: GOALS_2026.riders,
    challengers: GOALS_2026.challengers,
    volunteers: GOALS_2026.volunteers,
  };

  const LY_TOTALS = { volunteers: 1240 };
  const targets: Record<string, TeamTargets> = { '__all__': allTargets };

  teamBreakdown.forEach(t => {
    const short = shortTeam(t.name);
    const buGoal = GOALS_2026_SUBTEAMS[short];
    const ly = LAST_YEAR_SUBTEAMS[short];

    if (buGoal) {
      targets[t.name] = {
        funds: buGoal.funds,
        riders: buGoal.riders,
        challengers: buGoal.challengers,
        volunteers: ly
          ? Math.max(Math.round(GOALS_2026.volunteers * (ly.volunteers / LY_TOTALS.volunteers)), ly.volunteers > 0 ? 1 : 0)
          : 0,
      };
    } else {
      targets[t.name] = { funds: 0, riders: 1, challengers: 0, volunteers: 0 };
    }
  });

  // Fix rounding so volunteer sub-team goals sum exactly to the parent goal
  const teamKeys = teamBreakdown.map(t => t.name);
  const goal = GOALS_2026.volunteers;
  if (goal) {
    let sum = 0;
    teamKeys.forEach(k => { sum += targets[k].volunteers; });
    let diff = goal - sum;
    const sorted = [...teamKeys].sort((a, b) => targets[b].volunteers - targets[a].volunteers);
    let i = 0;
    while (diff !== 0) {
      const step = diff > 0 ? 1 : -1;
      targets[sorted[i % sorted.length]].volunteers += step;
      diff -= step;
      i++;
    }
  }

  return targets;
}

export function getLastYearEstimate(selectedTeam: string): {
  funds: number;
  riders: number;
  challengers: number;
  volunteers: number;
  isEstimate: boolean;
} {
  if (selectedTeam === '__all__') {
    return { funds: LAST_YEAR_TOTAL, riders: 1707, challengers: 556, volunteers: 1240, isEstimate: false };
  }
  const short = shortTeam(selectedTeam);
  const ly = LAST_YEAR_SUBTEAMS[short];
  if (ly) {
    return { funds: 0, riders: ly.riders, challengers: ly.challengers, volunteers: ly.volunteers, isEstimate: false };
  }
  return { funds: 0, riders: 0, challengers: 0, volunteers: 0, isEstimate: true };
}
