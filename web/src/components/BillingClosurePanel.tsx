"use client";
import { useEffect, useRef, useState } from "react";
import type { BillingClosure } from "@/contracts/types";
import type { useAdministrativeStepUp } from "@/hooks/useAdministrativeStepUp";
import { api, ApiClientError } from "@/lib/api/client";
import { Button } from "./Button";
import { Card } from "./Card";
import { ErrorState } from "./ErrorState";
import { Spinner } from "./Spinner";

type Props = { stepUp: ReturnType<typeof useAdministrativeStepUp>; onClosed: () => void };
const money = (value: string) => new Intl.NumberFormat("pt-BR", { style: "currency", currency: "BRL" }).format(Number(value));
const MESSAGE: Record<BillingClosure["state"], string> = {
  UNAVAILABLE: "Não há ciclo pago disponível para este fechamento.",
  PENDING_USAGE: "Há gerações pendentes. O fechamento aguarda conclusão ou conciliação.",
  NO_CHARGE: "Não há excedente final a cobrar.",
  MINIMUM_UNAVAILABLE: "O limite mínimo de pagamento precisa de conferência antes do fechamento.",
  ABSORBABLE: "O residual está abaixo do mínimo validado do provedor. A FM o absorve no encerramento, sem nova fatura.",
  ABSORBED: "Residual absorvido pela FM. Nenhum pagamento foi registrado por essa absorção.",
  INVOICE_REQUIRED: "Há excedente autorizado e entregue a quitar. O fechamento não inclui outra mensalidade.",
  INVOICED: "Fatura final registrada no histórico. A quitação depende da confirmação do pagamento.",
  SETTLED: "Excedente final quitado. A reativação ainda exige uma nova contratação paga.",
  RECONCILIATION_REQUIRED: "Este consumo já está vinculado a outra obrigação. Concilie antes de qualquer nova cobrança.",
};
export function BillingClosurePanel({ stepUp, onClosed }: Props) {
  const [closure, setClosure] = useState<BillingClosure | null>(null);
  const [loading, setLoading] = useState(true);
  const [review, setReview] = useState<{ fingerprint: string; key: string } | null>(null);
  const [accepted, setAccepted] = useState(false);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const inFlight = useRef(false);
  useEffect(() => {
    let active = true;
    api.get<BillingClosure>("/billing/closure").then(value => { if (active) setClosure(value); })
      .catch(() => { if (active) setError("Não foi possível consultar o fechamento."); })
      .finally(() => { if (active) setLoading(false); });
    return () => { active = false; };
  }, []);
  async function refresh() {
    if (busy) return;
    setLoading(true); setError(null); setReview(null); setAccepted(false);
    try { setClosure(await api.get<BillingClosure>("/billing/closure")); onClosed(); }
    catch { setError("Não foi possível atualizar o fechamento."); }
    finally { setLoading(false); }
  }
  async function confirm() {
    if (!review || !accepted || !stepUp.ready || inFlight.current) return;
    inFlight.current = true; setBusy(true); setError(null);
    try {
      const result = await api.post<BillingClosure>("/billing/closure", { fingerprint: review.fingerprint, accept: true },
        { idempotencyKey: review.key, headers: stepUp.headers() });
      setClosure(result); setReview(null); stepUp.consumePresentedToken(); onClosed();
    } catch (err) {
      stepUp.noteError(err);
      setError(err instanceof ApiClientError && err.status < 500 ? err.message
        : "Fechamento ainda não confirmado. Reutilize esta confirmação para consultar a mesma solicitação.");
    } finally { inFlight.current = false; setBusy(false); }
  }
  return <Card>
    <h2>Fechamento do consumo final</h2>
    {loading ? <Spinner label="Consultando fechamento" /> : <>
      {closure ? <>
        <p>{MESSAGE[closure.state]}</p>
        {closure.amount !== null ? <p>Consumo adicional entregue: {money(closure.amount)}.</p> : null}
        {closure.mode === "SIMULATOR" ? <p>Simulação: nenhuma movimentação de dinheiro real.</p> : closure.mode === "SANDBOX" ? <p>Ambiente de teste.</p> : null}
        {!review && closure.fingerprint && ["ABSORBABLE", "INVOICE_REQUIRED"].includes(closure.state) ?
          <Button disabled={busy} onClick={() => { setReview({ fingerprint: closure.fingerprint!, key: crypto.randomUUID() }); setAccepted(false); }}>Revisar fechamento final</Button> : null}
      </> : null}
      {review ? <section aria-label="Confirmar fechamento final">
        <label><input type="checkbox" checked={accepted} disabled={busy} onChange={event => setAccepted(event.target.checked)} /> Conferi o consumo final e seu tratamento, sem nova mensalidade.</label>
        <Button disabled={busy || !accepted || !stepUp.ready} onClick={confirm}>{busy ? "Confirmando…" : "Confirmar fechamento final"}</Button>
        <Button variant="secondary" disabled={busy} onClick={() => setReview(null)}>Voltar</Button>
      </section> : null}
      <Button variant="secondary" disabled={busy} onClick={refresh}>Atualizar fechamento</Button>
    </>}
    {error ? <ErrorState title="Fechamento não confirmado" description={error} /> : null}
  </Card>;
}
