"use client";

import {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useMemo,
  useState,
  type ReactNode,
} from "react";
import {
  ApiClientError,
  api,
  getCsrfToken,
  setCsrfToken,
  setUnauthenticatedListener,
} from "../lib/api/client";
import type { Me } from "../contracts/types";
import type { SessionUser } from "../types/session";

export type AuthStatus = "bootstrapping" | "authenticated" | "unauthenticated" | "error";

export interface AuthContextValue {
  status: AuthStatus;
  /** Resumo da sessao (GET/POST /auth/session) -- fonte do csrf_token. */
  session: SessionUser | null;
  /** Fonte de verdade Web para roles/permissions (GET /me, Etapa 2 secao 19). */
  me: Me | null;
  error: string | null;
  login: (idToken: string) => Promise<void>;
  logout: () => Promise<void>;
  /**
   * Troca o vinculo (tenant/unidade) ativo da sessao para outro vinculo real da mesma
   * identidade (WP-03, `POST /auth/session/switch`) -- nunca decide sozinho qual tenant
   * e valido, so repassa o `user_id` escolhido pelo usuario entre os que
   * `GET /me/memberships` ja devolveu; o backend e' quem valida e recusa fail-closed.
   */
  switchMembership: (targetUserId: string) => Promise<void>;
}

const AuthContext = createContext<AuthContextValue | null>(null);

async function fetchSessionAndMe(): Promise<{ session: SessionUser; me: Me }> {
  const session = await api.get<SessionUser>("/auth/session");
  setCsrfToken(session.csrf_token);
  const me = await api.get<Me>("/me");
  return { session, me };
}

export function AuthProvider({ children }: { children: ReactNode }) {
  const [status, setStatus] = useState<AuthStatus>("bootstrapping");
  const [session, setSession] = useState<SessionUser | null>(null);
  const [me, setMe] = useState<Me | null>(null);
  const [error, setError] = useState<string | null>(null);

  const clearAuth = useCallback(() => {
    setCsrfToken(null);
    setSession(null);
    setMe(null);
  }, []);

  // Qualquer chamada da API que receba 401, em qualquer lugar do app, limpa o
  // AuthContext e marca unauthenticated -- 401 nunca e' tratado como 403 (secao 18).
  useEffect(() => {
    setUnauthenticatedListener(() => {
      clearAuth();
      setStatus("unauthenticated");
    });
    return () => setUnauthenticatedListener(null);
  }, [clearAuth]);

  // Bootstrap: reobtem csrf_token via GET /auth/session apos reload -- nunca
  // localStorage (secao 13).
  useEffect(() => {
    let active = true;
    (async () => {
      try {
        const result = await fetchSessionAndMe();
        if (!active) return;
        setSession(result.session);
        setMe(result.me);
        setStatus("authenticated");
      } catch (err) {
        if (!active) return;
        if (err instanceof ApiClientError && err.status === 401) {
          clearAuth();
          setStatus("unauthenticated");
          return;
        }
        clearAuth();
        setError(err instanceof Error ? err.message : "Falha ao verificar sessao.");
        setStatus("error");
      }
    })();
    return () => {
      active = false;
    };
  }, [clearAuth]);

  const login = useCallback(async (idToken: string) => {
    setError(null);
    // Login nao e' uma mutacao autenticada por sessao existente (nao ha csrf_token
    // ainda) -- POST /auth/session e' protegido pelo backend via allowlist de
    // Origin/Referer (login-CSRF, backend/api/session.py), nao por X-CSRF-Token.
    const response = await fetch("/api/campaia/auth/session", {
      method: "POST",
      credentials: "include",
      headers: { "content-type": "application/json" },
      body: JSON.stringify({ id_token: idToken }),
    });
    const body = await response.json().catch(() => null);
    if (!response.ok) {
      throw new ApiClientError(response.status, body);
    }
    const sessionUser = body as SessionUser;
    setCsrfToken(sessionUser.csrf_token);
    setSession(sessionUser);
    const meResponse = await api.get<Me>("/me");
    setMe(meResponse);
    setStatus("authenticated");
  }, []);

  const logout = useCallback(async () => {
    try {
      // DELETE /auth/session real (backend/api/routes_auth.py::logout) nao exige
      // X-CSRF-Token -- por isso NAO usa o api.delete() generico (que bloqueia
      // fail-closed qualquer mutacao sem CSRF em memoria). Logout precisa funcionar
      // mesmo quando a sessao ja esta invalida/expirada e nao ha csrf_token algum
      // (secao 15). Ainda assim, disciplina consistente: envia o header quando
      // disponivel.
      const headers: Record<string, string> = {};
      const token = getCsrfToken();
      if (token) headers["x-csrf-token"] = token;
      await fetch("/api/campaia/auth/session", {
        method: "DELETE",
        credentials: "include",
        headers,
      });
    } catch {
      // Falha de rede/sessao ja invalida: seguimos limpando o estado local mesmo
      // assim -- nunca deixamos o usuario "logado" na UI por causa de um logout
      // que falhou no servidor.
    } finally {
      clearAuth();
      setStatus("unauthenticated");
    }
  }, [clearAuth]);

  const switchMembership = useCallback(async (targetUserId: string) => {
    setError(null);
    const sessionUser = await api.post<SessionUser>("/auth/session/switch", {
      user_id: targetUserId,
    });
    setCsrfToken(sessionUser.csrf_token);
    setSession(sessionUser);
    const meResponse = await api.get<Me>("/me");
    setMe(meResponse);
  }, []);

  const value = useMemo<AuthContextValue>(
    () => ({ status, session, me, error, login, logout, switchMembership }),
    [status, session, me, error, login, logout, switchMembership],
  );

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
}

export function useAuth(): AuthContextValue {
  const ctx = useContext(AuthContext);
  if (!ctx) {
    throw new Error("useAuth() precisa estar dentro de <AuthProvider>.");
  }
  return ctx;
}
