import { create } from 'zustand';
import type { BundleData, ModalState } from '../types';
import type { TabId } from '../types/constants';
import { fetchBundleCore, fetchBundleRest } from '../api/client';

// Heavy datasets arrive in a second wave (/api/bundle/rest). Seed them empty so
// components reading e.g. bundle.donations don't crash before that wave resolves.
const EMPTY_REST: Pick<
  BundleData,
  'members' | 'donations' | 'donors' | 'companies' | 'orgSnapshots' | 'commitmentGap'
> = { members: [], donations: [], donors: [], companies: [], orgSnapshots: [], commitmentGap: null };

interface DashboardStore {
  bundle: BundleData | null;
  loading: boolean;
  error: string | null;
  restLoaded: boolean;
  restError: string | null;
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
  restLoaded: false,
  restError: null,
  activeTab: 'overview',
  modal: null,
  memberHighlight: null,

  loadBundle: async () => {
    set({ loading: true, error: null, restLoaded: false, restError: null });
    try {
      // First wave: render as soon as the small core payload lands.
      const core = await fetchBundleCore();
      set({ bundle: { ...EMPTY_REST, ...core } as BundleData, loading: false });

      // Second wave: heavy datasets in the background — does not block first paint.
      fetchBundleRest()
        .then((rest) =>
          set((s) => (s.bundle ? { bundle: { ...s.bundle, ...rest }, restLoaded: true } : {})),
        )
        .catch((e) => set({ restError: (e as Error).message }));
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
