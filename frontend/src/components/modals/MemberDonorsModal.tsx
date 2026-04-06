import { useMemo } from 'react';
import { Modal } from '../shared/Modal';
import { useDashboardStore } from '../../store/useDashboardStore';
import { money, moneyFull } from '../../utils/format';
import tableStyles from '../../styles/table.module.css';

interface Props {
  publicId: string;
  name: string;
  onClose: () => void;
}

export function MemberDonorsModal({ publicId, name, onClose }: Props) {
  const donations = useDashboardStore((s) => s.bundle?.donations ?? []);

  const isOpen = !!publicId;
  const recipientId = publicId;
  const memberName = name || 'Member Donations';

  const filtered = useMemo(
    () =>
      isOpen
        ? donations.filter((d) => d.recipient_public_id === recipientId)
        : [],
    [donations, recipientId, isOpen],
  );

  const total = useMemo(
    () => filtered.reduce((s, d) => s + (d.amount || 0), 0),
    [filtered],
  );

  if (!isOpen) return null;

  return (
    <Modal isOpen={isOpen} onClose={onClose} title={`Donations to ${memberName}`}>
      <table className={tableStyles.table}>
        <thead>
          <tr>
            <th>Date</th>
            <th>Donor</th>
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
              <td style={{ textAlign: 'right' }}>{moneyFull(d.amount)}</td>
            </tr>
          ))}
          {filtered.length === 0 && (
            <tr>
              <td colSpan={3} style={{ textAlign: 'center', color: '#888' }}>
                No donation records
              </td>
            </tr>
          )}
        </tbody>
        {filtered.length > 0 && (
          <tfoot>
            <tr className={tableStyles.totalsRow}>
              <td colSpan={2} style={{ fontWeight: 700 }}>Total</td>
              <td style={{ textAlign: 'right', fontWeight: 700 }}>{money(total)}</td>
            </tr>
          </tfoot>
        )}
      </table>
    </Modal>
  );
}
