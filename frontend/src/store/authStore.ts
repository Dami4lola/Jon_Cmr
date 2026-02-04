import { create } from 'zustand';
import { persist } from 'zustand/middleware';
import type { User } from '../types';

interface AuthState {
  user: User | null;
  token: string | null;
  isAuthenticated: boolean;

  // Computed-like getters
  isManager: () => boolean;
  isAdmin: () => boolean;
  hasRole: (role: string) => boolean;

  // Actions
  login: (token: string, user: User) => void;
  logout: () => void;
  updateUser: (user: User) => void;
}

export const useAuthStore = create<AuthState>()(
  persist(
    (set, get) => ({
      user: null,
      token: null,
      isAuthenticated: false,

      isManager: () => {
        const { user } = get();
        if (!user) return false;
        return user.roles.includes('manager') || user.roles.includes('admin');
      },

      isAdmin: () => {
        const { user } = get();
        if (!user) return false;
        return user.roles.includes('admin');
      },

      hasRole: (role: string) => {
        const { user } = get();
        if (!user) return false;
        return user.roles.includes(role);
      },

      login: (token, user) => {
        localStorage.setItem('access_token', token);
        set({ token, user, isAuthenticated: true });
      },

      logout: () => {
        localStorage.removeItem('access_token');
        set({ token: null, user: null, isAuthenticated: false });
      },

      updateUser: (user) => {
        set({ user });
      },
    }),
    {
      name: 'auth-storage',
      partialize: (state) => ({
        user: state.user,
        token: state.token,
        isAuthenticated: state.isAuthenticated,
      }),
    }
  )
);
