import { useDashboardStore } from '../../store/useDashboardStore';
import { RouteMembersModal } from './RouteMembersModal';
import { MemberDonorsModal } from './MemberDonorsModal';
import { DonorRecipientsModal } from './DonorRecipientsModal';
import { TeamMembersModal } from './TeamMembersModal';
import { CompanyDetailModal } from './CompanyDetailModal';

export function ModalRouter() {
  const { modal, closeModal } = useDashboardStore();

  if (!modal) return null;

  switch (modal.type) {
    case 'routeMembers':
      return (
        <RouteMembersModal
          routeId={modal.data.routeId as string}
          routeName={modal.data.routeName as string}
          onClose={closeModal}
        />
      );
    case 'memberDonors':
      return (
        <MemberDonorsModal
          publicId={modal.data.publicId as string}
          name={modal.data.name as string}
          onClose={closeModal}
        />
      );
    case 'donorRecipients':
      return (
        <DonorRecipientsModal
          donorName={modal.data.donorName as string}
          onClose={closeModal}
        />
      );
    case 'teamMembers':
      return (
        <TeamMembersModal
          teamName={modal.data.teamName as string}
          onClose={closeModal}
        />
      );
    case 'companyDetail':
      return (
        <CompanyDetailModal
          companyName={modal.data.companyName as string}
          onClose={closeModal}
        />
      );
    default:
      return null;
  }
}
