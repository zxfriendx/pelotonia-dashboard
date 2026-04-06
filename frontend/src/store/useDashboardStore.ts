import { create } from 'zustand';
import type { BundleData, ModalState } from '../types';
import type { TabId } from '../types/constants';
import { fetchBundle } from '../api/client';

interface DashboardStore {
  bundle: BundleData | null;
  loading: boolean;
  error: string | null;
  activeTab: TabId;
  modal: ModalState | null;
  memberHighlight: { publicId: string; name: string } | null;

  loadBundle: () => Promise<void>;
  setActiveTab: (tab: TabId) => void;
  openModal: (modal: ModalState) => void;
  closeModal: () => void;
  navigateToMember: (publicId: string, name: string) => void;
  clearMemberHighlight: () => void;
}

export const useDashboardStore = create<DashboardStore>((set) => ({
  bundle: null,
  loading: false,
  error: null,
  activeTab: 'overview',
  modal: null,
  memberHighlight: null,

  loadBundle: async () => {
    set({ loading: true, error: null });
    try {
      const bundle = await fetchBundle();
      set({ bundle, loading: false });
    } catch (e) {
      set({ error: (e as Error).message, loading: false });
    }
  },

  setActiveTab: (tab) => set({ activeTab: tab }),

  openModal: (modal) => set({ modal }),

  closeModal: () => set({ modal: null }),

  navigateToMember: (publicId, name) => {
    set({
      activeTab: 'members',
      memberHighlight: { publicId, name },
    });
  },

  clearMemberHighlight: () => set({ memberHighlight: null }),
}));
