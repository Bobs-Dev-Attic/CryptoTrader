/** Auth context: persists the JWT and exposes login/register/logout. */
import React, {
  createContext,
  useContext,
  useEffect,
  useMemo,
  useState,
} from "react";

import { api, getToken, setRefreshToken, setToken, storeTokens, User } from "./api";

interface AuthState {
  user: User | null;
  loading: boolean;
  login: (email: string, password: string) => Promise<void>;
  register: (email: string, password: string) => Promise<void>;
  logout: () => Promise<void>;
  refresh: () => Promise<void>;
}

const AuthContext = createContext<AuthState | undefined>(undefined);

export function AuthProvider({ children }: { children: React.ReactNode }) {
  const [user, setUser] = useState<User | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    (async () => {
      const token = await getToken();
      if (token) {
        try {
          setUser(await api.me());
        } catch {
          await setToken(null);
        }
      }
      setLoading(false);
    })();
  }, []);

  const login = async (email: string, password: string) => {
    const res = await api.login(email, password);
    await storeTokens(res);
    setUser(res.user);
  };

  const register = async (email: string, password: string) => {
    const res = await api.register(email, password);
    await storeTokens(res);
    setUser(res.user);
  };

  const logout = async () => {
    await setToken(null);
    await setRefreshToken(null);
    setUser(null);
  };

  const refresh = async () => {
    try {
      setUser(await api.me());
    } catch {
      /* ignore */
    }
  };

  const value = useMemo(
    () => ({ user, loading, login, register, logout, refresh }),
    [user, loading]
  );
  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
}

export function useAuth(): AuthState {
  const ctx = useContext(AuthContext);
  if (!ctx) throw new Error("useAuth must be used within AuthProvider");
  return ctx;
}
