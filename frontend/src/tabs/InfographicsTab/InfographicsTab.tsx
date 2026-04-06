import { useState, useMemo } from 'react';
import { useDashboardStore } from '../../store/useDashboardStore';
import { shortTeam, moneyShort } from '../../utils/format';
import { computeSmartTargets } from '../../utils/targets';
import {
  REGISTRATION_OPEN,
  RIDE_WEEKEND,
  FUNDRAISING_CLOSE,
} from '../../types/constants';
import { ThermoCard } from './ThermoCard';
import { SummaryCards } from './SummaryCards';
import { GoalsTable } from './GoalsTable';
import styles from '../../styles/infographic.module.css';

export function InfographicsTab() {
  const bundle = useDashboardStore((s) => s.bundle);
  const [selectedTeam, setSelectedTeam] = useState('__all__');

  const teamOptions = useMemo(() => {
    if (!bundle) return [];
    return bundle.teamBreakdown.map((t) => t.name);
  }, [bundle]);

  const targets = useMemo(
    () => (bundle ? computeSmartTargets(bundle) : {}),
    [bundle],
  );

  const {
    fundsRaised, fundsGoal, riders, challengers, volunteers, survivors, avgDonation,
  } = useMemo(() => {
    if (!bundle) {
      return { fundsRaised: 0, fundsGoal: 0, riders: 0, challengers: 0, volunteers: 0, survivors: 0, avgDonation: 0 };
    }
    const { overview, teamBreakdown, teams, donations } = bundle;

    if (selectedTeam === '__all__') {
      return {
        fundsRaised: overview.raised,
        fundsGoal: overview.goal,
        riders: overview.riders || 0,
        challengers: overview.challengers || 0,
        volunteers: overview.volunteers || 0,
        survivors: overview.cancer_survivors,
        avgDonation: overview.donations_count > 0 ? overview.total_donated / overview.donations_count : 0,
      };
    }

    const team = teamBreakdown.find((t) => t.name === selectedTeam);
    if (!team) {
      return { fundsRaised: 0, fundsGoal: 0, riders: 0, challengers: 0, volunteers: 0, survivors: 0, avgDonation: 0 };
    }

    const teamData = teams.find((t) => t.name === selectedTeam);
    const teamDons = donations.filter((d) => d.team_name === selectedTeam);
    const teamDonTotal = teamDons.reduce((s, d) => s + (d.amount || 0), 0);

    return {
      fundsRaised: team.total_raised,
      fundsGoal: teamData ? teamData.goal : 0,
      riders: team.riders,
      challengers: team.challengers,
      volunteers: team.volunteers,
      survivors: team.survivors,
      avgDonation: teamDons.length > 0 ? teamDonTotal / teamDons.length : 0,
    };
  }, [bundle, selectedTeam]);

  const tgt = targets[selectedTeam] || targets['__all__'] || { funds: null, riders: 2100, challengers: 547, volunteers: 1500 };
  const fundsTarget = tgt.funds || fundsGoal;

  // Timeline calculations
  const now = new Date();
  const regDay = Math.max(1, Math.ceil((now.getTime() - REGISTRATION_OPEN.getTime()) / 86400000) + 1);
  const daysToRide = Math.max(0, Math.ceil((RIDE_WEEKEND.getTime() - now.getTime()) / 86400000));
  const daysToClose = Math.max(0, Math.ceil((FUNDRAISING_CLOSE.getTime() - now.getTime()) / 86400000));
  const fundsDaysTotal = Math.ceil((FUNDRAISING_CLOSE.getTime() - REGISTRATION_OPEN.getTime()) / 86400000);
  const rideDaysTotal = Math.ceil((RIDE_WEEKEND.getTime() - REGISTRATION_OPEN.getTime()) / 86400000);
  const fundsExpectedPct = (regDay / fundsDaysTotal) * 100;
  const rideExpectedPct = (regDay / rideDaysTotal) * 100;

  // Build stat chips per metric
  function buildChips(key: 'funds' | 'riders' | 'challengers' | 'volunteers') {
    if (!bundle) return [];
    const { overview, teamBreakdown } = bundle;

    if (selectedTeam === '__all__') {
      if (key === 'funds') {
        return [
          { v: moneyShort(overview.total_committed || 0), l: 'Committed' },
          { v: moneyShort(overview.hr_committed || 0), l: 'High Rollers' },
          { v: moneyShort(overview.std_committed || 0), l: 'Standard' },
        ];
      }
      const sorted = [...teamBreakdown].sort((a, b) => {
        if (key === 'riders') return (b.riders || 0) - (a.riders || 0);
        if (key === 'challengers') return (b.challengers || 0) - (a.challengers || 0);
        return (b.volunteers || 0) - (a.volunteers || 0);
      });
      return sorted.slice(0, 3).map((t) => {
        const short = shortTeam(t.name);
        const abbr = short.length > 12 ? short.substring(0, 11) + '\u2026' : short;
        let val: string;
        if (key === 'riders') val = (t.riders || 0).toLocaleString();
        else if (key === 'challengers') val = (t.challengers || 0).toLocaleString();
        else val = (t.volunteers || 0).toLocaleString();
        return { v: val, l: abbr };
      });
    }

    if (key === 'funds') {
      const team = teamBreakdown.find((t) => t.name === selectedTeam);
      return [
        { v: moneyShort(team ? team.total_committed || 0 : 0), l: 'Committed' },
        { v: moneyShort(team ? team.hr_committed || 0 : 0), l: 'High Rollers' },
        { v: moneyShort(team ? team.std_committed || 0 : 0), l: 'Standard' },
      ];
    }
    return [
      { v: 'Day ' + regDay, l: 'Campaign' },
      { v: daysToRide + 'd', l: 'To Ride' },
      { v: (riders + challengers + volunteers).toLocaleString(), l: 'Total' },
    ];
  }

  if (!bundle) return null;

  const thermos = [
    {
      key: 'funds' as const,
      label: 'Funds Raised',
      current: fundsRaised,
      goal: fundsTarget,
      format: moneyShort,
      deadline: 'Fundraising closes Oct 15',
      daysTotal: fundsDaysTotal,
      daysLeft: daysToClose,
      expected: fundsExpectedPct,
    },
    {
      key: 'riders' as const,
      label: 'Riders',
      current: riders,
      goal: tgt.riders,
      format: (v: number) => v.toLocaleString(),
      deadline: '',
      daysTotal: rideDaysTotal,
      daysLeft: daysToRide,
      expected: rideExpectedPct,
    },
    {
      key: 'challengers' as const,
      label: 'Challengers',
      current: challengers,
      goal: tgt.challengers,
      format: (v: number) => v.toLocaleString(),
      deadline: '',
      daysTotal: rideDaysTotal,
      daysLeft: daysToRide,
      expected: rideExpectedPct,
    },
    {
      key: 'volunteers' as const,
      label: 'Volunteers',
      current: volunteers,
      goal: tgt.volunteers,
      format: (v: number) => v.toLocaleString(),
      deadline: '',
      daysTotal: rideDaysTotal,
      daysLeft: daysToRide,
      expected: rideExpectedPct,
    },
  ];

  return (
    <div>
      <div className={styles.infographicControls}>
        <select
          className={styles.infographicSelect}
          value={selectedTeam}
          onChange={(e) => setSelectedTeam(e.target.value)}
        >
          <option value="__all__">All Teams</option>
          {teamOptions.map((name) => (
            <option key={name} value={name}>
              {shortTeam(name)}
            </option>
          ))}
        </select>
      </div>

      <div className={styles.thermoGrid}>
        {thermos.map((t) => (
          <ThermoCard
            key={t.key}
            label={t.label}
            current={t.current}
            goal={t.goal}
            format={t.format}
            chips={buildChips(t.key)}
            daysLeft={t.daysLeft}
            expected={t.expected}
            deadline={t.deadline || undefined}
          />
        ))}
      </div>

      <SummaryCards
        survivors={survivors}
        highRollers={bundle.overview.high_rollers}
        avgDonation={avgDonation}
      />

      <GoalsTable />
    </div>
  );
}
