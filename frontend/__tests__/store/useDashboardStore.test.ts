import { describe, it, expect, vi, beforeEach } from 'vitest';
import type { BundleData } from '../../src/types';
import { mockBundle } from '../fixtures/bundleData';

// Mock the API client so we can drive the two-wave (core → rest) load by hand.
vi.mock('../../src/api/client', () => ({
  fetchBundleCore: vi.fn(),
  fetchBundleRest: vi.fn(),
}));

import { fetchBundleCore, fetchBundleRest } from '../../src/api/client';
import { useDashboardStore } from '../../src/store/useDashboardStore';

const REST_KEYS = ['members', 'donations', 'donors', 'companies', 'orgSnapshots'] as const;

// Split the fixture the same way the backend splits /api/bundle.
function splitFixture() {
  const core: Partial<BundleData> = {};
  const rest: Partial<BundleData> = {};
  for (const [k, v] of Object.entries(mockBundle)) {
    if ((REST_KEYS as readonly string[]).includes(k)) (rest as Record<string, unknown>)[k] = v;
    else (core as Record<string, unknown>)[k] = v;
  }
  return { core, rest };
}

const flush = () => new Promise((r) => setTimeout(r, 0));

describe('useDashboardStore.loadBundle (two-wave)', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    useDashboardStore.setState({
      bundle: null,
      loading: false,
      error: null,
      restLoaded: false,
      restError: null,
    });
  });

  it('renders core first with heavy datasets empty, then merges rest', async () => {
    const { core, rest } = splitFixture();
    let resolveRest!: (v: Partial<BundleData>) => void;
    const restPromise = new Promise<Partial<BundleData>>((res) => (resolveRest = res));
    vi.mocked(fetchBundleCore).mockResolvedValue(core);
    vi.mocked(fetchBundleRest).mockReturnValue(restPromise);

    // First wave completes when loadBundle resolves (it only awaits core).
    await useDashboardStore.getState().loadBundle();

    let s = useDashboardStore.getState();
    expect(s.loading).toBe(false);
    expect(s.bundle).not.toBeNull();
    // Core data is present immediately…
    expect(s.bundle!.overview.raised).toBe(mockBundle.overview.raised);
    expect(s.bundle!.teams.length).toBe(mockBundle.teams.length);
    // …while heavy datasets are seeded empty and not yet "loaded".
    expect(s.restLoaded).toBe(false);
    expect(s.bundle!.members).toEqual([]);
    expect(s.bundle!.donations).toEqual([]);

    // Second wave arrives.
    resolveRest(rest);
    await flush();

    s = useDashboardStore.getState();
    expect(s.restLoaded).toBe(true);
    expect(s.bundle!.members.length).toBe(mockBundle.members.length);
    expect(s.bundle!.donations.length).toBe(mockBundle.donations.length);
    // Core data is untouched by the merge.
    expect(s.bundle!.overview.raised).toBe(mockBundle.overview.raised);
  });

  it('keeps the page usable and records restError if the rest wave fails', async () => {
    const { core } = splitFixture();
    vi.mocked(fetchBundleCore).mockResolvedValue(core);
    vi.mocked(fetchBundleRest).mockRejectedValue(new Error('network down'));

    await useDashboardStore.getState().loadBundle();
    await flush();

    const s = useDashboardStore.getState();
    expect(s.bundle).not.toBeNull(); // core still rendered
    expect(s.restLoaded).toBe(false);
    expect(s.restError).toBe('network down');
    expect(s.error).toBeNull(); // top-level load did not fail
  });

  it('surfaces a fatal error if the core wave fails', async () => {
    vi.mocked(fetchBundleCore).mockRejectedValue(new Error('core 500'));

    await useDashboardStore.getState().loadBundle();

    const s = useDashboardStore.getState();
    expect(s.bundle).toBeNull();
    expect(s.loading).toBe(false);
    expect(s.error).toBe('core 500');
  });
});
