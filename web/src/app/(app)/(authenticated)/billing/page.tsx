"use client";

import { useEffect, useRef, useState } from "react";
import { AdministrativeStepUpCard } from "@/components/AdministrativeStepUpCard";
import { BillingSubscriptionSetup } from "@/components/BillingSubscriptionSetup";
import { CommercialLifecycleActions } from "@/components/CommercialLifecycleActions";
import { BillingCheckoutPanel } from "@/components/BillingCheckoutPanel";
import { BillingUsagePanel } from "@/components/BillingUsagePanel";
import { BillingChargeHistoryPanel } from "@/components/BillingChargeHistoryPanel";
import { Button } from "@/components/Button";
import { Card } from "@/components/Card";
import { EmptyState } from "@/components/EmptyState";
import { ErrorState } from "@/components/ErrorState";
import { PageContainer } from "@/components/PageContainer";
import { PageHeader } from "@/components/PageHeader";
import { Spinner } from "@/components/Spinner";
import { StatusPanel } from "@/components/StatusPanel";
import type { BillingPlan, BillingSubscription } from "@/contracts/types";
import { useAdministrativeStepUp } from "@/hooks/useAdministrativeStepUp";
import { api, ApiClientError } from "@/lib/api/client";
import { useAuth } from "@/providers/AuthProvider";
import styles from "./page.module.css";

type Action = { kind: "cancel" | "reactivate" | "change-plan"; label: string; target?: string; key: string };
const STATUS: Record<BillingSubscription["status"], string> = {
  ACTIVE: "Ativa", TRIAL: "Período de teste", PENDING_PAYMENT: "Aguardando pagamento",
  PAST_DUE: "Pagamento em atraso", EXPIRED: "Expirada", CANCELED: "Cancelada",
};
const date = (value?: string | null) => value ? new Date(value).toLocaleString("pt-BR") : "Não definido";
const money = (value: string, currency: string) => new Intl.NumberFormat("pt-BR", { style: "currency", currency, maximumFractionDigits: 20 }).format(Number(value));

export default function BillingPage() {
  const { session, me } = useAuth();
  // A troca de contexto descarta dados, confirmacao e chave da operacao anterior.
  return <BillingContent key={`${session?.tenant_id}:${session?.business_unit_id}:${session?.user_id}`} canManage={Boolean(me?.roles?.some((role) => ["OWNER", "FINANCE"].includes(role)))} />;
}

