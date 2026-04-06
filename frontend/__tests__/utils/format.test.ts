import { describe, it, expect } from 'vitest';
import { money, moneyFull, moneyShort, shortTeam, pct } from '../../src/utils/format';

describe('money', () => {
  it('formats zero', () => {
    expect(money(0)).toBe('$0');
  });

  it('formats thousands with comma', () => {
    expect(money(1234)).toBe('$1,234');
  });

  it('formats millions with commas', () => {
    expect(money(1234567)).toBe('$1,234,567');
  });
});

describe('moneyFull', () => {
  it('formats with two decimal places', () => {
    expect(moneyFull(1234.5)).toBe('$1,234.50');
  });

  it('formats whole number with .00', () => {
    expect(moneyFull(100)).toBe('$100.00');
  });

  it('rounds to two decimals', () => {
    expect(moneyFull(99.999)).toBe('$100.00');
  });
});

describe('moneyShort', () => {
  it('formats millions with M suffix', () => {
    expect(moneyShort(1500000)).toBe('$1.5M');
  });

  it('formats thousands with k suffix', () => {
    expect(moneyShort(5000)).toBe('$5k');
  });

  it('formats small values without suffix', () => {
    expect(moneyShort(500)).toBe('$500');
  });

  it('formats exactly 1000 as $1k', () => {
    expect(moneyShort(1000)).toBe('$1k');
  });

  it('formats exactly 1000000 as $1.0M', () => {
    expect(moneyShort(1000000)).toBe('$1.0M');
  });
});

describe('shortTeam', () => {
  it('strips Team Huntington Bank prefix', () => {
    expect(shortTeam('Team Huntington Bank - Consumer Regional Bank')).toBe('Consumer Regional Bank');
  });

  it('returns name unchanged when no prefix', () => {
    expect(shortTeam('Some Other Team')).toBe('Some Other Team');
  });

  it('returns dash for null', () => {
    expect(shortTeam(null)).toBe('\u2014');
  });

  it('returns dash for undefined', () => {
    expect(shortTeam(undefined)).toBe('\u2014');
  });

  it('returns dash for empty string', () => {
    expect(shortTeam('')).toBe('\u2014');
  });
});

describe('pct', () => {
  it('calculates percentage with one decimal', () => {
    expect(pct(50, 200)).toBe(25);
  });

  it('returns 0 when goal is zero', () => {
    expect(pct(100, 0)).toBe(0);
  });

  it('handles fractional percentages', () => {
    expect(pct(1, 3)).toBeCloseTo(33.3, 0);
  });

  it('returns 100 for equal value and goal', () => {
    expect(pct(500, 500)).toBe(100);
  });
});
