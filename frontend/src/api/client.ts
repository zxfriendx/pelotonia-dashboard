import type { BundleData, RouteMember } from '../types';

const API_BASE = '/api';

export async function fetchBundle(): Promise<BundleData> {
  const res = await fetch(`${API_BASE}/bundle`);
  if (!res.ok) throw new Error(`Failed to fetch bundle: ${res.status}`);
  return res.json();
}

export async function fetchRouteMembers(routeId: string): Promise<RouteMember[]> {
  const res = await fetch(`${API_BASE}/route-members/${routeId}`);
  if (!res.ok) throw new Error(`Failed to fetch route members: ${res.status}`);
  return res.json();
}
