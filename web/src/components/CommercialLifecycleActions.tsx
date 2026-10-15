"use client";
import { useRef, useState } from "react";
import type { BillingPlan, BillingSubscription } from "@/contracts/types";
import type { useAdministrativeStepUp } from "@/hooks/useAdministrativeStepUp";
import { api, ApiClientError } from "@/lib/api/client";
import { Button } from "./Button";
import { Card } from "./Card";
import { ErrorState } from "./ErrorState";

type Props = { subscription: BillingSubscription; plans: BillingPlan[];
  stepUp: ReturnType<typeof useAdministrativeStepUp>; onUpdated: (sub: BillingSubscription) => void };
type Action = { path: "cancel" | "reactivate" | "change-plan" | "undo-plan"; label: string;
  key: string; body?: { immediate?: boolean; target_plan_id?: string; expected_plan_fingerprint?: string } };
const date = (value: string) => new Date(value).toLocaleString("pt-BR");
const money = (value: string) => new Intl.NumberFormat("pt-BR", { style: "currency", currency: "BRL" }).format(Number(value));

export function CommercialLifecycleActions({ subscription: sub, plans, stepUp, onUpdated }: Props) {
  const [action, setAction] = useState<Action | null>(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [success, setSuccess] = useState(false);
  const inFlight = useRef(false);
  const terms = sub.commercial_terms;
  const closed = sub.status === "CANCELED" || sub.status === "EXPIRED";
  function prepare(path: Action["path"], label: string, body?: Action["body"]) {
    setAction({ path, label, body, key: crypto.randomUUID() }); setError(null); setSuccess(false);
  }
  async function confirm() {
    if (!action || inFlight.current || !stepUp.ready) return;
    inFlight.current = true; setBusy(true); setError(null);
    try {
      const updated = await api.post<BillingSubscription>(`/billing/subscription/${action.path}`, action.body,
        { idempotencyKey: action.key, headers: stepUp.headers() });
      onUpdated(updated); stepUp.consumePresentedToken(); setAction(null); setSuccess(true);
    } catch (err) {
      stepUp.noteError(err);
      setError(err instanceof ApiClientError && err.status < 500 ? err.message
        : "Resultado não confirmado. Reutilize esta confirmação para consultar a mesma solicitação.");
    } finally { inFlight.current = false; setBusy(false); }
  }
  return <Card>
    <h2>Gerenciar assinatura</h2>
    {sub.paid_period_ends_at ? <p>Fim do período pago: {date(sub.paid_period_ends_at)}.</p> : null}
    {sub.cancel_at_period_end && !closed ? <>
      <p>Encerramento agendado para {date(sub.cancel_at_period_end)}. O acesso continua até essa data.</p>
      <Button disabled={busy || action !== null} onClick={() => prepare("reactivate", "Manter assinatura, removendo o encerramento agendado sem nova cobrança")}>Manter assinatura</Button>
    </> : null}
    {sub.pending_plan_id ? <>
      <p>Troca para {sub.pending_plan_name} em {sub.pending_plan_effective_at ? date(sub.pending_plan_effective_at) : "data a confirmar"}, condicionada ao pagamento.</p>
      {sub.pending_plan_entitlements ? <p>Novas inclusões respeitam também os limites futuros: {sub.pending_plan_entitlements.max_users} usuários e {sub.pending_plan_entitlements.max_active_campaigns} campanhas ativas.</p> : null}
      <Button disabled={busy || action !== null} onClick={() => prepare("undo-plan", "Desistir da troca agendada antes do fechamento da obrigação")}>Desistir da troca agendada</Button>
    </> : null}
    {sub.status === "ACTIVE" && !sub.pending_plan_id && !sub.cancel_at_period_end ? terms.plan_changes.filter(rule => rule.activation === "NEXT_ANNIVERSARY").map(rule => {
      const target = plans.find(plan => plan.plan_id === rule.target_plan_id);
      return target ? <Button key={target.plan_id} disabled={busy || action !== null} onClick={() => prepare("change-plan",
        `Agendar ${target.name} para o próximo aniversário por ${money(target.monthly_price)} por ciclo, sem cobrança proporcional`,
        { target_plan_id: target.plan_id, expected_plan_fingerprint: target.fingerprint })}>Agendar {target.name}</Button> : null;
    }) : null}
    {!closed && !sub.cancel_at_period_end && terms.cancellation_mode === "PERIOD_END" ? <Button variant="secondary" disabled={busy || action !== null} onClick={() => prepare("cancel", "Cancelar a renovação ao fim do período já pago, preservando valores já consumidos")}>Cancelar renovação</Button> : null}
    {!closed ? <Button variant="secondary" disabled={busy || action !== null} onClick={() => prepare("cancel", "Encerrar imediatamente e bloquear novos recursos agora; valores consumidos e direitos de reembolso seguem a política contratada", { immediate: true })}>Encerrar imediatamente</Button> : null}
    {closed && terms.reactivation_mode === "PAYMENT_REQUIRED" ? <Button disabled={busy || action !== null} onClick={() => prepare("reactivate", "Solicitar nova contratação paga, sem novo trial; dívidas anteriores permanecem separadas")}>Solicitar reativação</Button> : null}
    <p>Trocas valem no próximo aniversário e exigem pagamento confirmado. Anúncios externos podem continuar gerando gastos após o encerramento do CampaIA.</p>
    {action ? <section aria-label="Confirmar solicitação de assinatura">
      <p>{action.label}</p>
      <Button disabled={busy || !stepUp.ready} onClick={confirm}>{busy ? "Confirmando…" : "Confirmar solicitação"}</Button>
      <Button variant="secondary" disabled={busy} onClick={() => setAction(null)}>Voltar</Button>
    </section> : null}
    {success ? <p role="status">Solicitação registrada. Confira a situação e as datas atualizadas.</p> : null}
    {error ? <ErrorState title="Solicitação não confirmada" description={error} /> : null}
  </Card>;
}
