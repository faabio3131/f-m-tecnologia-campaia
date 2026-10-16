"use client";
import { useEffect, useRef, useState } from "react";
import type { BillingRenewal } from "@/contracts/types";
import type { useAdministrativeStepUp } from "@/hooks/useAdministrativeStepUp";
import { api, ApiClientError } from "@/lib/api/client";
import { Button } from "./Button";
import { Card } from "./Card";
import { ErrorState } from "./ErrorState";
import { Spinner } from "./Spinner";

type Props = { stepUp: ReturnType<typeof useAdministrativeStepUp> };
const money = (value: string) => new Intl.NumberFormat("pt-BR", { style: "currency", currency: "BRL" }).format(Number(value));
async function read() {
  const result = await api.get<BillingRenewal>("/billing/renewal");
  if (!result || typeof result.enabled !== "boolean" || typeof result.fingerprint !== "string") throw new Error("Renewal unavailable");
  return result;
}
export function BillingRenewalPanel({ stepUp }: Props) {
  const [quote, setQuote] = useState<BillingRenewal | null>(null);
  const [loading, setLoading] = useState(true);
  const [review, setReview] = useState<{ enabled: boolean; fingerprint: string; key: string } | null>(null);
  const [accepted, setAccepted] = useState(false);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const inFlight = useRef(false);
  useEffect(() => {
    let active = true;
    read().then(value => { if (active) setQuote(value); })
      .catch(() => { if (active) setError("Não foi possível consultar a emissão recorrente."); })
      .finally(() => { if (active) setLoading(false); });
    return () => { active = false; };
  }, []);
  async function refresh() {
    if (inFlight.current) return;
    setLoading(true); setError(null); setReview(null); setAccepted(false);
    try { setQuote(await read()); }
    catch { setError("Não foi possível consultar a emissão recorrente."); }
    finally { setLoading(false); }
  }
  async function confirm() {
    if (!review || !accepted || !stepUp.ready || inFlight.current) return;
    inFlight.current = true; setBusy(true); setError(null);
    try {
      const result = await api.put<BillingRenewal>("/billing/renewal",
        { enabled: review.enabled, fingerprint: review.fingerprint },
        { idempotencyKey: review.key, headers: stepUp.headers() });
      setQuote(result); setReview(null); setAccepted(false); stepUp.consumePresentedToken();
    } catch (err) {
      stepUp.noteError(err);
      setError(err instanceof ApiClientError && err.status < 500 ? err.message
        : "Alteração ainda não confirmada. Reutilize esta confirmação para consultar a mesma solicitação.");
    } finally { inFlight.current = false; setBusy(false); }
  }
  function prepare(enabled: boolean) {
    if (!quote) return;
    setReview({ enabled, fingerprint: quote.fingerprint, key: crypto.randomUUID() }); setAccepted(false); setError(null);
  }
  return <Card>
    <h2>Emissão das próximas faturas</h2>
    {loading ? <Spinner label="Consultando emissão recorrente" /> : <>
      {quote ? <>
        <p role="status">{quote.enabled && quote.valid ? "Emissão recorrente autorizada para estas condições."
          : quote.enabled ? "A autorização registrada precisa de nova revisão das condições." : "Emissão recorrente não autorizada."}</p>
        <p>Plano {quote.plan_name}: mensalidade de {money(quote.monthly_price)}. No aniversário, a fatura reúne a próxima mensalidade antecipada e o excedente autorizado e entregue do período anterior.</p>
        <p>Esta autorização permite gerar faturas. Cada pagamento é feito no meio escolhido; ela não autoriza débito automático. O trial não é convertido automaticamente em plano pago.</p>
        {quote.next_due_at ? <p>Próximo aniversário: {new Date(quote.next_due_at).toLocaleString("pt-BR")}.</p> : null}
        {quote.mode === "SIMULATOR" ? <p>Simulação: nenhuma movimentação de dinheiro real.</p> : null}
        {!quote.can_enable ? <p>A emissão depende de contrato pago vigente, sem cancelamento ou pendências de conciliação.</p> : null}
        {!review && quote.can_enable && !(quote.enabled && quote.valid) ?
          <Button disabled={busy} onClick={() => prepare(true)}>Revisar autorização de emissão</Button> : null}
        {!review && quote.enabled ?
          <Button variant="secondary" disabled={busy} onClick={() => prepare(false)}>Desativar emissão recorrente</Button> : null}
      </> : null}
      {review ? <section aria-label="Confirmar autorização de emissão">
        <p>{review.enabled ? "A autorização vale para as condições e o contrato apresentados. Mudanças de plano ou ambiente exigem nova revisão. O excedente continua sujeito ao consentimento e teto próprios."
          : "Desativar impede novos envios recorrentes. Uma fatura já emitida ou com envio iniciado continua no histórico e exige conferência; ela não é cancelada automaticamente."}</p>
        <label><input type="checkbox" checked={accepted} disabled={busy} onChange={event => setAccepted(event.target.checked)} />
          {review.enabled ? "Autorizo a emissão das próximas faturas nas condições apresentadas." : "Confirmo a desativação da emissão recorrente."}
        </label>
        <Button disabled={busy || !accepted || !stepUp.ready} onClick={confirm}>Confirmar alteração da emissão</Button>
        <Button variant="secondary" disabled={busy} onClick={() => setReview(null)}>Voltar</Button>
      </section> : null}
      <Button variant="secondary" disabled={busy} onClick={refresh}>Atualizar emissão recorrente</Button>
    </>}
    {error ? <ErrorState title="Emissão recorrente não confirmada" description={error} /> : null}
  </Card>;
}
