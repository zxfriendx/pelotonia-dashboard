import { useMemo } from 'react';
import { Modal } from '../shared/Modal';
import { useDashboardStore } from '../../store/useDashboardStore';

import { moneyFull } from '../../utils/format';
import tableStyles from '../../styles/table.module.css';

interface Props {
  companyName: string;
  onClose: () => void;
}

export function CompanyDetailModal({ companyName, onClose }: Props) {
  const donations = useDashboardStore((s) => s.bundle?.donations ?? []);

  const isOpen = !!companyName;

  const filtered = useMemo(() => {
    if (!isOpen || !companyName) return [];
    return donations
      .filter((d) => (d.recognition_name || '').toLowerCase() === companyName.toLowerCase())
      .sort((a, b) => (b.amount || 0) - (a.amount || 0));
  }, [donations, companyName, isOpen]);

  if (!isOpen) return null;

  return (
    <Modal isOpen={isOpen} onClose={onClose} title={`Donations: ${companyName}`}>
      <table className={tableStyles.table}>
        <thead>
          <tr>
            <th>Date</th>
            <th>Donor Contact</th>
            <th>Recipient</th>
            <th style={{ textAlign: 'right' }}>Amount</th>
          </tr>
        </thead>
        <tbody>
          {filtered.map((d) => (
            <tr key={d.opportunity_id}>
              <td>{d.date ? d.date.substring(0, 10) : '—'}</td>
              <td>
                {d.anonymous_to_public
                  ? <i>{d.recognition_name || 'Anonymous'}</i>
                  : (d.donor_name || d.recognition_name || '—')}
              </td>
              <td>{d.recipient_name || '—'}</td>
              <td style={{ textAlign: 'right' }}>{moneyFull(d.amount)}</td>
            </tr>
          ))}
          {filtered.length === 0 && (
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
