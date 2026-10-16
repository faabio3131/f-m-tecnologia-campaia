"use client";
import { useEffect, useRef, useState, type FormEvent } from "react";
import type { CopyRevisionInput, CreativeProposal, CreativeProposalQuote } from "@/contracts/types";
import { api, ApiClientError } from "@/lib/api/client";
import { Button } from "./Button";
import { ErrorState } from "./ErrorState";

type Props = { campaignId: string; source: CreativeProposal; planVersion: number; busy: boolean;
  canGenerate: boolean; onBusy: (value: boolean) => void; onDelivered: () => Promise<void>; onCancel: () => void };
type Intent = { key: string; body: CopyRevisionInput; sent: boolean };
const channels: CopyRevisionInput["channel"][] = ["GOOGLE_ADS", "META_ADS", "META_FACEBOOK", "META_INSTAGRAM", "WHATSAPP"];
const currency = (value: string) => new Intl.NumberFormat("pt-BR", { style: "currency", currency: "BRL" }).format(Number(value));

export function CopyRevisionPanel({ campaignId, source, planVersion, busy, canGenerate, onBusy, onDelivered, onCancel }: Props) {
  const [index, setIndex] = useState(0), [instructions, setInstructions] = useState("");
  const [intent, setIntent] = useState<Intent | null>(null);
  const [error, setError] = useState<string | null>(null);
  const active = useRef(false), alive = useRef(false);
  const variants = "variacoes" in source.output ? source.output.variacoes : [];
  const endpoint = "/campaigns/" + encodeURIComponent(campaignId) + "/proposals/copy/" + encodeURIComponent(source.id) + "/revisions";
  useEffect(() => { alive.current = true; return () => { alive.current = false; }; }, [source.id]);

  async function deliver(request: Intent) {
    setIntent({ ...request, sent: true });
    try {
      await api.post<CreativeProposal>(endpoint, request.body, { idempotencyKey: request.key });
    } catch (err) {
      if (!alive.current) return;
      if (!request.sent && err instanceof ApiClientError && err.status < 500 && err.status !== 408) {
        setIntent(null); setError(err.message);
      } else {
        setError("Resultado ainda não confirmado. Confira o mesmo ajuste para evitar uma nova solicitação.");
      }
      return;
    }
    if (!alive.current) return;
    setIntent(null);
    // Delivery is confirmed; refresh errors never become a second uncertain write.
    try { await onDelivered(); }
    catch { if (alive.current) setError("Ajuste entregue. Atualize o histórico para conferir."); }
  }
  async function review(event: FormEvent) {
    event.preventDefault();
    if (active.current || busy || !canGenerate) return;
    active.current = true; onBusy(true); setError(null);
    try {
      const sourceChannel = source.request_summary.channel;
      if (!channels.some(value => value === sourceChannel)) throw new Error("Missing original channel");
      const quote = await api.get<CreativeProposalQuote>(endpoint + "/quote");
      const body: CopyRevisionInput = { expected_plan_version: planVersion,
        channel: sourceChannel as CopyRevisionInput["channel"], variant_index: index, instructions };
      const prepared: Intent = { key: "copy-revision-" + crypto.randomUUID(), body, sent: false };
      if (quote.mode === "COMMERCIAL") {
        if (!quote.cycle_id || !quote.policy_version || quote.credits === null || quote.extra_amount === null) {
          throw new Error("Incomplete quote");
        }
        body.credit_confirmation = { cycle_id: quote.cycle_id, policy_version: quote.policy_version,
          credits: quote.credits, extra_amount: quote.extra_amount };
        if (alive.current) setIntent(prepared);
      } else { await deliver(prepared); }
    } catch (err) {
      if (alive.current) setError(err instanceof ApiClientError ? err.message : "Não foi possível revisar o consumo do ajuste.");
    } finally { active.current = false; onBusy(false); }
  }
  async function confirm() {
    if (!intent || active.current || busy) return;
    active.current = true; onBusy(true); setError(null);
    try { await deliver(intent); }
    finally { active.current = false; onBusy(false); }
  }
  return <section aria-label="Ajustar uma variação">
    <h3>Ajustar uma variação da versão {source.version}</h3>
    <p>Os demais textos serão preservados. O lote original continuará no histórico.</p>
    {error ? <ErrorState title="Ajuste precisa de atenção" description={error} /> : null}
    <form onSubmit={review}>
      <fieldset disabled={busy || intent !== null || !canGenerate}>
        <legend>Descrever ajuste</legend>
        <label>Texto para ajustar <select value={index} onChange={event => setIndex(Number(event.target.value))}>
          {variants.map((_value, position) => <option key={position} value={position}>Texto {position + 1}</option>)}
        </select></label>
        <blockquote>{variants[index]}</blockquote>
        <label>Instruções para o ajuste <textarea value={instructions} required maxLength={2000}
          onChange={event => setInstructions(event.target.value)} /></label>
      </fieldset>
      {!intent ? <Button type="submit" disabled={busy || !canGenerate || variants.length === 0}>Revisar consumo do ajuste</Button> : null}
    </form>
    {intent ? <section aria-label="Confirmar ajuste">
      {intent.body.credit_confirmation ? <p>Este ajuste utiliza {intent.body.credit_confirmation.credits} crédito{intent.body.credit_confirmation.credits === 1 ? "" : "s"}.
        Excedente estimado: {currency(intent.body.credit_confirmation.extra_amount)}.</p> : null}
      {intent.sent ? <p>O texto e as instruções estão preservados para conferir a mesma operação.</p> : null}
      <Button disabled={busy} onClick={confirm}>{intent.sent ? "Conferir mesmo ajuste" : "Confirmar ajuste"}</Button>
      {!intent.sent ? <Button variant="secondary" disabled={busy} onClick={() => setIntent(null)}>Voltar aos ajustes</Button> : null}
    </section> : null}
    {!intent?.sent ? <Button variant="secondary" disabled={busy} onClick={onCancel}>Fechar ajuste</Button> : null}
  </section>;
}
