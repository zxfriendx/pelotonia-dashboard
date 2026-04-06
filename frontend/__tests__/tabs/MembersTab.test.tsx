import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen, fireEvent } from '@testing-library/react';
import { MembersTab } from '../../src/tabs/MembersTab';
import { mockBundle } from '../fixtures/bundleData';

// Mock CSS modules
vi.mock('../../src/styles/table.module.css', () => ({
  default: new Proxy({}, { get: (_, prop) => String(prop) }),
}));
vi.mock('../../src/styles/layout.module.css', () => ({
  default: new Proxy({}, { get: (_, prop) => String(prop) }),
}));
vi.mock('../../src/styles/kpi.module.css', () => ({
  default: new Proxy({}, { get: (_, prop) => String(prop) }),
}));

// Mock the store
const mockOpenModal = vi.fn();
const mockClearMemberHighlight = vi.fn();

vi.mock('../../src/store/useDashboardStore', () => ({
  useDashboardStore: (selector: (state: Record<string, unknown>) => unknown) => {
    const state = {
      bundle: mockBundle,
      openModal: mockOpenModal,
      memberHighlight: null,
      clearMemberHighlight: mockClearMemberHighlight,
    };
    return selector(state);
  },
}));

describe('MembersTab', () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it('renders the member table', () => {
    render(<MembersTab />);
    // Alice has is_captain=1, so her name appears with a star prefix in the same <td>
    expect(screen.getByText(/Alice Johnson/)).toBeInTheDocument();
    expect(screen.getByText('Bob Smith')).toBeInTheDocument();
    expect(screen.getByText('Carol Davis')).toBeInTheDocument();
  });

  it('renders KPI cards', () => {
    render(<MembersTab />);
    expect(screen.getByText('Total Members')).toBeInTheDocument();
    expect(screen.getByText('Unique Donors')).toBeInTheDocument();
    expect(screen.getByText('Avg Donors / Member')).toBeInTheDocument();
  });

  it('displays correct member count in KPI card', () => {
    render(<MembersTab />);
    // The Total Members KPI card shows the count
    const totalMembersLabel = screen.getByText('Total Members');
    const kpiCard = totalMembersLabel.parentElement!;
    expect(kpiCard).toHaveTextContent('3');
  });

  it('sorts members by raised descending', () => {
    render(<MembersTab />);
    const rows = screen.getAllByTitle('Click to see donations');
    // Alice ($5000) should be first, Bob ($3000) second, Carol ($0) third
    expect(rows[0]).toHaveTextContent('Alice Johnson');
    expect(rows[1]).toHaveTextContent('Bob Smith');
    expect(rows[2]).toHaveTextContent('Carol Davis');
  });

  it('search filters members', () => {
    render(<MembersTab />);
    const searchInput = screen.getByPlaceholderText('Search by name, team, type, tags...');
    fireEvent.change(searchInput, { target: { value: 'bob' } });

    expect(screen.getByText('Bob Smith')).toBeInTheDocument();
    expect(screen.queryByText(/Alice Johnson/)).not.toBeInTheDocument();
    expect(screen.queryByText('Carol Davis')).not.toBeInTheDocument();
  });

  it('displays member types correctly', () => {
    render(<MembersTab />);
    const rows = screen.getAllByTitle('Click to see donations');
    expect(rows[0]).toHaveTextContent('Rider');
    expect(rows[1]).toHaveTextContent('Challenger');
    expect(rows[2]).toHaveTextContent('Volunteer');
  });

  it('displays sub-team names without prefix', () => {
    render(<MembersTab />);
    expect(screen.getAllByText('Consumer Regional Bank').length).toBeGreaterThan(0);
    expect(screen.getAllByText('Tech/M&A and Cyber').length).toBeGreaterThan(0);
  });
});
