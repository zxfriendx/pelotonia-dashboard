import type { Member } from '../types';

export function memberType(m: Member): string {
  if (m.is_rider) return 'Rider';
  if (m.is_challenger) return 'Challenger';
  if (m.is_volunteer) return 'Volunteer';
  if (m.route_names) return 'Rider';
  return '—';
}
