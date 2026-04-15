import { useMemo } from 'react';
import { Modal } from '../shared/Modal';
import { useDashboardStore } from '../../store/useDashboardStore';

import { money, shortTeam } from '../../utils/format';
import tableStyles from '../../styles/table.module.css';

interface RecipientGroup {
  name: string;
  team: string;
  total: number;
  count: number;
}

interface Props {
  donorName: string;
  onClose: () => void;
}

export function DonorRecipientsModal({ donorName, onClose }: Props) {
  const donations = useDashboardStore((s) => s.bundle?.donations ?? []);

  const isOpen = !!donorName;

  const groups = useMemo(() => {
    if (!isOpen || !donorName) return [];
    const donorDons = donations.filter((d) => {
      const name = (d.donor_name && d.donor_name.trim())
        ? d.donor_name
        : (d.recognition_name && d.recognition_name.trim() ? d.recognition_name : 'Anonymous');
      return name === donorName;
    });
    const map = new Map<string, RecipientGroup>();
    donorDons.forEach((d) => {
      const key = d.recipient_public_id || d.recipient_name || 'Unknown';
      const existing = map.get(key);
      if (existing) {
        existing.total += d.amount || 0;
        existing.count += 1;
      } else {
        map.set(key, {
          name: d.recipient_name || '—',
          team: d.team_name || '',
          total: d.amount || 0,
          count: 1,
        });
      }
    });
    return [...map.values()].sort((a, b) => b.total - a.total);
  }, [donations, donorName, isOpen]);

  if (!isOpen) return null;

  return (
    <Modal isOpen={isOpen} onClose={onClose} title={`Donations by ${donorName}`}>
      <table className={tableStyles.table}>
        <thead>
          <tr>
            <th>Recipient</th>
            <th>Sub-Team</th>
            <th style={{ textAlign: 'right' }}>Total</th>
            <th style={{ textAlign: 'right' }}># Donations</th>
          </tr>
        </thead>
        <tbody>
          {groups.map((g, i) => (
            <tr key={i}>
              <td>{g.name}</td>
              <td>{shortTeam(g.team)}</td>
              <td style={{ textAlign: 'right' }}>{money(g.total)}</td>
              <td style={{ textAlign: 'right' }}>{g.count}</td>
            </tr>
          ))}
          {groups.length === 0 && (
            <tr>
              <td colSpan={4} style={{ textAlign: 'center', color: '#888' }}>
                No donations found
              </td>
            </tr>
          )}
        </tbody>
      </table>
    </Modal>
  );
}
