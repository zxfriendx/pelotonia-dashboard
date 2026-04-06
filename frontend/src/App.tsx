import { useEffect } from 'react';
import { useDashboardStore } from './store/useDashboardStore';
import { Header } from './components/layout/Header';
import { Footer } from './components/layout/Footer';
import { TabBar } from './components/layout/TabBar';
import { KpiStrip } from './components/layout/KpiStrip';
import { ProgressBar } from './components/layout/ProgressBar';
import { OverviewTab } from './tabs/OverviewTab';
import { TeamsTab } from './tabs/TeamsTab';
import { RoutesTab } from './tabs/RoutesTab';
import { MembersTab } from './tabs/MembersTab';
import { DonorsTab } from './tabs/DonorsTab';
import { CompaniesTab } from './tabs/CompaniesTab';
import { DonationsTab } from './tabs/DonationsTab';
import { InfographicsTab } from './tabs/InfographicsTab/InfographicsTab';
import { ReportTab } from './tabs/ReportTab';
import { KidsTab } from './tabs/KidsTab';
import { LeaderboardTab } from './tabs/LeaderboardTab';
import { ModalRouter } from './components/modals/ModalRouter';
import type { TabId } from './types/constants';

const TAB_COMPONENTS: Record<TabId, React.FC> = {
  overview: OverviewTab,
  teams: TeamsTab,
  routes: RoutesTab,
  members: MembersTab,
  donors: DonorsTab,
  companies: CompaniesTab,
  donations: DonationsTab,
  infographics: InfographicsTab,
  report: ReportTab,
  kids: KidsTab,
  leaderboard: LeaderboardTab,
};

export function App() {
  const { bundle, loading, error, activeTab, loadBundle } = useDashboardStore();

  useEffect(() => {
    loadBundle();
  }, [loadBundle]);

  if (loading && !bundle) {
    return (
      <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'center', height: '100vh', color: '#888' }}>
        Loading dashboard data…
      </div>
    );
  }

  if (error && !bundle) {
    return (
      <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'center', height: '100vh', color: '#c00' }}>
        Failed to load data: {error}
      </div>
    );
  }

  const ActiveTab = TAB_COMPONENTS[activeTab];

  return (
    <>
      <Header />
      <KpiStrip />
      <ProgressBar />
      <TabBar />
      <main style={{ maxWidth: 1200, margin: '0 auto', padding: '20px 16px' }}>
        {ActiveTab && <ActiveTab />}
      </main>
      <Footer />
      <ModalRouter />
    </>
  );
}
