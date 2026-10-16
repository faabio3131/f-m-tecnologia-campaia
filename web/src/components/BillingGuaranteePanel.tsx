"use client";

import { useEffect, useRef, useState } from "react";
import type { BillingGuarantee } from "@/contracts/types";
import type { useAdministrativeStepUp } from "@/hooks/useAdministrativeStepUp";
import { api, ApiClientError } from "@/lib/api/client";
import { Button } from "./Button";
import { Card } from "./Card";
import { ErrorState } from "./ErrorState";
import { Spinner } from "./Spinner";

type Props = { stepUp: ReturnType<typeof useAdministrativeStepUp>; onRequested: () => void };
const MESSAGE: Record<BillingGuarantee["state"], string> = {
  UNAVAILABLE: "A garantia comercial fica disponível após o primeiro pagamento confirmado.",
  MANUAL_REVIEW: "Precisamos conferir o histórico do primeiro pagamento. Seus direitos de revisão permanecem preservados.",
  ELIGIBLE: "A primeira contratação está dentro da janela de garantia comercial de 7 dias.",
  EXPIRED: "A janela da garantia comercial terminou. Direitos legais e revisão de cobranças indevidas permanecem preservados.",
  REQUESTED: "Solicitação registrada. O recebimento do pedido não confirma o estorno ou a devolução.",
  PROCESSING: "Tratamento iniciado. Devoluções e ajustes são conferidos separadamente.",
  FINANCIALLY_RESOLVED: "Devolução integral conferida e encerramento financeiro registrado.",
};
const REFUND_PROGRESS: Record<string, string> = {
  NOT_DISPATCHED: "Aguardando conferência da devolução", PROVIDER_PENDING: "Devolução em processamento no provedor",
  DISPATCH_UNCERTAIN: "Envio da devolução em conferência", REVIEW_REQUIRED: "Devolução precisa de conferência adicional",
  REFUND_DONE_ADJUSTMENT_PENDING: "Devolução integral informada pelo provedor; ajuste contratual pendente",
};
const money = (value: string) => new Intl.NumberFormat("pt-BR", { style: "currency", currency: "BRL" }).format(Number(value));
const date = (value: string) => new Date(value).toLocaleString("pt-BR");
async function readGuarantee() {
  const result = await api.get<BillingGuarantee>("/billing/guarantee");
  if (!result || !Array.isArray(result.items) || !(result.state in MESSAGE)) throw new Error("Guarantee unavailable");
  return result;
}

