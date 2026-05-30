import { create } from "zustand";

interface User {
  id: string;
  email: string;
  role: string;
  two_fa_enabled: boolean;
  is_active: boolean;
}

interface AuthState {
  user: User | null;
  setUser: (user: User | null) => void;
  clearUser: () => void;
}

export const useAuthStore = create<AuthState>((set) => ({
  user: null,
  setUser: (user) => set({ user }),
  clearUser: () => set({ user: null }),
}));
