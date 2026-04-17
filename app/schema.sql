-- Pelotonia Dashboard — Canonical Postgres Schema
-- Ported from SQLite (pelotonia_scraper.py, pledgeit_scraper.py, org_scraper.py)

CREATE TABLE IF NOT EXISTS teams (
    id text PRIMARY KEY,
    name text NOT NULL,
    level text,
    parent_id text,
    captain_name text,
    captain_public_id text,
    years_active double precision,
    story text,
    accepting_members boolean DEFAULT false,
    members_count double precision,
    num_sub_pelotons double precision,
    profile_image_url text,
    cover_image_url text,
    raised double precision DEFAULT 0,
    goal double precision DEFAULT 0,
    goal_override double precision,
    goal_achieved boolean DEFAULT false,
    all_time_raised double precision DEFAULT 0,
    total_raised_by_members double precision DEFAULT 0,
    general_peloton_funds double precision DEFAULT 0,
    last_scraped timestamptz,
    current_event_name text
);

CREATE TABLE IF NOT EXISTS members (
    public_id text PRIMARY KEY,
    name text NOT NULL,
    team_id text REFERENCES teams(id),
    is_captain boolean DEFAULT false,
    is_admin boolean DEFAULT false,
    is_cancer_survivor boolean DEFAULT false,
    raised double precision DEFAULT 0,
    attributed double precision DEFAULT 0,
    commitment_amount double precision DEFAULT 0,
    fundraising_goal double precision DEFAULT 0,
    profile_image_url text,
    first_name text,
    last_name text,
    registration_types text,
    story text,
    is_donor_list_visible boolean,
    all_time_raised double precision DEFAULT 0,
    tags text,
    current_event_name text,
    is_rider boolean DEFAULT false,
    is_volunteer boolean DEFAULT false,
    is_challenger boolean DEFAULT false,
    ride_type text,
    ride_types text,
    committed_amount double precision DEFAULT 0,
    personal_goal double precision DEFAULT 0,
    committed_high_roller boolean DEFAULT false,
    last_scraped timestamptz
);

CREATE TABLE IF NOT EXISTS donations (
    opportunity_id text PRIMARY KEY,
    recipient_public_id text NOT NULL REFERENCES members(public_id),
    event_id text,
    event_name text,
    amount double precision NOT NULL,
    date text,
    is_recurring boolean DEFAULT false,
    pending boolean DEFAULT false,
    anonymous_to_public boolean DEFAULT false,
    recognition_name text,
    donor_name text,
    donor_public_id text,
    donor_profile_image_url text,
    last_scraped timestamptz
);

CREATE TABLE IF NOT EXISTS donor_identities (
    recognition_name text PRIMARY KEY,
    inferred_name text,
    confidence text,
    source text,
    donor_public_id text,
    notes text
);

CREATE TABLE IF NOT EXISTS rides (
    id text PRIMARY KEY,
    name text NOT NULL,
    type text,
    is_signature_ride boolean DEFAULT false,
    status text,
    registration_start text,
    registration_end text,
    ride_weekend_start text,
    ride_weekend_end text,
    last_scraped timestamptz
);

CREATE TABLE IF NOT EXISTS routes (
    id text PRIMARY KEY,
    ride_id text REFERENCES rides(id),
    name text NOT NULL,
    distance double precision,
    duration text,
    fundraising_commitment double precision,
    capacity double precision,
    highest_incline double precision,
    start_date text,
    image_url text,
    starting_city text,
    ending_city text,
    last_scraped timestamptz
);

CREATE TABLE IF NOT EXISTS daily_snapshots (
    snapshot_date text NOT NULL,
    team_id text NOT NULL,
    raised double precision DEFAULT 0,
    goal double precision DEFAULT 0,
    all_time_raised double precision DEFAULT 0,
    members_count integer DEFAULT 0,
    donations_count integer DEFAULT 0,
    total_donated double precision DEFAULT 0,
    signature_riders integer DEFAULT 0,
    gravel_riders integer DEFAULT 0,
    riders_count integer DEFAULT 0,
    challengers_count integer DEFAULT 0,
    volunteers_count integer DEFAULT 0,
    PRIMARY KEY (snapshot_date, team_id)
);

CREATE TABLE IF NOT EXISTS member_routes (
    member_public_id text NOT NULL REFERENCES members(public_id),
    route_id text NOT NULL REFERENCES routes(id),
    route_name text,
    ride_type text,
    distance double precision,
    fundraising_commitment double precision,
    last_scraped timestamptz,
    PRIMARY KEY (member_public_id, route_id)
);

CREATE TABLE IF NOT EXISTS events (
    id text PRIMARY KEY,
    name text,
    year integer,
    total_participants double precision,
    status text,
    fundraising_start text,
    fundraising_end text,
    ride_weekend_start text,
    ride_weekend_end text,
    last_scraped timestamptz
);

CREATE TABLE IF NOT EXISTS kids_snapshots (
    snapshot_date text NOT NULL,
    campaign_id text NOT NULL DEFAULT 'dbpr4x7j9x',
    fundraiser_count integer DEFAULT 0,
    estimated_amount_raised double precision DEFAULT 0,
    monetary_goal double precision DEFAULT 0,
    team_count integer DEFAULT 0,
    last_scraped timestamptz,
    PRIMARY KEY (snapshot_date, campaign_id)
);

CREATE TABLE IF NOT EXISTS org_snapshots (
    snapshot_date text NOT NULL,
    team_id text NOT NULL,
    name text,
    members_count integer DEFAULT 0,
    sub_team_count integer DEFAULT 0,
    raised double precision DEFAULT 0,
    goal double precision DEFAULT 0,
    all_time_raised double precision DEFAULT 0,
    last_scraped timestamptz,
    PRIMARY KEY (snapshot_date, team_id)
);

-- Indexes
CREATE INDEX IF NOT EXISTS idx_member_routes_route ON member_routes(route_id);
CREATE INDEX IF NOT EXISTS idx_member_routes_member ON member_routes(member_public_id);
CREATE INDEX IF NOT EXISTS idx_members_team ON members(team_id);
CREATE INDEX IF NOT EXISTS idx_donations_recipient ON donations(recipient_public_id);
CREATE INDEX IF NOT EXISTS idx_donations_donor ON donations(donor_public_id);
CREATE INDEX IF NOT EXISTS idx_donations_donor_name ON donations(donor_name);
CREATE INDEX IF NOT EXISTS idx_donations_recognition ON donations(recognition_name);
CREATE INDEX IF NOT EXISTS idx_donations_date ON donations(date);
CREATE INDEX IF NOT EXISTS idx_donations_event ON donations(event_name);
CREATE INDEX IF NOT EXISTS idx_snapshots_date ON daily_snapshots(snapshot_date);
