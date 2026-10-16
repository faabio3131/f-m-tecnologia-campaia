"use client";
import { useEffect, useRef, useState } from "react";
import type { BrandProfile, BrandVersions } from "@/contracts/types";
import { api } from "@/lib/api/client";
import { Button } from "./Button";
import { ErrorState } from "./ErrorState";
import { Spinner } from "./Spinner";

export function BrandHistoryPanel({ identity, name }: { identity: string; name: string }) {
  const [items, setItems] = useState<BrandProfile[] | null>(null);
  const [cursor, setCursor] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const inFlight = useRef(false);
  useEffect(() => {
    let active = true;
    api.get<BrandVersions>(`/brand-profiles/${encodeURIComponent(identity)}/versions`).then(result => {
      if (!Array.isArray(result?.items)) throw new Error("History unavailable");
      if (active) { setItems(result.items); setCursor(result.next_cursor); }
    }).catch(() => { if (active) setError("Não foi possível consultar as versões preservadas."); });
    return () => { active = false; };
  }, [identity]);
  async function more() {
    if (!cursor || inFlight.current) return;
    inFlight.current = true; setBusy(true); setError(null);
    try {
      const result = await api.get<BrandVersions>(`/brand-profiles/${encodeURIComponent(identity)}/versions?cursor=${encodeURIComponent(cursor)}`);
      if (!Array.isArray(result?.items)) throw new Error("History unavailable");
      setItems(previous => [...previous ?? [], ...result.items]); setCursor(result.next_cursor);
    } catch { setError("Não foi possível consultar as versões preservadas."); }
    finally { inFlight.current = false; setBusy(false); }
  }
  return <section aria-label={`Histórico de ${name}`} style={{ overflowWrap: "anywhere" }}>
    <h3>Versões preservadas</h3>
    {items === null && !error ? <Spinner label="Consultando versões" /> : null}
    {items?.map((item, index) => <article key={item.version ?? index}>
      <h4>Versão {item.version ?? 1} — {item.name}</h4>
      <p>Tom de voz: {item.tone}.</p>
      <p>Cores: {item.colors?.join(", ") || "Não informadas"}.</p>
      <p>Diferenciais: {item.differentiators?.join("; ") || "Não informados"}.</p>
      <p>Restrições: {item.restrictions?.join("; ") || "Não informadas"}.</p>
      {item.updated_at ? <p>Atualizada em {new Date(item.updated_at).toLocaleString("pt-BR")}.</p>
        : item.created_at ? <p>Cadastro original de {new Date(item.created_at).toLocaleString("pt-BR")}.</p> : null}
    </article>)}
    {cursor ? <Button variant="secondary" disabled={busy} onClick={more}>Carregar mais versões</Button> : null}
    {error ? <ErrorState title="Histórico indisponível" description={error} /> : null}
  </section>;
}
