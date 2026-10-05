import { create } from "zustand";
import { clearClientToken, getClientToken, setClientToken } from "../lib/auth";

interface AuthState {
  token: string | null;
  isAuthenticated: boolean;
  isHydrated: boolean;
  hydrate: () => void;
  login: (token: string) => void;
  logout: () => void;
}

const useAuth = create<AuthState>((set) => ({
  token: null,
  isAuthenticated: false,
  isHydrated: false,

  hydrate: () => {
    const token = getClientToken();
    set({ token, isAuthenticated: Boolean(token), isHydrated: true });
  },

  login: (token: string) => {
    setClientToken(token);
    set({ token, isAuthenticated: true, isHydrated: true });
  },

  logout: () => {
    clearClientToken();
    set({ token: null, isAuthenticated: false, isHydrated: true });
  },
}));

export default useAuth;