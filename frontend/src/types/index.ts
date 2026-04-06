export interface Overview {
  team_name: string;
  raised: number;
  goal: number;
  all_time_raised: number;
  members_count: number;
  donations_count: number;
  total_donated: number;
  cancer_survivors: number;
  high_rollers: number;
  signature_riders: number;
  gravel_riders: number;
  riders: number;
  challengers: number;
  volunteers: number;
  total_committed: number;
  hr_committed: number;
  std_committed: number;
  general_peloton_funds: number;
  first_year: number;
  last_scraped: string;
}

export interface Team {
  id: string;
  name: string;
  raised: number;
  goal: number;
  all_time_raised: number;
  members_count: number;
}

export interface TimelineEntry {
  date: string;
  daily_count: number;
  daily_amount: number;
  cumulative: number;
}

export interface Member {
  public_id: string;
  name: string;
  raised: number;
  all_time_raised: number;
  is_cancer_survivor: number;
  tags: string;
  team_name: string;
  is_rider: number;
  is_challenger: number;
  is_volunteer: number;
  ride_type: string;
  committed_amount: number;
  personal_goal: number;
  committed_high_roller: number;
  route_names: string;
  profile_image_url: string;
  is_captain: number;
  years_active: number;
}

export interface Donation {
  opportunity_id: string;
  recipient_public_id: string;
  recipient_name: string;
  donor_name: string;
  recognition_name: string;
  anonymous_to_public: number;
  amount: number;
  date: string;
  team_name: string;
}

export interface TeamBreakdown {
  name: string;
  riders: number;
  challengers: number;
  volunteers: number;
  total: number;
  total_committed: number;
  total_raised: number;
  total_all_time: number;
  high_rollers: number;
  survivors: number;
  hr_committed: number;
  std_committed: number;
  first_year: number;
}

export interface CommitTier {
  tier: number;
  count: number;
  riders: number;
  challengers: number;
  total_raised: number;
  total_all_time: number;
  high_rollers: number;
}

export interface RideType {
  ride_category: string;
  count: number;
  riders: number;
  challengers: number;
  total_committed: number;
  total_raised: number;
}

export interface Route {
  id: string;
  name: string;
  distance: number;
  fundraising_commitment: number;
  capacity: number;
  starting_city: string;
  ending_city: string;
  image_url: string;
  ride_name: string;
  ride_type: string;
  ride_weekend_start: string;
  ride_weekend_end: string;
  signups: number;
  ride_total_signups: number;
  route_raised: number;
  route_committed: number;
}

export interface RouteMember {
  public_id: string;
  name: string;
  raised: number;
  committed_amount: number;
  tags: string;
  is_cancer_survivor: number;
  years: number;
  is_first_year: number;
}

export interface SignupTimelineEntry {
  snapshot_date: string;
  signature_riders: number;
  gravel_riders: number;
  members_count: number;
  raised: number;
  riders_count: number;
  challengers_count: number;
  volunteers_count: number;
}

export interface EventData {
  event_id: string;
  event_name: string;
  year: number;
}

export interface DonorSummary {
  donor: string;
  total: number;
  cnt: number;
}

export interface CompanySummary {
  company: string;
  total: number;
  donor_count: number;
  recipient_count: number;
  donation_count: number;
}

export interface Ticker {
  pelotonia_total_raised: number;
  pelotonia_member_count: number;
  pelotonia_all_time_raised: number;
  huntington_pct_of_total: number;
}

export interface SubteamSnapshot {
  snapshot_date: string;
  team_id: string;
  team_name: string;
  raised: number;
  all_time_raised: number;
  members_count: number;
}

export interface KidsOverview {
  snapshot_date: string;
  fundraiser_count: number;
  estimated_amount_raised: number;
  monetary_goal: number;
  team_count: number;
}

export interface KidsSnapshot {
  snapshot_date: string;
  fundraiser_count: number;
  estimated_amount_raised: number;
  monetary_goal: number;
  team_count: number;
}

export interface OrgSnapshot {
  team_id: string;
  name: string;
  members_count: number;
  sub_team_count: number;
  raised: number;
  goal: number;
  all_time_raised: number;
  last_scraped: string;
  snapshot_date?: string;
}

export interface BundleData {
  overview: Overview;
  teams: Team[];
  timeline: TimelineEntry[];
  fundraisers: Member[];
  donors: DonorSummary[];
  members: Member[];
  donations: Donation[];
  teamBreakdown: TeamBreakdown[];
  commitTiers: CommitTier[];
  rideTypes: RideType[];
  routes: Route[];
  signupTimeline: SignupTimelineEntry[];
  events: EventData[];
  companies: CompanySummary[];
  ticker: Ticker;
  subteamSnapshots: SubteamSnapshot[];
  kidsOverview: KidsOverview | null;
  kidsSnapshots: KidsSnapshot[];
  orgLeaderboard: OrgSnapshot[];
  orgSnapshots: OrgSnapshot[];
}

// Modal types
export type ModalType = 'routeMembers' | 'memberDonors' | 'donorRecipients' | 'teamMembers' | 'companyDetail';

export interface ModalState {
  type: ModalType;
  data: Record<string, unknown>;
}

// Targets for infographics
export interface TeamTargets {
  funds: number | null;
  riders: number;
  challengers: number;
  volunteers: number;
}
