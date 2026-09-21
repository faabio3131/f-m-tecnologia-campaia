"use client";

import { useRouter } from "next/navigation";
import { useState } from "react";
import { Button } from "@/components/Button";
import styles from "./BriefForm.module.css";

/**
 * WP-05: sixth deliberate client-side network call in web/src -- see
 * scripts/lib/security-boundaries.mjs's NETWORK_CALL_ALLOWED_FILES. Same CSRF discipline as
 * every other mutation in this app. POST /briefs also requires an Idempotency-Key
 * (backend/api/deps.py require_idempotency_key), generated fresh per submit.
 *
 * region/currency are left out of this form entirely and NOT sent in the body --
 * BriefCreate (backend/api/models.py) already defaults both ("BR"/"BRL"), and this sandbox
 * has no other market/currency to choose from yet, so exposing the fields would be a control
 * with only one real answer.
 */
function readCsrfCookie(): string | null {
  const match = document.cookie.match(/(?:^|; )campaia_csrf=([^;]+)/);
  return match ? decodeURIComponent(match[1]) : null;
}

const CHANNELS = [
  { value: "GOOGLE_ADS", label: "Google Ads" },
  { value: "META_FACEBOOK", label: "Meta — Facebook" },
  { value: "META_INSTAGRAM", label: "Meta — Instagram" },
  { value: "WHATSAPP", label: "WhatsApp" },
];

export interface BriefFormProps {
  bffOrigin: string;
}

export function BriefForm({ bffOrigin }: BriefFormProps) {
  const router = useRouter();
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
    const objective = String(form.get("objective") ?? "").trim();
    if (!objective) {
      setError("Objetivo é obrigatório.");
      setPending(false);
      return;
    }
    const channels = CHANNELS.filter((c) => form.get(`channel-${c.value}`) === "on").map(
      (c) => c.value,
    );
    if (channels.length === 0) {
      setError("Selecione ao menos um canal.");
      setPending(false);
      return;
    }

    const body = {
      name: String(form.get("name") ?? "").trim(),
      objective,
      product: String(form.get("product") ?? "").trim(),
      audience: String(form.get("audience") ?? "").trim(),
      total_budget: String(form.get("total_budget") ?? "10000"),
      daily_cap: String(form.get("daily_cap") ?? "1000"),
      channels,
    };

    try {
      const response = await fetch(`${bffOrigin}/briefs`, {
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
        setError("Não foi possível submeter o briefing. Tente novamente.");
        setPending(false);
        return;
      }
      const campaign = (await response.json()) as { id: string };
      router.push(`/campaigns/${campaign.id}`);
    } catch {
      setError("Não foi possível submeter o briefing. Tente novamente.");
      setPending(false);
    }
  }

  return (
    <form className={styles.form} onSubmit={handleSubmit}>
      <label className={styles.field}>
        <span>Nome da campanha</span>
        <input name="name" type="text" maxLength={120} disabled={pending} />
      </label>
      <label className={styles.field}>
        <span>Objetivo*</span>
        <input
          name="objective"
          type="text"
          maxLength={500}
          placeholder="ex: gerar leads qualificados para o novo produto"
          required
          disabled={pending}
        />
      </label>
      <label className={styles.field}>
        <span>Produto/serviço</span>
        <input name="product" type="text" maxLength={200} disabled={pending} />
      </label>
      <label className={styles.field}>
        <span>Público-alvo</span>
        <input name="audience" type="text" maxLength={300} disabled={pending} />
      </label>
      <div className={styles.row}>
        <label className={styles.field}>
          <span>Orçamento total (BRL)</span>
          <input
            name="total_budget"
            type="number"
            min="0"
            step="0.01"
            defaultValue="10000"
            disabled={pending}
          />
        </label>
        <label className={styles.field}>
          <span>Limite diário (BRL)</span>
          <input
            name="daily_cap"
            type="number"
            min="0"
            step="0.01"
            defaultValue="1000"
            disabled={pending}
          />
        </label>
      </div>
      <fieldset className={styles.channels}>
        <legend>Canais*</legend>
        {CHANNELS.map((channel) => (
          <label key={channel.value} className={styles.channelOption}>
            <input
              type="checkbox"
              name={`channel-${channel.value}`}
              defaultChecked={channel.value === "GOOGLE_ADS"}
              disabled={pending}
            />
            {channel.label}
          </label>
        ))}
      </fieldset>
      <Button type="submit" disabled={pending}>
        {pending ? "Enviando…" : "Enviar briefing"}
      </Button>
      {error ? (
        <p role="alert" className={styles.error}>
          {error}
        </p>
      ) : null}
    </form>
  );
}
