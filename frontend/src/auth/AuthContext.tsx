import {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useMemo,
  useState,
  type ReactNode,
} from 'react';
import { api, setCsrfToken } from '../api/client';
import type { User } from '../api/types';

interface AuthState {
  user: User | null;
  loading: boolean;
  login: (username: string, password: string) => Promise<void>;
  logout: () => Promise<void>;
  refresh: () => Promise<void>;
  changePassword: (current: string, next: string) => Promise<void>;
  changeUsername: (username: string, currentPassword: string) => Promise<void>;
}

const AuthContext = createContext<AuthState | null>(null);

export function AuthProvider({
  children,
  initialUser,
}: {
  children: ReactNode;
  /** Solo para pruebas: evita el arranque automático de sesión. */
  initialUser?: User | null;
}) {
  const [user, setUser] = useState<User | null>(initialUser ?? null);
  const [loading, setLoading] = useState(initialUser === undefined);

  useEffect(() => {
    if (initialUser !== undefined) return;
    let active = true;
    api.me()
      .then((current) => {
        if (active) setUser(current);
      })
      .catch(() => {
        if (active) setUser(null);
      })
      .finally(() => {
        if (active) setLoading(false);
      });
    return () => {
      active = false;
    };
  }, [initialUser]);

  const login = useCallback(async (username: string, password: string) => {
    const response = await api.login(username, password);
    setCsrfToken(response.csrf_token);
    setUser(response.user);
    setLoading(false);
  }, []);

  const logout = useCallback(async () => {
    try {
      await api.logout();
    } catch {
      // Si la sesión ya caducó, se limpia igualmente el estado local.
    } finally {
      setCsrfToken(null);
      setUser(null);
    }
  }, []);

  const refresh = useCallback(async () => {
    setUser(await api.me());
  }, []);

  const changePassword = useCallback(async (current: string, next: string) => {
    const response = await api.changePassword(current, next);
    setCsrfToken(response.csrf_token);
    setUser(response.user);
  }, []);

  const changeUsername = useCallback(async (username: string, currentPassword: string) => {
    setUser(await api.changeUsername(username, currentPassword));
  }, []);

  const value = useMemo(
    () => ({ user, loading, login, logout, refresh, changePassword, changeUsername }),
    [user, loading, login, logout, refresh, changePassword, changeUsername],
  );
  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
}

export function useAuth(): AuthState {
  const context = useContext(AuthContext);
  if (!context) {
    throw new Error('useAuth debe usarse dentro de AuthProvider');
  }
  return context;
}
