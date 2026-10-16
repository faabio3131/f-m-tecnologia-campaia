"use client";
import { useEffect, useRef, useState, type FormEvent } from "react";
import type { CopyProposalInput, AudienceProposalInput, CreativeProposal, CreativeProposalPage, CreativeProposalQuote } from "@/contracts/types";
import { api, ApiClientError } from "@/lib/api/client";
import { CopyRevisionPanel } from "./CopyRevisionPanel";
import { Button } from "./Button";
import { Card } from "./Card";
import { ErrorState } from "./ErrorState";
import { Input } from "./Input";
import { Spinner } from "./Spinner";

type Kind = "copy" | "audience";
type Props = { campaignId: string; planVersion: number; channels: string[];
  product?: string; audience?: string; busy: boolean; onBusy: (value: boolean) => void;
  onDelivered: () => Promise<void> };
type Prepared = { key: string; kind: Kind; body: CopyProposalInput | AudienceProposalInput; sent: boolean };
type Pages = Partial<Record<Kind, CreativeProposalPage>>;
const labels: Record<Kind, string> = { copy: "Textos", audience: "Públicos" };
const knownChannels: CopyProposalInput["channel"][] = ["GOOGLE_ADS", "META_ADS", "META_FACEBOOK", "META_INSTAGRAM", "WHATSAPP"];
const currency = (value: string) => new Intl.NumberFormat("pt-BR", { style: "currency", currency: "BRL" }).format(Number(value));

