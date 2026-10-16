"use client";

import { useEffect, useRef, useState, type FormEvent } from "react";
import { api, ApiClientError } from "@/lib/api/client";
import { Button } from "./Button";
import { Card } from "./Card";
import { ErrorState } from "./ErrorState";
import { Input } from "./Input";
import { Spinner } from "./Spinner";

type ImageItem = {
  id: string; campaign_id: string; campaign_version: number;
  state: string; width: number; height: number; revision: number;
  content_type: string; available: boolean;
};
type ImagePage = { items: ImageItem[]; has_more: boolean; generation_enabled: boolean };
type ImageQuote = { mode: string; action: string; cycle_id: string | null; policy_version: string | null;
  credits: number | null; extra_amount: string | null; generation_enabled: boolean };
type Pending = { key: string; prompt: string; quote: ImageQuote; sent: boolean };

export function GeneratedImagesPanel({ campaignId, planVersion }: { campaignId: string; planVersion: number }) {
  const [page, setPage] = useState<ImagePage | null>(null);
  const [quote, setQuote] = useState<ImageQuote | null>(null);
  const [prompt, setPrompt] = useState("");
  const [pending, setPending] = useState<Pending | null>(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [notice, setNotice] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);
  const alive = useRef(false);
  const inflight = useRef(false);
  const base = "/campaigns/" + encodeURIComponent(campaignId) + "/images";

  async function refresh() {
    const [found, cost] = await Promise.all([
      api.get<ImagePage>(base),
      api.get<ImageQuote>(base + "/quote").catch(() => null),
    ]);
    if (alive.current) { setPage(found); setQuote(cost); setError(null); }
  }
  useEffect(() => {
    alive.current = true;
    refresh().catch((cause) => {
      if (alive.current) setError(cause instanceof ApiClientError ? cause.message : "Falha ao consultar criativos.");
    }).finally(() => { if (alive.current) setLoading(false); });
    return () => { alive.current = false; };
    // The parent is keyed by authenticated tenant, unit and campaign.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [campaignId, planVersion]);

  async function review(event: FormEvent) {
    event.preventDefault();
    if (!page?.generation_enabled || !quote?.generation_enabled || !quote.cycle_id ||
        !quote.policy_version || quote.credits === null || quote.extra_amount === null ||
        prompt.trim().length < 8 || planVersion < 1 || inflight.current || pending) return;
    setPending({ key: "image-" + crypto.randomUUID(), prompt: prompt.trim(), quote, sent: false });
    setNotice(null); setError(null);
  }

  async function confirm() {
    if (!pending || inflight.current) return;
    inflight.current = true;
    setBusy(true);
    setError(null);
    const current = { ...pending, sent: true };
    setPending(current);
    try {
      await api.post<ImageItem>(base, {
        expected_plan_version: planVersion,
        prompt: current.prompt,
        credit_confirmation: {
          cycle_id: current.quote.cycle_id, policy_version: current.quote.policy_version,
          credits: current.quote.credits, extra_amount: current.quote.extra_amount,
        },
      }, { idempotencyKey: current.key, timeoutMs: 60_000 });
      if (!alive.current) return;
      setPending(null); setNotice("Criativo armazenado. Revise-o antes de publicar.");
      try { await refresh(); }
      catch { if (alive.current) setError("Entrega confirmada; atualize o histórico para conferir."); }
    } catch (cause) {
      if (!alive.current) return;
      if (cause instanceof ApiClientError && cause.status < 500 && cause.status !== 408 &&
          cause.code !== "AI_OPERATION_PENDING") {
        setPending(null);
        setError(cause.message);
      } else {
        setError("Resultado incerto. A chave original foi preservada; não iniciaremos outra geração.");
      }
    } finally {
      inflight.current = false;
      if (alive.current) setBusy(false);
    }
  }

  const enabled = Boolean(page?.generation_enabled && quote?.generation_enabled && !pending);
  return <Card><section aria-label="Imagens da campanha">
    <h2>Imagens da campanha</h2>
    <p>Histórico privado de imagens para revisão humana; nenhuma publicação automática.</p>
    {loading ? <Spinner label="Consultando imagens" /> : null}
    {error ? <ErrorState title="Imagens precisam de atenção" description={error} /> : null}
    {notice ? <p role="status">{notice}</p> : null}
    {quote?.mode === "COMMERCIAL" && quote.credits !== null
      ? <p>Créditos previstos por imagem: {quote.credits}. Extra previsto: {quote.extra_amount ?? "não disponível"}.</p>
      : null}
    {!page?.generation_enabled ? <p role="status">Geração indisponível até as configurações internas e externas necessárias.</p> : null}
    <form onSubmit={review}>
      <Input label="Descrição da imagem" value={prompt} onChange={(event) => setPrompt(event.target.value)}
        minLength={8} maxLength={1500} disabled={!enabled || busy} required />
      <Button disabled={!enabled || busy || prompt.trim().length < 8} variant="secondary">Revisar créditos para gerar imagem</Button>
    </form>
    {pending ? <div>
      <p>Confirme a geração com {pending.quote.credits} créditos e valor extra previsto de {pending.quote.extra_amount}.</p>
      {pending.sent ? <p>A mesma chave será reutilizada. Nenhum segundo disparo é autorizado.</p> : null}
      <Button disabled={busy} onClick={confirm} variant="secondary">
        {pending.sent ? "Conferir mesma solicitação" : "Confirmar geração"}
      </Button>
      {!pending.sent ? <Button disabled={busy} variant="secondary" onClick={() => setPending(null)}>Cancelar</Button> : null}
    </div> : null}
    {page && page.items.length === 0 ? <p>Nenhum criativo registrado nesta campanha.</p> : null}
    {page?.items.map((item) => <div key={item.id}>
      <p>Criativo {item.id} · versão {item.campaign_version} · {item.width} × {item.height} · {item.state}</p>
      {!item.available ? <p>Entrega ainda não confirmada.</p> : null}
    </div>)}
    {page?.has_more ? <p>Existem mais registros; consulte os históricos da campanha.</p> : null}
  </section></Card>;
}
