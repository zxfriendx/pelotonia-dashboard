import type { Member } from '../types';

export function memberType(m: Member): string {
  if (m.is_rider) return 'Rider';
  if (m.is_challenger) return 'Challenger';
  if (m.is_volunteer) return 'Volunteer';
  if (m.route_names) return 'Rider';
  // On a team but no participation type chosen yet and no route signed up.
  // Matches the backend's "registered only" fall-through in _get_team_breakdown.
  if (m.team_name) return 'Registered';
  return '—';
}
