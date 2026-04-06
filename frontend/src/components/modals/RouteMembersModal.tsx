import { useEffect, useState } from 'react';
import { Modal } from '../shared/Modal';
import { fetchRouteMembers } from '../../api/client';
import { money } from '../../utils/format';
import type { RouteMember } from '../../types';
import tableStyles from '../../styles/table.module.css';

interface Props {
  routeId: string;
  routeName: string;
  onClose: () => void;
}

export function RouteMembersModal({ routeId, routeName, onClose }: Props) {
  const [members, setMembers] = useState<RouteMember[]>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const isOpen = !!routeId;

  useEffect(() => {
    if (!isOpen || !routeId) return;
    setLoading(true);
    setError(null);
    fetchRouteMembers(routeId)
      .then(setMembers)
      .catch((e) => setError((e as Error).message))
      .finally(() => setLoading(false));
  }, [isOpen, routeId]);

  if (!isOpen) return null;

  return (
    <Modal isOpen={isOpen} onClose={onClose} title={routeName}>
      {loading && <div style={{ textAlign: 'center', padding: 24, color: '#888' }}>Loading...</div>}
      {error && <div style={{ textAlign: 'center', padding: 24, color: '#e74c3c' }}>{error}</div>}
      {!loading && !error && (
        <table className={tableStyles.table}>
          <thead>
            <tr>
              <th>#</th>
              <th>Name</th>
              <th style={{ textAlign: 'right' }}>Years</th>
              <th style={{ textAlign: 'right' }}>Raised</th>
              <th style={{ textAlign: 'right' }}>Committed</th>
            </tr>
          </thead>
          <tbody>
            {members.map((m, i) => (
              <tr key={m.public_id}>
                <td>{i + 1}</td>
                <td>{m.name}</td>
                <td style={{ textAlign: 'right' }}>{m.years || '—'}</td>
                <td style={{ textAlign: 'right' }}>{money(m.raised)}</td>
                <td style={{ textAlign: 'right' }}>{money(m.committed_amount)}</td>
              </tr>
            ))}
            {members.length === 0 && (
              <tr>
                <td colSpan={5} style={{ textAlign: 'center', color: '#888' }}>
                  No members found
                </td>
              </tr>
            )}
          </tbody>
        </table>
      )}
    </Modal>
  );
}