function BillingContent({ canManage }: { canManage: boolean }) {
  const [subscription, setSubscription] = useState<BillingSubscription | null>(null);
  const [plans, setPlans] = useState<BillingPlan[]>([]);
  const [loading, setLoading] = useState(true);
  const [loadError, setLoadError] = useState(false);
  const [catalogError, setCatalogError] = useState(false);
  const [action, setAction] = useState<Action | null>(null);
  const [busy, setBusy] = useState(false);
  const [actionError, setActionError] = useState<string | null>(null);
  const [historyVersion, setHistoryVersion] = useState(0);
  const [success, setSuccess] = useState<string | null>(null);
  const inFlight = useRef(false);
  const stepUp = useAdministrativeStepUp();

  useEffect(() => {
    let active = true;
    Promise.allSettled([
      api.get<BillingSubscription>("/billing/subscription"),
      api.get<{ items: BillingPlan[] }>("/billing/plans"),
    ]).then(([sub, catalog]) => {
      if (!active) return;
      if (sub.status === "fulfilled") setSubscription(sub.value);
      else if (!(sub.reason instanceof ApiClientError && sub.reason.status === 404)) setLoadError(true);
      if (catalog.status === "fulfilled") setPlans(catalog.value.items);
      else setCatalogError(true);
      setLoading(false);
    });
    return () => { active = false; };
  }, []);

  function prepare(kind: Action["kind"], label: string, target?: string) {
    setAction({ kind, label, target, key: crypto.randomUUID() });
    setActionError(null);
    setSuccess(null);
  }

  async function confirm() {
    if (!action || inFlight.current || !stepUp.ready) return;
    inFlight.current = true;
    setBusy(true);
    setActionError(null);
    try {
      const result = await api.post<BillingSubscription>(`/billing/subscription/${action.kind}`,
        action.kind === "change-plan" ? { target_plan_id: action.target } : undefined,
        { idempotencyKey: action.key, headers: stepUp.headers() });
      setSubscription(result);
      stepUp.consumePresentedToken();
      setAction(null);
      setSuccess("Solicitação registrada. Confira o estado atualizado da assinatura.");
    } catch (error) {
      stepUp.noteError(error);
      // A mesma confirmacao conserva a chave apos timeout/falha de rede para replay seguro.
      setActionError(error instanceof ApiClientError && error.status < 500
        ? error.message : "Não foi possível confirmar o resultado. Tente novamente nesta confirmação para consultar a mesma operação.");
    } finally {
      inFlight.current = false;
      setBusy(false);
    }
  }

  const terms = subscription?.commercial_terms;
  return <PageContainer>
    <PageHeader title="Plano e cobrança" description="Assinatura e condições comerciais da sua organização." />
    {loading ? <Spinner label="Carregando assinatura" /> : loadError ?
      <ErrorState title="Não foi possível consultar a assinatura" description="Verifique sua permissão de cobrança e tente recarregar a página." /> : <>
      {canManage ? <AdministrativeStepUpCard {...stepUp} description="Contratação, alterações de plano, cancelamento e reativação exigem autenticação Google recente." onError={setActionError} /> : null}
      {subscription && terms ? <>
        <Card><StatusPanel title="Assinatura atual" items={[
          { label: "Plano", value: subscription.plan_name },
          { label: "Situação", value: STATUS[subscription.status] },
          { label: "Mensalidade contratada", value: money(terms.monthly_price, terms.currency) },
          { label: "Créditos incluídos por mês", value: terms.included_credits },
          { label: "Preço por crédito extra", value: money(terms.extra_credit_unit_price, terms.currency) },
          { label: "Acesso aos recursos", value: subscription.entitlement_access_active ? "Liberado" : "Bloqueado" },
          ...(subscription.trial_ends_at ? [{ label: "Fim do período de teste", value: date(subscription.trial_ends_at) }] : []),
          ...(subscription.pending_plan_name ? [{ label: terms.credit_policy ? "Troca agendada" : "Troca aguardando pagamento", value: subscription.pending_plan_name }] : []),
          ...(subscription.reactivation_requested_at ? [{ label: "Reativação", value: "Aguardando pagamento confirmado" }] : []),
        ]} /></Card>
        {subscription.status === "PAST_DUE" ? <Card><StatusPanel title="Pagamento em atraso" items={[
          { label: "Em atraso desde", value: date(subscription.past_due_at) },
          { label: "Fim da carência", value: date(subscription.grace_period_ends_at) },
          { label: "Dentro da carência", value: subscription.past_due_in_grace ? "Sim" : "Não" },
          { label: "Lembretes enviados", value: String(subscription.dunning_reminders_sent ?? 0) },
          { label: "Próximo lembrete previsto", value: date(subscription.next_dunning_reminder_at) },
        ]} /></Card> : null}
        <Card><StatusPanel title="Recursos contratados" items={[
          { label: "Limite de usuários", value: String(subscription.entitlements?.max_users ?? "Não configurado") },
          { label: "Limite de campanhas ativas", value: String(subscription.entitlements?.max_active_campaigns ?? "Não configurado") },
          { label: "Canais", value: subscription.entitlements?.channels.join(", ") || "Nenhum configurado" },
        ]} /></Card>
        {terms.credit_policy && canManage ? <BillingCheckoutPanel key={`${subscription.status}:${subscription.plan_id}:${subscription.activated_at}:${subscription.cancel_at_period_end}:${subscription.pending_plan_id}`} stepUp={stepUp} onIssued={() => { setHistoryVersion(value => value + 1); void api.get<BillingSubscription>("/billing/subscription").then(setSubscription).catch(() => undefined); }} /> : null}
        <BillingUsagePanel key={`${subscription.status}:${subscription.plan_id}:${subscription.activated_at}:${subscription.cancel_at_period_end}:${subscription.pending_plan_id}`} canManage={canManage} stepUp={stepUp} />
        {canManage && !terms.credit_policy ? <>
          <Card><h2 className={styles.title}>Gerenciar assinatura</h2>
            <div className={styles.actions}>
              {subscription.status !== "CANCELED" && terms.cancellation_mode === "IMMEDIATE" ?
                <Button variant="secondary" disabled={busy || action !== null} onClick={() => prepare("cancel", "Cancelar assinatura imediatamente")}>Cancelar assinatura</Button> : null}
              {subscription.status === "CANCELED" && terms.reactivation_mode === "PAYMENT_REQUIRED" && terms.reactivation_billing_mode === "CURRENT_PLAN_FULL_CYCLE" ?
                <Button disabled={busy || action !== null} onClick={() => prepare("reactivate", "Solicitar reativação com pagamento de um ciclo completo do plano atual")}>Solicitar reativação</Button> : null}
              {subscription.status === "ACTIVE" && !subscription.pending_plan_id ? terms.plan_changes.map((rule) => {
                const target = plans.find((plan) => plan.plan_id === rule.target_plan_id);
                return target && rule.billing_mode === "TARGET_PLAN_FULL_CYCLE" ? <Button key={target.plan_id} disabled={busy || action !== null} onClick={() => prepare("change-plan", `Solicitar ${rule.kind === "UPGRADE" ? "upgrade" : "downgrade"} para ${target.name}: ${money(target.monthly_price, target.currency)} por um ciclo completo, com ativação após pagamento`, target.plan_id)}>Mudar para {target.name}</Button> : null;
              }) : null}
            </div>
            <p>Trocas de plano e reativações liberam recursos após o pagamento confirmado. O cancelamento imediato bloqueia o acesso aos recursos contratados.</p>
          </Card>
        </> : terms.credit_policy && canManage ? <CommercialLifecycleActions subscription={subscription} plans={plans} stepUp={stepUp} onUpdated={setSubscription} /> : null}
      </> : <EmptyState title="Nenhuma assinatura configurada" description="Sua organização ainda não possui uma assinatura." />}
      {!subscription && canManage && !catalogError && plans.length > 0 ?
        <BillingSubscriptionSetup plans={plans} stepUp={stepUp} onCreated={setSubscription} /> : null}
      {action ? <Card><section aria-label="Confirmar alteração de assinatura">
        <h2 className={styles.title}>{action.label}</h2>
        <p>Confirme para registrar esta alteração na assinatura da organização.</p>
        <div className={styles.actions}>
          <Button disabled={busy || !stepUp.ready} onClick={confirm}>{busy ? "Enviando…" : "Confirmar alteração"}</Button>
          <Button variant="secondary" disabled={busy} onClick={() => setAction(null)}>Voltar</Button>
        </div>
      </section></Card> : null}
      {success ? <p role="status">{success}</p> : null}
      {actionError ? <ErrorState title="Alteração não confirmada" description={actionError} /> : null}
      {stepUp.stepUpMessage ? <p role="alert">{stepUp.stepUpMessage}</p> : null}
      <BillingChargeHistoryPanel key={historyVersion} />
      <Card><h2 className={styles.title}>Planos disponíveis neste ambiente</h2>
        {catalogError ? <ErrorState title="Catálogo de planos indisponível" description="As condições comerciais ainda não estão disponíveis para consulta neste ambiente." /> : plans.length === 0 ? <p>Nenhum plano configurado.</p> : plans.map((plan) => <StatusPanel key={plan.plan_id} title={plan.name} items={[
          { label: "Mensalidade", value: money(plan.monthly_price, plan.currency) },
          { label: "Créditos incluídos", value: plan.included_credits },
          { label: "Crédito extra", value: money(plan.extra_credit_unit_price, plan.currency) },
          { label: "Período de teste", value: plan.trial_days ? `${plan.trial_days} dias` : "Não configurado" },
        ]} />)}
      </Card>
    </>}
  </PageContainer>;
}
