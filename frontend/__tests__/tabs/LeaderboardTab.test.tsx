import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen } from '@testing-library/react';
import { LeaderboardTab } from '../../src/tabs/LeaderboardTab';
import { mockBundle } from '../fixtures/bundleData';

// Mock CSS modules
vi.mock('../../src/styles/kpi.module.css', () => ({
  default: new Proxy({}, { get: (_, prop) => String(prop) }),
}));
vi.mock('../../src/styles/layout.module.css', () => ({
  default: new Proxy({}, { get: (_, prop) => String(prop) }),
}));

// Mock chart component to avoid canvas issues in jsdom
vi.mock('../../src/components/charts/OrgRaisedChart', () => ({
  OrgRaisedChart: () => <div data-testid="org-chart">Chart</div>,
}));

// Mock the store
vi.mock('../../src/store/useDashboardStore', () => ({
  useDashboardStore: (selector: (state: Record<string, unknown>) => unknown) => {
    const state = {
      bundle: mockBundle,
    };
    return selector(state);
  },
}));

describe('LeaderboardTab', () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it('renders the org table', () => {
    render(<LeaderboardTab />);
    expect(screen.getByText('Organization Leaderboard')).toBeInTheDocument();
    expect(screen.getByText('Huntington Bank')).toBeInTheDocument();
    expect(screen.getByText('Nationwide Insurance')).toBeInTheDocument();
  });

  it('renders KPI cards', () => {
    render(<LeaderboardTab />);
    expect(screen.getByText('Huntington Rank')).toBeInTheDocument();
    expect(screen.getByText('Huntington Raised')).toBeInTheDocument();
    expect(screen.getByText('% of Pelotonia Total')).toBeInTheDocument();
    expect(screen.getByText('Total Members')).toBeInTheDocument();
  });

  it('displays Huntington rank as 1', () => {
    render(<LeaderboardTab />);
    // Huntington has higher raised ($150k) than Nationwide ($120k), so rank 1
    const kpiCards = screen.getByText('Huntington Rank').parentElement!;
    expect(kpiCards).toHaveTextContent('1');
  });

  it('displays Huntington raised amount', () => {
    render(<LeaderboardTab />);
    // $150,000 appears in both KPI card and table row; just verify at least one exists
    const matches = screen.getAllByText('$150,000');
    expect(matches.length).toBeGreaterThanOrEqual(1);
  });

  it('displays total members across orgs', () => {
    render(<LeaderboardTab />);
    // 250 + 180 = 430
    expect(screen.getByText('430')).toBeInTheDocument();
  });

  it('renders the chart component', () => {
    render(<LeaderboardTab />);
    expect(screen.getByTestId('org-chart')).toBeInTheDocument();
  });

  it('shows column headers', () => {
    render(<LeaderboardTab />);
    expect(screen.getByText('Organization')).toBeInTheDocument();
    // "Members" appears both in KPI label ("Total Members") and column header
    expect(screen.getAllByText('Members').length).toBeGreaterThanOrEqual(1);
    // "Raised" column header includes sort indicator; use regex
    expect(screen.getAllByText(/^Raised/).length).toBeGreaterThanOrEqual(1);
    expect(screen.getByText('Goal')).toBeInTheDocument();
    expect(screen.getByText('All-Time')).toBeInTheDocument();
  });
});
