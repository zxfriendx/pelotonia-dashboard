import { useMemo } from 'react';
import { Modal } from '../shared/Modal';
import { useDashboardStore } from '../../store/useDashboardStore';

import { money, shortTeam } from '../../utils/format';
import tableStyles from '../../styles/table.module.css';

function memberType(m: { is_rider: number; is_challenger: number; is_volunteer: number }): string {
  if (m.is_rider) return 'Rider';
  if (m.is_challenger) return 'Challenger';
  if (m.is_volunteer) return 'Volunteer';
  return 'Registered';
}

interface Props {
  teamName: string;
  onClose: () => void;
}

export function TeamMembersModal({ teamName, onClose }: Props) {
  const allMembers = useDashboardStore((s) => s.bundle?.members ?? []);

  const isOpen = !!teamName;

  const filtered = useMemo(
    () =>
      isOpen
        ? allMembers
            .filter((m) => m.team_name === teamName)
            .sort((a, b) => (b.raised || 0) - (a.raised || 0))
        : [],
    [allMembers, teamName, isOpen],
  );

  if (!isOpen) return null;

  return (
    <Modal isOpen={isOpen} onClose={onClose} title={`Members: ${shortTeam(teamName)}`}>
      <table className={tableStyles.table}>
        <thead>
          <tr>
            <th>Name</th>
            <th>Type</th>
            <th style={{ textAlign: 'right' }}>Raised</th>
            <th style={{ textAlign: 'right' }}>Committed</th>
          </tr>
        </thead>
        <tbody>
          {filtered.map((m) => (
            <tr key={m.public_id}>
              <td>{m.name}</td>
              <td>{memberType(m)}</td>
              <td style={{ textAlign: 'right' }}>{money(m.raised)}</td>
              <td style={{ textAlign: 'right' }}>{money(m.committed_amount)}</td>
            </tr>
          ))}
          {filtered.length === 0 && (
            <tr>
              <td colSpan={4} style={{ textAlign: 'center', color: '#888' }}>
                No members found
              </td>
            </tr>
          )}
        </tbody>
      </table>
    </Modal>
  );
}
