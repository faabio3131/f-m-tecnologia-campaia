"use client";

import { useState } from "react";
import { Button } from "@/components/Button";
import type { BrandProfile } from "@/contracts/types";
import styles from "./BrandKitForm.module.css";

/**
 * WP-04: fourth deliberate client-side network call in web/src -- see
 * scripts/lib/security-boundaries.mjs's NETWORK_CALL_ALLOWED_FILES. Same CSRF discipline
 * as LogoutButton/TenantSwitcher (double-submit cookie). POST /brand-profiles also requires
 * an Idempotency-Key (backend/api/deps.py require_idempotency_key) -- generated fresh per
 * submit with the Web Crypto API already available in every browser this app targets,
 * never reused across submits (a reused key would make a genuinely new Brand Kit look like
 * a replay of the previous one).
 */
function readCsrfCookie(): string | null {
  const match = document.cookie.match(/(?:^|; )campaia_csrf=([^;]+)/);
  return match ? decodeURIComponent(match[1]) : null;
}

function splitLines(value: string): string[] {
  return value
    .split("\n")
    .map((line) => line.trim())
    .filter((line) => line.length > 0);
}

function splitCommas(value: string): string[] {
  return value
    .split(",")
    .map((entry) => entry.trim())
    .filter((entry) => entry.length > 0);
}

export interface BrandKitFormProps {
  bffOrigin: string;
  existing: BrandProfile[];
}

export function BrandKitForm({ bffOrigin, existing }: BrandKitFormProps) {
  const [pending, setPending] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function handleSubmit(event: React.FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setPending(true);
    setError(null);

    const csrfToken = readCsrfCookie();
    if (!csrfToken) {
      setError("Sessão sem cookie CSRF válido — recarregue a página.");
      setPending(false);
      return;
    }

    const form = new FormData(event.currentTarget);
    const name = String(form.get("name") ?? "").trim();
    const tone = String(form.get("tone") ?? "").trim();
    if (!name || !tone) {
      setError("Nome e tom de voz são obrigatórios.");
      setPending(false);
      return;
    }

    const body = {
      name,
      tone,
      colors: splitCommas(String(form.get("colors") ?? "")),
      differentiators: splitLines(String(form.get("differentiators") ?? "")),
      restrictions: splitLines(String(form.get("restrictions") ?? "")),
    };

    try {
      const response = await fetch(`${bffOrigin}/brand-profiles`, {
        method: "POST",
        credentials: "include",
        headers: {
          "content-type": "application/json",
          "x-csrf-token": csrfToken,
          "idempotency-key": crypto.randomUUID(),
        },
        body: JSON.stringify(body),
      });
      if (!response.ok) {
        setError("Não foi possível salvar o Brand Kit. Tente novamente.");
        setPending(false);
        return;
      }
      window.location.reload();
    } catch {
      setError("Não foi possível salvar o Brand Kit. Tente novamente.");
      setPending(false);
    }
  }

  return (
    <div className={styles.wrapper}>
      {existing.length > 0 ? (
        <ul className={styles.existingList}>
          {existing.map((profile) => (
            <li key={profile.id} className={styles.existingItem}>
              <strong>{profile.name}</strong> — {profile.tone}
            </li>
          ))}
        </ul>
      ) : (
        <p className={styles.emptyNote}>
          Nenhum Brand Kit ainda — usado pela IA na geração de criativos. Pode ser
          preenchido a qualquer momento; não bloqueia a criação de campanhas.
        </p>
      )}

      <form className={styles.form} onSubmit={handleSubmit}>
        <label className={styles.field}>
          <span>Nome*</span>
          <input name="name" type="text" maxLength={120} required disabled={pending} />
        </label>
        <label className={styles.field}>
          <span>Tom de voz*</span>
          <input
            name="tone"
            type="text"
            maxLength={200}
            placeholder="formal, casual, técnico, inspirador…"
            required
            disabled={pending}
          />
        </label>
        <label className={styles.field}>
          <span>Cores principais (separadas por vírgula)</span>
          <input name="colors" type="text" placeholder="#2f5ce0, #12b886" disabled={pending} />
        </label>
        <label className={styles.field}>
          <span>Diferenciais competitivos (uma linha por item)</span>
          <textarea name="differentiators" rows={3} disabled={pending} />
        </label>
        <label className={styles.field}>
          <span>Restrições de comunicação (uma linha por item)</span>
          <textarea
            name="restrictions"
            rows={3}
            placeholder="não mencionar concorrentes…"
            disabled={pending}
          />
        </label>
        <Button type="submit" disabled={pending}>
          {pending ? "Salvando…" : "Salvar Brand Kit"}
        </Button>
        {error ? (
          <p role="alert" className={styles.error}>
            {error}
          </p>
        ) : null}
      </form>
    </div>
  );
}
