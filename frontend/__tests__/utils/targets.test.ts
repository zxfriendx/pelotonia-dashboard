import { describe, it, expect } from 'vitest';
import { computeSmartTargets, getLastYearEstimate } from '../../src/utils/targets';
import { GOALS_2026 } from '../../src/types/constants';
import { mockBundle } from '../fixtures/bundleData';

describe('computeSmartTargets', () => {
  it('returns targets for __all__ and each team', () => {
    const targets = computeSmartTargets(mockBundle);

    expect(targets).toHaveProperty('__all__');
    for (const tb of mockBundle.teamBreakdown) {
      expect(targets).toHaveProperty(tb.name);
    }
  });

  it('sets __all__ riders/challengers/volunteers from GOALS_2026', () => {
    const targets = computeSmartTargets(mockBundle);
    const all = targets['__all__'];

    expect(all.riders).toBe(GOALS_2026.riders);
    expect(all.challengers).toBe(GOALS_2026.challengers);
    expect(all.volunteers).toBe(GOALS_2026.volunteers);
    expect(all.funds).toBeNull();
  });

  it('volunteer sub-team targets sum to GOALS_2026.volunteers', () => {
    const targets = computeSmartTargets(mockBundle);
    const teamKeys = mockBundle.teamBreakdown.map((t) => t.name);

    let sum = 0;
    for (const k of teamKeys) {
      sum += targets[k].volunteers;
    }
    expect(sum).toBe(GOALS_2026.volunteers);
  });

  it('assigns non-zero funds for known sub-teams', () => {
    const targets = computeSmartTargets(mockBundle);
    const crbKey = 'Team Huntington Bank - Consumer Regional Bank';
    expect(targets[crbKey].funds).toBeGreaterThan(0);
  });
});

describe('getLastYearEstimate', () => {
  it('returns totals for __all__', () => {
    const ly = getLastYearEstimate('__all__');
    expect(ly.isEstimate).toBe(false);
    expect(ly.riders).toBe(1707);
    expect(ly.challengers).toBe(556);
    expect(ly.volunteers).toBe(1240);
    expect(ly.funds).toBeGreaterThan(0);
  });

  it('returns data for known sub-team', () => {
    const ly = getLastYearEstimate('Team Huntington Bank - Consumer Regional Bank');
    expect(ly.isEstimate).toBe(false);
    expect(ly.riders).toBe(813);
    expect(ly.challengers).toBe(241);
    expect(ly.volunteers).toBe(632);
  });

  it('returns estimate for unknown team', () => {
    const ly = getLastYearEstimate('Team Huntington Bank - Unknown Division');
    expect(ly.isEstimate).toBe(true);
    expect(ly.riders).toBe(0);
    expect(ly.challengers).toBe(0);
    expect(ly.volunteers).toBe(0);
  });
});
