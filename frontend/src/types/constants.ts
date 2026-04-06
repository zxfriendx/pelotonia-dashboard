export const BRAND = {
  green: '#44D62C',
  forest: '#00471F',
  black: '#0E1411',
  tread: '#29322D',
  white: '#FFFFFF',
  grayBg: '#f5f6f7',
} as const;

export const LAST_YEAR_TOTAL = 5009310;
export const REGISTRATION_OPEN = new Date(2026, 2, 4);
export const RIDE_WEEKEND = new Date(2026, 7, 1);
export const FUNDRAISING_CLOSE = new Date(2026, 9, 15);
export const CAMPAIGN_START = REGISTRATION_OPEN;
export const CAMPAIGN_END = FUNDRAISING_CLOSE;

export const GOALS_2026 = { riders: 2100, challengers: 547, volunteers: 1500 } as const;

export const GOALS_2026_SUBTEAMS: Record<string, { riders: number; challengers: number; funds: number }> = {
  'Audit': { riders: 19, challengers: 7, funds: 57651 },
  'Commercial, CRE, and Capital Markets': { riders: 221, challengers: 64, funds: 726864 },
  'Communications': { riders: 11, challengers: 2, funds: 22182 },
  'Consumer Regional Bank': { riders: 1016, challengers: 236, funds: 1958856 },
  'Corporate Operations': { riders: 133, challengers: 49, funds: 735662 },
  'Credit, Collections, and Financial Recovery Group': { riders: 61, challengers: 17, funds: 192489 },
  'Finance and Strategy': { riders: 91, challengers: 17, funds: 316231 },
  'Friends, Family, Retirees, and Alumni': { riders: 117, challengers: 4, funds: 171647 },
  'Human Resources': { riders: 50, challengers: 17, funds: 158489 },
  'Legal & Public Affairs': { riders: 18, challengers: 4, funds: 199233 },
  'Office of Inclusion': { riders: 5, challengers: 1, funds: 16605 },
  'Payments & TM': { riders: 68, challengers: 27, funds: 161571 },
  'Risk': { riders: 59, challengers: 19, funds: 127397 },
  'Tech/M&A and Cyber': { riders: 231, challengers: 82, funds: 1145146 },
};

export const LAST_YEAR_SUBTEAMS: Record<string, { riders: number; challengers: number; volunteers: number; total: number }> = {
  'Audit': { riders: 15, challengers: 7, volunteers: 6, total: 28 },
  'Commercial, CRE, and Capital Markets': { riders: 177, challengers: 62, volunteers: 82, total: 321 },
  'Communications': { riders: 9, challengers: 2, volunteers: 1, total: 12 },
  'Consumer Regional Bank': { riders: 813, challengers: 241, volunteers: 632, total: 1686 },
  'Corporate Operations': { riders: 106, challengers: 48, volunteers: 71, total: 225 },
  'Credit, Collections, and Financial Recovery Group': { riders: 49, challengers: 18, volunteers: 24, total: 91 },
  'Finance and Strategy': { riders: 73, challengers: 16, volunteers: 42, total: 131 },
  'Friends, Family, Retirees, and Alumni': { riders: 118, challengers: 4, volunteers: 25, total: 147 },
  'Human Resources': { riders: 40, challengers: 17, volunteers: 51, total: 108 },
  'Legal & Public Affairs': { riders: 14, challengers: 5, volunteers: 26, total: 45 },
  'Office of Inclusion': { riders: 4, challengers: 1, volunteers: 1, total: 6 },
  'Payments & TM': { riders: 54, challengers: 26, volunteers: 46, total: 126 },
  'Risk': { riders: 47, challengers: 18, volunteers: 54, total: 119 },
  'Tech/M&A and Cyber': { riders: 185, challengers: 86, volunteers: 173, total: 444 },
};

export const PARENT_TEAM_ID = 'a0s3t00000BKX8sAAH';

export const TAB_IDS = [
  'overview', 'teams', 'routes', 'members', 'donors',
  'companies', 'donations', 'infographics', 'report', 'kids', 'leaderboard',
] as const;

export type TabId = typeof TAB_IDS[number];
