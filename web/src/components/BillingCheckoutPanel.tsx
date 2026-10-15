"use client";
import { useEffect, useRef, useState } from "react";
import type { BillingCheckout } from "@/contracts/types";
import type { useAdministrativeStepUp } from "@/hooks/useAdministrativeStepUp";
import { api, ApiClientError } from "@/lib/api/client";
import { safeBillingInvoiceUrl } from "@/lib/billing";
import { Button } from "./Button";
import { Card } from "./Card";
import { ErrorState } from "./ErrorState";
import { Spinner } from "./Spinner";

type Props = { stepUp: ReturnType<typeof useAdministrativeStepUp>; onIssued: () => void };
type Quote = NonNullable<BillingCheckout["quote"]>;
const money = (value: string) => new Intl.NumberFormat("pt-BR", { style: "currency", currency: "BRL" }).format(Number(value));
const date = (value: string) => new Date(value).toLocaleString("pt-BR", { timeZone: "America/Sao_Paulo", timeZoneName: "short" });

export function BillingCheckoutPanel({ stepUp, onIssued }: Props) {
  const [checkout, setCheckout] = useState<BillingCheckout | null>(null);
  const [loading, setLoading] = useState(true);
  const [review, setReview] = useState<{ key: string; quote: Quote } | null>(null);
  const [accepted, setAccepted] = useState(false);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [issued, setIssued] = useState(false);
  const inFlight = useRef(false);
  useEffect(() => {
    let active = true;
    api.get<BillingCheckout>("/billing/checkout").then(value => { if (active) setCheckout(value); })
      .catch(() => { if (active) setError("Não foi possível consultar os valores da cobrança."); })
      .finally(() => { if (active) setLoading(false); });
    return () => { active = false; };
  }, []);
  async function refresh() {
    if (busy || inFlight.current) return;
    setLoading(true); setError(null); setReview(null); setAccepted(false);
    try { setCheckout(await api.get<BillingCheckout>("/billing/checkout")); onIssued(); }
    catch { setError("Não foi possível atualizar a consulta."); }
    finally { setLoading(false); }
  }
  async function confirm() {
    if (!review || !accepted || !stepUp.ready || inFlight.current) return;
    inFlight.current = true; setBusy(true); setError(null);
    try {
      await api.post("/billing/charges", { competence: review.quote.competence,
        expected_quote_fingerprint: review.quote.fingerprint, accept_quote: true },
        { idempotencyKey: review.key, headers: stepUp.headers() });
      stepUp.consumePresentedToken(); setReview(null); setAccepted(false); setIssued(true); onIssued();
      // Registration is not payment. Read the persisted state rather than inventing a paid status.
      try { setCheckout(await api.get<BillingCheckout>("/billing/checkout")); } catch { /* explicit refresh remains available */ }
    } catch (err) {
      stepUp.noteError(err);
      setError(err instanceof ApiClientError && err.status < 500 ? err.message
        : "Emissão ainda não confirmada. Reutilize esta confirmação para consultar a solicitação.");
    } finally { inFlight.current = false; setBusy(false); }
  }
  const quote = review?.quote ?? checkout?.quote;
  const invoice = quote ? safeBillingInvoiceUrl(checkout?.invoice_url, quote.provider, quote.mode) : null;
  return <Card>
    <h2>Pagamento da assinatura</h2>
    {loading ? <Spinner label="Consultando valores" /> : <>
      {checkout?.state === "NOT_DUE" ? <p>Próxima renovação em {checkout.available_at ? date(checkout.available_at) : "data a confirmar"}. Nenhuma nova mensalidade será emitida antes dessa data.</p> : null}
      {checkout?.state === "CLOSED" ? <p>A renovação está cancelada. Consulte o histórico ou as opções de reativação.</p> : null}
      {checkout?.state === "UNAVAILABLE" ? <p>Checkout indisponível neste contrato.</p> : null}
      {quote ? <section aria-label="Valores da cobrança">
        <p>{quote.organization_name ?? "Organização atual"} · Titular com documento final {quote.holder_document_masked}</p>
        <p>Plano {quote.plan_name} · {quote.included_credits} créditos incluídos no ciclo pago.</p>
        <p>{quote.period_starts_at && quote.period_ends_at ? `Período: ${date(quote.period_starts_at)} a ${date(quote.period_ends_at)}.` : "O primeiro ciclo começa na confirmação do pagamento, com nova franquia integral; o saldo do trial não é somado."}</p>
        <p>Vencimento: {quote.due_at ? date(quote.due_at) : "não registrado nesta cobrança"}.</p>
        <ul>{quote.lines.map((line, index) => <li key={index}>{line.description}: {money(line.amount)}</li>)}</ul>
        <p><strong>Total: {money(quote.amount)}</strong></p>
        <p>Excedente somente após uso autorizado, por {money(quote.extra_credit_price)} por crédito. Sem juros, multa ou repasse de tarifa de gateway nesta versão.</p>
        {quote.mode !== "PRODUCTION" ? <p>{quote.mode === "SIMULATOR" ? "Simulação: esta cobrança não movimenta dinheiro." : "Ambiente de teste: esta fatura não é uma cobrança de produção."}</p> : <p>Pagamento na fatura Asaas, com as formas habilitadas para a conta. Não informe dados de cartão no CampaIA.</p>}
        {checkout?.state === "PENDING" ? <p>A emissão anterior está em conferência. Consultá-la preserva a mesma cobrança.</p> : null}
        {checkout?.state === "REGISTERED" ? <p>Cobrança já registrada. Consulte a fatura e o histórico.</p> : null}
        {!review && ["READY", "PENDING"].includes(checkout?.state ?? "") ? <Button disabled={busy} onClick={() => { setReview({ key: crypto.randomUUID(), quote }); setAccepted(false); setError(null); }}>
          {checkout?.state === "PENDING" ? "Consultar emissão pendente" : "Revisar e emitir cobrança"}</Button> : null}
        {invoice ? <a href={invoice} target="_blank" rel="noopener noreferrer">Abrir fatura Asaas</a> : null}
      </section> : null}
      {review ? <section aria-label="Confirmar cobrança revisada">
        <label><input type="checkbox" checked={accepted} disabled={busy} onChange={event => setAccepted(event.target.checked)} /> Conferi o plano, o período e o valor desta cobrança.</label>
        <Button disabled={busy || !accepted || !stepUp.ready} onClick={confirm}>{busy ? "Consultando…" : "Confirmar cobrança"}</Button>
        <Button variant="secondary" disabled={busy} onClick={() => setReview(null)}>Voltar</Button>
      </section> : null}
      <Button variant="secondary" disabled={busy} onClick={refresh}>Atualizar consulta</Button>
    </>}
    {issued ? <p role="status">Cobrança registrada. O acesso muda somente após confirmação do pagamento.</p> : null}
    {error ? <ErrorState title="Pagamento não confirmado" description={error} /> : null}
  </Card>;
}
