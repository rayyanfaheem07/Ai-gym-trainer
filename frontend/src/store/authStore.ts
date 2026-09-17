import { create } from "zustand";
import { User } from "@/types";
import { authApi } from "@/lib/api";
import { getStoredToken, setStoredToken, removeStoredToken, isTokenExpired } from "@/lib/auth";

interface AuthStoreState {
  user: User | null;
  token: string | null;
  isAuthenticated: boolean;
  isLoading: boolean;
  error: string | null;
  initialize: () => Promise<void>;
  login: (email: string, pass: string) => Promise<User>;
  register: (email: string, pass: string, fullName?: string) => Promise<User>;
  logout: () => void;
  clearError: () => void;
}

export const useAuthStore = create<AuthStoreState>((set, get) => ({
  user: null,
  token: null,
  isAuthenticated: false,
  isLoading: true,
  error: null,

  initialize: async () => {
    const token = getStoredToken();
    if (!token || isTokenExpired(token)) {
      removeStoredToken();
      set({ user: null, token: null, isAuthenticated: false, isLoading: false });
      return;
    }

    try {
      set({ token, isLoading: true });
      const user = await authApi.getMe();
      set({ user, token, isAuthenticated: true, isLoading: false, error: null });
    } catch {
      removeStoredToken();
      set({ user: null, token: null, isAuthenticated: false, isLoading: false });
    }
  },

  login: async (email: string, pass: string) => {
    set({ isLoading: true, error: null });
    try {
      const resp = await authApi.login({ email, password: pass });
      setStoredToken(resp.access_token);
      set({
        user: resp.user,
        token: resp.access_token,
        isAuthenticated: true,
        isLoading: false,
        error: null,
      });
      return resp.user;
    } catch (err: any) {
      set({ isLoading: false, error: err.message || "Failed to log in" });
      throw err;
    }
  },

  register: async (email: string, pass: string, fullName?: string) => {
    set({ isLoading: true, error: null });
    try {
      const user = await authApi.register({
        email,
        password: pass,
        full_name: fullName,
      });
      // Automatically log in after registration
      const loginResp = await authApi.login({ email, password: pass });
      setStoredToken(loginResp.access_token);
      set({
        user: loginResp.user,
        token: loginResp.access_token,
        isAuthenticated: true,
        isLoading: false,
        error: null,
      });
      return user;
    } catch (err: any) {
      set({ isLoading: false, error: err.message || "Registration failed" });
      throw err;
    }
  },

  logout: () => {
    removeStoredToken();
    set({
      user: null,
      token: null,
      isAuthenticated: false,
      isLoading: false,
      error: null,
    });
  },

  clearError: () => set({ error: null }),
}));