export function BillingGuaranteePanel({ stepUp, onRequested }: Props) {
  const [quote, setQuote] = useState<BillingGuarantee | null>(null);
  const [loading, setLoading] = useState(true);
  const [review, setReview] = useState<{ fingerprint: string; key: string } | null>(null);
  const [accepted, setAccepted] = useState(false);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const inFlight = useRef(false);
  useEffect(() => {
    let active = true;
    readGuarantee().then(value => { if (active) setQuote(value); })
      .catch(() => { if (active) setError("Não foi possível consultar a garantia comercial."); })
      .finally(() => { if (active) setLoading(false); });
    return () => { active = false; };
  }, []);
  async function refresh() {
    if (inFlight.current) return;
    setLoading(true); setError(null); setReview(null); setAccepted(false);
    try { setQuote(await readGuarantee()); }
    catch { setError("Não foi possível consultar a garantia comercial."); }
    finally { setLoading(false); }
  }
  async function confirm() {
    if (!review || !accepted || !stepUp.ready || inFlight.current) return;
    inFlight.current = true; setBusy(true); setError(null);
    try {
      const result = await api.post<BillingGuarantee>("/billing/guarantee",
        { fingerprint: review.fingerprint, accept: true }, { idempotencyKey: review.key, headers: stepUp.headers() });
      setQuote(result); setReview(null); setAccepted(false); stepUp.consumePresentedToken(); onRequested();
    } catch (err) {
      stepUp.noteError(err);
      setError(err instanceof ApiClientError && err.status < 500 ? err.message
        : "Pedido ainda não confirmado. Reutilize esta confirmação para consultar a mesma solicitação.");
    } finally { inFlight.current = false; setBusy(false); }
  }
  return <Card>
    <h2>Garantia do primeiro pagamento</h2>
    {loading ? <Spinner label="Consultando garantia" /> : <>
      {quote ? <>
        <p role={["REQUESTED", "PROCESSING", "FINANCIALLY_RESOLVED"].includes(quote.state) ? "status" : undefined}>{MESSAGE[quote.state]}</p>
        {quote.first_paid_at ? <p>Primeiro pagamento verificado: {date(quote.first_paid_at)}.</p> : null}
        {quote.deadline ? <p>Prazo da garantia comercial: {date(quote.deadline)}.</p> : null}
        {quote.paid_amount !== null ? <p>Pagamentos considerados nesta revisão: {money(quote.paid_amount)}. Este total não confirma um valor já devolvido.</p> : null}
        {quote.items.map(item => <p key={item.billing_id}>Pagamento de {date(item.paid_at)}: {money(item.amount)}.</p>)}
        {quote.items.some(item => item.mode === "SIMULATOR") ? <p>Simulação: nenhuma movimentação de dinheiro real.</p> : null}
        {["REQUESTED", "PROCESSING", "FINANCIALLY_RESOLVED"].includes(quote.state) ? <>
          <p style={{ overflowWrap: "anywhere" }}>Protocolo: {quote.request_id}. Recebido em {quote.requested_at ? date(quote.requested_at) : "conferência"}.</p>
          {quote.state === "FINANCIALLY_RESOLVED" ? <>
            <p>Encerramento financeiro{quote.financial_resolved_at ? ` em ${date(quote.financial_resolved_at)}` : ""}. Uma contratação nova exige novo aceite e pagamento.</p>
            <p>O documento fiscal de ajuste continua pendente de conferência. Este encerramento não confirma sua emissão.</p>
          </> : quote.state === "REQUESTED" ? <p>O tratamento deve ser iniciado em até 2 dias úteis. A disponibilização da devolução depende do meio de pagamento e do provedor.</p>
            : <p>Tratamento iniciado{quote.processing_started_at ? ` em ${date(quote.processing_started_at)}` : ""}. A disponibilização da devolução depende do meio de pagamento e do provedor.</p>}
          {quote.processing_review_required ? <p>Há pagamentos ou ajustes que precisam de conferência adicional.</p> : null}
          {quote.refund_progress?.map(item => <section key={item.billing_id} aria-label="Andamento de uma devolução">
            <p>{REFUND_PROGRESS[item.state] ?? "Devolução em conferência"}.</p>
            <p>Pagamento: {money(item.paid_amount)}. Devolução concluída registrada: {item.completed_amount !== null ? money(item.completed_amount) : "não confirmada"}.</p>
          </section>)}
        </> : null}
        {!review && quote.state === "ELIGIBLE" && quote.fingerprint ? <Button disabled={busy} onClick={() => {
          setReview({ fingerprint: quote.fingerprint!, key: crypto.randomUUID() }); setAccepted(false); setError(null);
        }}>Revisar solicitação de garantia</Button> : null}
      </> : null}
      {review ? <section aria-label="Confirmar solicitação de garantia">
        <p>A garantia abrange os valores CampaIA pagos no intervalo considerado, inclusive excedente pago. Não inclui gastos de mídia cobrados diretamente por terceiros. Se houver excedente autorizado e entregue ainda não pago, ele será conferido no fechamento final.</p>
        <label><input type="checkbox" checked={accepted} disabled={busy} onChange={event => setAccepted(event.target.checked)} /> Solicito a garantia e entendo que o acesso pago será encerrado imediatamente.</label>
        <Button disabled={busy || !accepted || !stepUp.ready} onClick={confirm}>Confirmar solicitação de garantia</Button>
        <Button variant="secondary" disabled={busy} onClick={() => setReview(null)}>Voltar</Button>
      </section> : null}
      <Button variant="secondary" disabled={busy} onClick={refresh}>Atualizar garantia</Button>
    </>}
    {error ? <ErrorState title="Garantia não confirmada" description={error} /> : null}
  </Card>;
}
