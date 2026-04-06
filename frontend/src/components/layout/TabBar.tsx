import { useRef, useCallback } from 'react';
import styles from '../../styles/tabs.module.css';
import { useDashboardStore } from '../../store/useDashboardStore';
import type { TabId } from '../../types/constants';
import { TAB_IDS } from '../../types/constants';

const TAB_LABELS: Record<TabId, string> = {
  overview: 'Overview',
  teams: 'Teams',
  routes: 'Routes & Events',
  members: 'Members',
  donors: 'Donors',
  companies: 'Companies',
  donations: 'Donations',
  infographics: 'Infographics',
  report: 'Daily Report',
  kids: 'Pelotonia Kids',
  leaderboard: 'Leaderboard',
};

export function TabBar() {
  const activeTab = useDashboardStore((s) => s.activeTab);
  const setActiveTab = useDashboardStore((s) => s.setActiveTab);
  const tabsRef = useRef<HTMLDivElement>(null);

  const handleClick = useCallback(
    (tab: TabId, el: HTMLButtonElement) => {
      setActiveTab(tab);
      el.scrollIntoView({ behavior: 'smooth', inline: 'center', block: 'nearest' });
    },
    [setActiveTab],
  );

  return (
    <div className={styles.tabsWrap}>
      <div className={styles.tabs} ref={tabsRef}>
        {TAB_IDS.map((id) => (
          <button
            key={id}
            className={`${styles.tab} ${activeTab === id ? styles.active : ''}`}
            onClick={(e) => handleClick(id, e.currentTarget)}
          >
            {TAB_LABELS[id]}
          </button>
        ))}
      </div>
    </div>
  );
}
