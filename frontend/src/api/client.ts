import type { BundleData, RouteMember } from '../types';

const API_BASE = '/api';

export async function fetchBundle(): Promise<BundleData> {
  const res = await fetch(`${API_BASE}/bundle`);
  if (!res.ok) throw new Error(`Failed to fetch bundle: ${res.status}`);
  return res.json();
}

/** First-wave payload: small datasets needed to render the initial view. */
export async function fetchBundleCore(): Promise<Partial<BundleData>> {
  const res = await fetch(`${API_BASE}/bundle/core`);
  if (!res.ok) throw new Error(`Failed to fetch core bundle: ${res.status}`);
  return res.json();
}

/** Second-wave payload: heavy tab-only datasets, fetched after first paint. */
export async function fetchBundleRest(): Promise<Partial<BundleData>> {
  const res = await fetch(`${API_BASE}/bundle/rest`);
  if (!res.ok) throw new Error(`Failed to fetch rest bundle: ${res.status}`);
  return res.json();
}

export async function fetchRouteMembers(routeId: string): Promise<RouteMember[]> {
  const res = await fetch(`${API_BASE}/route-members/${routeId}`);
  if (!res.ok) throw new Error(`Failed to fetch route members: ${res.status}`);
  return res.json();
}
