"use client";

import { useState } from "react";
import type { Membership } from "@/contracts/types";
import styles from "./TenantSwitcher.module.css";

/**
 * WP-03: the second (and, with LogoutButton, only) deliberate client-side network call in
 * web/src -- see scripts/lib/security-boundaries.mjs's NETWORK_CALL_ALLOWED_FILES. Reads
 * the same non-HttpOnly `campaia_csrf` cookie LogoutButton already reads (double-submit
 * CSRF, unchanged mechanism) and POSTs the chosen tenant_id to POST
 * /session/switch-tenant. The server is the only source of truth for which tenants this
 * is allowed to switch into -- this component only ever offers the memberships the server
 * itself returned via GET /session/memberships (props.memberships), never an
 * arbitrary/typed-in tenant id.
 */
function readCsrfCookie(): string | null {
  const match = document.cookie.match(/(?:^|; )campaia_csrf=([^;]+)/);
  return match ? decodeURIComponent(match[1]) : null;
}

export interface TenantSwitcherProps {
  bffOrigin: string;
  memberships: Membership[];
}

export function TenantSwitcher({ bffOrigin, memberships }: TenantSwitcherProps) {
  const [pending, setPending] = useState(false);
  const [error, setError] = useState<string | null>(null);

  // Nothing to switch to -- WP-03 roadmap wording: "seletor de tenant/unidade (quando o
  // usuario pertence a mais de um)". Rendering nothing here, rather than a disabled
  // control, keeps the shell honest about a single-tenant user having no real choice.
  if (memberships.length <= 1) {
    return null;
  }

  async function handleSwitch(tenantId: string) {
    setPending(true);
    setError(null);
    const csrfToken = readCsrfCookie();
    if (!csrfToken) {
      setError("Sessão sem cookie CSRF válido — recarregue a página.");
      setPending(false);
      return;
    }
    try {
      const response = await fetch(`${bffOrigin}/session/switch-tenant`, {
        method: "POST",
        credentials: "include",
        headers: {
          "content-type": "application/json",
          "x-csrf-token": csrfToken,
        },
        body: JSON.stringify({ tenant_id: tenantId }),
      });
      if (!response.ok) {
        setError("Não foi possível trocar de tenant. Tente novamente.");
        setPending(false);
        return;
      }
      window.location.reload();
    } catch {
      setError("Não foi possível trocar de tenant. Tente novamente.");
      setPending(false);
    }
  }

  return (
    <div className={styles.switcher}>
      <label className={styles.label} htmlFor="campaia-tenant-switcher">
        Tenant ativo
      </label>
      <select
        id="campaia-tenant-switcher"
        className={styles.select}
        disabled={pending}
        value={memberships.find((m) => m.is_active)?.tenant_id ?? ""}
        onChange={(event) => handleSwitch(event.target.value)}
      >
        {memberships.map((m) => (
          <option key={m.tenant_id ?? ""} value={m.tenant_id ?? ""}>
            {m.tenant_id ?? ""} ({(m.roles ?? []).join(", ")})
          </option>
        ))}
      </select>
      {error ? (
        <p role="alert" className={styles.error}>
          {error}
        </p>
      ) : null}
    </div>
  );
}