export function CreativeProposalsPanel({ campaignId, planVersion, channels, product = "", audience: initialAudience = "",
  busy, onBusy, onDelivered }: Props) {
  const allowed = knownChannels.filter(value => channels.includes(value));
  const [pages, setPages] = useState<Pages>({});
  const [kind, setKind] = useState<Kind>("copy");
  const [channel, setChannel] = useState<CopyProposalInput["channel"]>(allowed[0] ?? "GOOGLE_ADS");
  const [offer, setOffer] = useState(product), [tone, setTone] = useState("");
  const [variants, setVariants] = useState(5);
  const [audience, setAudience] = useState(initialAudience), [region, setRegion] = useState("BR");
  const [exclusions, setExclusions] = useState(""), [sensitive, setSensitive] = useState(false);
  const [prepared, setPrepared] = useState<Prepared | null>(null);
  const [revisionSource, setRevisionSource] = useState<CreativeProposal | null>(null);
  const [error, setError] = useState<string | null>(null), [notice, setNotice] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);
  const active = useRef(false), alive = useRef(false), readEpoch = useRef(0);
  const base = "/campaigns/" + encodeURIComponent(campaignId) + "/proposals/";

  async function refresh() {
    const epoch = ++readEpoch.current;
    const [copy, publicos] = await Promise.all([
      api.get<CreativeProposalPage>(base + "copy"), api.get<CreativeProposalPage>(base + "audience"),
    ]);
    if (alive.current && readEpoch.current === epoch) setPages({ copy, audience: publicos });
  }
  useEffect(() => {
    alive.current = true;
    refresh().catch(() => { if (alive.current) setError("Não foi possível consultar as propostas."); })
      .finally(() => { if (alive.current) setLoading(false); });
    return () => { alive.current = false; };
    // Campaign scope is keyed by the parent, including tenant and business unit.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [campaignId, planVersion]);

  async function deliver(intent: Prepared) {
    const sent = { ...intent, sent: true };
    setPrepared(sent);
    let delivered: CreativeProposal;
    try {
      delivered = await api.post<CreativeProposal>(base + intent.kind, intent.body, { idempotencyKey: intent.key });
    } catch (err) {
      if (!alive.current) return;
      if (!intent.sent && err instanceof ApiClientError && err.status < 500 && err.status !== 408) {
        setPrepared(null); setError(err.message);
      } else {
        setError("Resultado ainda não confirmado. Confira a mesma solicitação antes de alterar os campos.");
      }
      return;
    }
    if (!alive.current) return;
    // The write is confirmed. A subsequent read error must never turn it into an uncertain write.
    setPrepared(null); setNotice(labels[intent.kind] + " entregues · versão " + delivered.version + ".");
    try { await onDelivered(); await refresh(); }
    catch { if (alive.current) setError("Entrega confirmada. Atualize o histórico para conferir a versão atual."); }
  }
  async function review(event: FormEvent) {
    event.preventDefault();
    if (active.current || busy || revisionSource !== null || !pages[kind]?.capability.can_generate || allowed.length === 0) return;
    active.current = true; onBusy(true); setError(null); setNotice(null);
    try {
      const quote = await api.get<CreativeProposalQuote>(base + kind + "/quote");
      const body: CopyProposalInput | AudienceProposalInput = kind === "copy"
        ? { expected_plan_version: planVersion, channel, offer, tone, variants }
        : { expected_plan_version: planVersion, channel, audience, region,
            exclusions: exclusions.split("\n").map(value => value.trim()).filter(Boolean), sensitive_declared: sensitive };
      const intent: Prepared = { key: "creative-" + kind + "-" + crypto.randomUUID(), kind, body, sent: false };
      if (quote.mode === "COMMERCIAL") {
        if (!quote.cycle_id || !quote.policy_version || quote.credits === null || quote.extra_amount === null) {
          throw new Error("Incomplete quote");
        }
        body.credit_confirmation = { cycle_id: quote.cycle_id, policy_version: quote.policy_version,
          credits: quote.credits, extra_amount: quote.extra_amount };
        if (alive.current) setPrepared(intent);
      } else {
        await deliver(intent);
      }
    } catch (err) {
      if (alive.current) setError(err instanceof ApiClientError ? err.message : "Não foi possível revisar o consumo.");
    } finally { active.current = false; if (alive.current) onBusy(false); }
  }
  async function confirm() {
    if (!prepared || active.current || busy) return;
    active.current = true; onBusy(true); setError(null);
    try { await deliver(prepared); }
    finally { active.current = false; if (alive.current) onBusy(false); }
  }
  async function readMore(target: Kind) {
    if (active.current || busy) return;
    const cursor = pages[target]?.next_cursor;
    active.current = true; onBusy(true); setError(null);
    try {
      if (!cursor) { await refresh(); return; }
      const next = await api.get<CreativeProposalPage>(base + target + "?cursor=" + encodeURIComponent(cursor));
      if (alive.current) setPages(previous => ({ ...previous, [target]: {
        ...next, items: [...previous[target]?.items ?? [], ...next.items],
      } }));
    } catch { if (alive.current) setError("Não foi possível consultar o histórico."); }
    finally { active.current = false; if (alive.current) onBusy(false); }
  }

  const page = pages[kind], locked = busy || prepared !== null || revisionSource !== null;
  return <Card><section aria-label="Textos e públicos" style={{ overflowWrap: "anywhere" }}>
    <h2>Textos e públicos</h2>
    <p>Propostas em texto para revisão humana. Cada entrega pede nova validação e aprovação da campanha.</p>
    <p>São rascunhos; a aparência e o direcionamento final do anúncio dependem da preparação por canal.</p>
    {loading ? <Spinner label="Consultando propostas" /> : null}
    {error ? <ErrorState title="Propostas precisam de atenção" description={error} /> : null}
    {notice ? <p role="status">{notice}</p> : null}
    <form onSubmit={review}>
      <fieldset disabled={locked}>
        <legend>Preparar proposta</legend>
        <label>Tipo de proposta <select value={kind} onChange={event => setKind(event.target.value as Kind)}>
          <option value="copy">Textos</option><option value="audience">Públicos</option>
        </select></label>
        <label>Canal da proposta <select value={channel} onChange={event => setChannel(event.target.value as CopyProposalInput["channel"])}>
          {allowed.map(value => <option key={value} value={value}>{value}</option>)}
        </select></label>
        {kind === "copy" ? <>
          <Input label="Oferta dos textos" value={offer} required maxLength={2000} onChange={event => setOffer(event.target.value)} />
          <Input label="Tom dos textos" value={tone} required maxLength={200} onChange={event => setTone(event.target.value)} />
          <Input label="Quantidade de textos" type="number" value={variants} min={1} max={5} step={1}
            onChange={event => setVariants(Number(event.target.value))} required />
        </> : <>
          <Input label="Público desejado" value={audience} required maxLength={2000} onChange={event => setAudience(event.target.value)} />
          <Input label="Região do público" value={region} required maxLength={120} onChange={event => setRegion(event.target.value)} />
          <label>Exclusões (uma por linha) <textarea value={exclusions} maxLength={10020}
            onChange={event => setExclusions(event.target.value)} /></label>
          <label><input type="checkbox" checked={sensitive} onChange={event => setSensitive(event.target.checked)} />Público envolve tema sensível</label>
        </>}
      </fieldset>
      {page?.capability.mode === "SIMULATED" ? <p>Ambiente de teste: geração simulada.</p> : null}
      {page && !page.capability.enabled ? <p>Esta geração está indisponível no momento.</p> : null}
      {page?.capability.billing_required ? <p>Inicie um trial ou ciclo pago antes de gerar.</p> : null}
      {!prepared ? <Button type="submit" disabled={locked || !page?.capability.can_generate || allowed.length === 0}>Gerar proposta</Button> : null}
    </form>
    {prepared ? <section aria-label="Confirmar proposta">
      {prepared.body.credit_confirmation ? <p>Esta entrega utiliza {prepared.body.credit_confirmation.credits} créditos.
        Excedente estimado: {currency(prepared.body.credit_confirmation.extra_amount)}.</p> : null}
      {prepared.sent ? <p>Os campos estão preservados para conferir a mesma operação.</p> : <p>Confirme o consumo antes de gerar.</p>}
      <Button disabled={busy} onClick={confirm}>{prepared.sent ? "Conferir mesma proposta" : "Confirmar proposta"}</Button>
      {!prepared.sent ? <Button variant="secondary" disabled={busy} onClick={() => setPrepared(null)}>Voltar aos campos</Button> : null}
    </section> : null}
    {revisionSource ? <CopyRevisionPanel key={revisionSource.id} campaignId={campaignId} source={revisionSource}
      planVersion={planVersion} busy={busy} canGenerate={pages.copy?.capability.can_generate ?? false}
      onBusy={onBusy} onCancel={() => setRevisionSource(null)} onDelivered={async () => {
        setRevisionSource(null); setNotice("Ajuste entregue. Confira a nova versão dos textos.");
        try { await onDelivered(); await refresh(); }
        catch { if (alive.current) setError("Ajuste entregue. Atualize o histórico para conferir a versão atual."); }
      }} /> : null}
    <Button variant="secondary" disabled={busy} onClick={() => readMore(kind)}>Atualizar histórico de propostas</Button>
    {(["copy", "audience"] as const).map(target => <section key={target} aria-label={"Histórico de " + labels[target]}>
      <h3>{labels[target]} preservados</h3>
      {pages[target]?.items.length === 0 ? <p>Nenhuma proposta de {labels[target].toLowerCase()} ainda.</p> : null}
      {pages[target]?.items.map((item, position) => <article key={item.id}>
        <h4>{labels[target]} · versão {item.version}</h4>
        <p>{item.current ? "Contexto vigente" : "Contexto anterior · precisa gerar novamente"} · plano {item.plan_version}</p>
        {"variacoes" in item.output ? <ol>{item.output.variacoes.map((value, index) => <li key={index}>{value}</li>)}</ol>
          : <><p>Segmentos: {item.output.segmentos.join("; ")}.</p><p>Exclusões: {item.output.exclusoes.join("; ") || "Nenhuma"}.</p>
            <p>Tema sensível identificado: {item.output.sensivel ? "Sim" : "Não"}.</p></>}
        {target === "copy" && position === 0 && item.current && pages.copy?.capability.can_generate
          ? <Button variant="secondary" disabled={busy || prepared !== null || revisionSource !== null}
              onClick={() => setRevisionSource(item)}>Ajustar um texto</Button> : null}
        {typeof item.request_summary.revision_of === "string" ? <p>Revisão de uma variação da versão anterior.</p> : null}
        <details><summary>Contexto e origem</summary>
          <pre style={{ whiteSpace: "pre-wrap" }}>{JSON.stringify(item.request_summary, null, 2)}</pre>
          <p>{item.provider} · {item.model} · prompt {item.prompt_version}</p>
          <p>{new Date(item.created_at).toLocaleString("pt-BR")}</p>
        </details>
      </article>)}
      {pages[target]?.next_cursor ? <Button variant="secondary" disabled={busy} onClick={() => readMore(target)}>Mais versões de {labels[target].toLowerCase()}</Button> : null}
    </section>)}
  </section></Card>;
}
