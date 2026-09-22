"use client";

import { useState } from "react";
import { Button } from "@/components/Button";

/**
 * WP-02: the one deliberate client-side network call in web/src (see
 * scripts/lib/security-boundaries.mjs's NETWORK_CALL_ALLOWED_FILES). Logout is
 * CSRF-protected via the double-submit pattern: the `campaia_csrf` cookie is
 * intentionally NOT HttpOnly so this component can read it and echo it back as a header
 * -- an attacker's cross-site script cannot read it (same-origin policy), so a forged
 * logout request predictably fails the BFF's CSRF check.
 */
function readCsrfCookie(): string | null {
  const match = document.cookie.match(/(?:^|; )campaia_csrf=([^;]+)/);
  return match ? decodeURIComponent(match[1]) : null;
}

export interface LogoutButtonProps {
  bffOrigin: string;
}

export function LogoutButton({ bffOrigin }: LogoutButtonProps) {
  const [pending, setPending] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function handleLogout() {
    setPending(true);
    setError(null);
    const csrfToken = readCsrfCookie();
    if (!csrfToken) {
      setError("Sessão sem cookie CSRF válido — recarregue a página.");
      setPending(false);
      return;
    }
    try {
      const response = await fetch(`${bffOrigin}/auth/logout`, {
        method: "POST",
        credentials: "include",
        headers: { "x-csrf-token": csrfToken },
      });
      if (!response.ok && response.status !== 0) {
        setError("Não foi possível encerrar a sessão. Tente novamente.");
        setPending(false);
        return;
      }
      window.location.reload();
    } catch {
      setError("Não foi possível encerrar a sessão. Tente novamente.");
      setPending(false);
    }
  }

  return (
    <div>
      <Button variant="secondary" onClick={handleLogout} disabled={pending}>
        {pending ? "Saindo..." : "Sair"}
      </Button>
      {error ? <p role="alert">{error}</p> : null}
    </div>
  );
}
