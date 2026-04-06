import { describe, it, expect } from 'vitest';
import { memberType } from '../../src/utils/memberType';
import type { Member } from '../../src/types';

function makeMember(overrides: Partial<Member> = {}): Member {
  return {
    public_id: 'test-001',
    name: 'Test User',
    raised: 0,
    all_time_raised: 0,
    is_cancer_survivor: 0,
    tags: '[]',
    team_name: 'Team Huntington Bank - Test',
    is_rider: 0,
    is_challenger: 0,
    is_volunteer: 0,
    ride_type: '',
    committed_amount: 0,
    personal_goal: 0,
    committed_high_roller: 0,
    route_names: '',
    profile_image_url: '',
    is_captain: 0,
    years_active: 1,
    ...overrides,
  };
}

describe('memberType', () => {
  it('classifies rider', () => {
    expect(memberType(makeMember({ is_rider: 1 }))).toBe('Rider');
  });

  it('classifies challenger', () => {
    expect(memberType(makeMember({ is_challenger: 1 }))).toBe('Challenger');
  });

  it('classifies volunteer', () => {
    expect(memberType(makeMember({ is_volunteer: 1 }))).toBe('Volunteer');
  });

  it('falls back to Rider when route_names is set', () => {
    expect(memberType(makeMember({ route_names: '50-Mile Route' }))).toBe('Rider');
  });

  it('returns dash for unknown type', () => {
    expect(memberType(makeMember())).toBe('\u2014');
  });

  it('prioritizes rider over challenger', () => {
    expect(memberType(makeMember({ is_rider: 1, is_challenger: 1 }))).toBe('Rider');
  });

  it('prioritizes challenger over volunteer', () => {
    expect(memberType(makeMember({ is_challenger: 1, is_volunteer: 1 }))).toBe('Challenger');
  });
});
