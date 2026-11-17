import { createContext, useContext, useMemo, useState, type ReactNode } from "react";
import type { AuthResponse, AuthUser } from "../api/types";

const KEY = "trustify.session";

interface StoredSession {
  accessToken: string;
  sessionId: string;
  user: AuthUser;
}

interface AuthState {
  session: StoredSession | null;
  setSession: (response: AuthResponse) => void;
  clear: () => void;
}

const AuthContext = createContext<AuthState | null>(null);

function read(): StoredSession | null {
  const raw = localStorage.getItem(KEY);
  if (!raw) return null;
  try {
    return JSON.parse(raw) as StoredSession;
  } catch {
    return null;
  }
}

export function AuthProvider({ children }: { children: ReactNode }) {
  const [session, setStored] = useState<StoredSession | null>(() => read());
  const value = useMemo<AuthState>(
    () => ({
      session,
      setSession: (response) => {
        const next = { accessToken: response.access_token, sessionId: response.session_id, user: response.user };
        localStorage.setItem(KEY, JSON.stringify(next));
        setStored(next);
      },
      clear: () => {
        localStorage.removeItem(KEY);
        setStored(null);
      },
    }),
    [session],
  );
  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
}

export function useAuth() {
  const value = useContext(AuthContext);
  if (!value) throw new Error("AuthProvider is missing");
  return value;
}

export function currentToken() {
  return read()?.accessToken ?? null;
}

export function currentSessionId() {
  return read()?.sessionId ?? null;
}
