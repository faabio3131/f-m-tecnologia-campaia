"use client";

import { useEffect, useRef, useState, type FormEvent } from "react";
import Image from "next/image";
import { api, ApiClientError } from "@/lib/api/client";
import { Button } from "./Button";
import { Card } from "./Card";
import { ErrorState } from "./ErrorState";
import { Input } from "./Input";
import { Spinner } from "./Spinner";

type ImageItem = {
  id: string; campaign_id: string; campaign_version: number;
  state: string; width: number; height: number; revision: number;
  content_type: string; available: boolean; content_url: string | null;
  sha256?: string; storage_generation?: string | null; source_creative_id?: string | null;
};
type ImagePage = { items: ImageItem[]; has_more: boolean; generation_enabled: boolean };
type ImageQuote = { mode: string; action: string; cycle_id: string | null; policy_version: string | null;
  credits: number | null; extra_amount: string | null; generation_enabled: boolean };
type Pending = { key: string; prompt: string; quote: ImageQuote; sent: boolean };

export function GeneratedImagesPanel({ campaignId, planVersion }: { campaignId: string; planVersion: number }) {
  const [page, setPage] = useState<ImagePage | null>(null);
  const [quote, setQuote] = useState<ImageQuote | null>(null);
  const [prompt, setPrompt] = useState("");
  const [editOperation, setEditOperation] = useState<Record<string, string>>({});
  const [pending, setPending] = useState<Pending | null>(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [notice, setNotice] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);
  const alive = useRef(false);
  const inflight = useRef(false);
  const editReplayKeys = useRef<Record<string, string>>({});
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
        setNotice("Resultado incerto. A chave original foi preservada; consulte o inventário e reconcilie sem gerar novamente.");
        try { await refresh(); } catch { if (alive.current) setError("Histórico indisponível; mantenha a solicitação original."); }
      }
    } finally {
      inflight.current = false;
      if (alive.current) setBusy(false);
    }
  }

  async function editPixels(item: ImageItem) {
    const operation = editOperation[item.id] || "rotate_90";
    if (busy || inflight.current || item.state !== "STORED" ||
        item.campaign_version !== planVersion || !item.sha256 || !item.storage_generation) return;
    inflight.current = true; setBusy(true); setError(null); setNotice(null);
    const replayScope = item.id + ":" + item.sha256 + ":" + item.storage_generation + ":" + operation;
    const idemKey = editReplayKeys.current[replayScope] || ("pixel-edit-" + crypto.randomUUID());
    editReplayKeys.current[replayScope] = idemKey;
    try {
      await api.post<ImageItem>(base + "/" + encodeURIComponent(item.id) + "/pixel-edit", {
        operation, expected_sha256: item.sha256, expected_generation: item.storage_generation,
      }, { idempotencyKey: idemKey, timeoutMs: 60_000 });
      delete editReplayKeys.current[replayScope];
      if (alive.current) {
        setNotice("Nova versão editada armazenada; a imagem original foi preservada.");
        await refresh();
      }
    } catch (cause) {
      if (alive.current) {
        const msg = cause instanceof ApiClientError ? cause.message : "Edição não confirmada.";
        setError(msg + " Se o resultado for incerto, consulte o histórico antes de repetir.");
      }
    } finally {
      inflight.current = false;
      if (alive.current) setBusy(false);
    }
  }

  async function reconcile(item: ImageItem) {
    if (busy || inflight.current || item.state !== "STORAGE_PENDING") return;
    inflight.current = true; setBusy(true); setError(null);
    try {
      const result = await api.post<ImageItem>(base + "/" + encodeURIComponent(item.id) + "/reconcile",
        undefined, { idempotencyKey: "creative-reconcile-" + item.id });
      if (!alive.current) return;
      if (result.available) {
        setPending(null); setNotice("Armazenamento e créditos reconciliados.");
      } else setNotice("Criativo ainda pendente; não é seguro repetir a geração.");
      await refresh();
    } catch (cause) {
      if (alive.current) setError(cause instanceof ApiClientError ? cause.message : "Não foi possível reconciliar agora.");
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
      <Button type="submit" disabled={!enabled || busy || prompt.trim().length < 8} variant="secondary">Revisar créditos para gerar imagem</Button>
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
      {item.available && item.content_url ? <Image unoptimized src={item.content_url}
        alt={"Criativo " + item.id} width={item.width} height={item.height}
        style={{ maxWidth: "min(100%, 320px)", height: "auto" }} /> : null}
      {item.source_creative_id ? <p>Versão derivada de {item.source_creative_id}</p> : null}
      {item.available && item.campaign_version === planVersion && item.sha256 && item.storage_generation
        ? <div aria-label={"Editor de imagem " + item.id}>
          <label htmlFor={"pixel-edit-" + item.id}>Transformação da imagem</label>
          <select id={"pixel-edit-" + item.id} value={editOperation[item.id] || "rotate_90"}
            disabled={busy} onChange={(event) => setEditOperation((values) =>
              ({ ...values, [item.id]: event.target.value }))}>
            <option value="rotate_90">Girar 90 graus</option>
            <option value="rotate_180">Girar 180 graus</option>
            <option value="flip_horizontal">Espelhar horizontalmente</option>
          </select>
          <Button variant="secondary" disabled={busy}
            onClick={() => void editPixels(item)}>Criar versão editada</Button>
          <p>A edição exige autenticação reforçada. Nenhuma imagem aprovada é alterada.</p>
        </div> : null}
      {item.available ? <p>
        <a href={"/api/campaia" + base + "/" + encodeURIComponent(item.id) + "/visual-preview/google"}>Rascunho Google Ads</a>
        {" · "}<a href={base + "/" + encodeURIComponent(item.id) + "/visual-preview/meta"}>Rascunho Meta</a>
        {" · "}<a href={base + "/" + encodeURIComponent(item.id) + "/visual-preview/whatsapp"}>Rascunho WhatsApp</a>
      </p> : null}
      {!item.available ? <p>Entrega ainda não confirmada.</p> : null}
      {item.state === "STORAGE_PENDING" ? <Button disabled={busy}
        onClick={() => void reconcile(item)} variant="secondary">Conferir armazenamento</Button> : null}
    </div>)}
    {page?.has_more ? <p>Existem mais registros; consulte os históricos da campanha.</p> : null}
  </section></Card>;
}
