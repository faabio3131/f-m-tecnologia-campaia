"use client";

import { useRef, useState, type FormEvent } from "react";
import type { BillingPlan, BillingSubscription, BillingSubscriptionInput } from "@/contracts/types";
import type { useAdministrativeStepUp } from "@/hooks/useAdministrativeStepUp";
import { api, ApiClientError } from "@/lib/api/client";
import { Button } from "./Button";
import { Card } from "./Card";
import { ErrorState } from "./ErrorState";
import { Input } from "./Input";
import { StatusPanel } from "./StatusPanel";
import styles from "./BillingSubscriptionSetup.module.css";

type Confirmation = { key: string; body: BillingSubscriptionInput; plan: BillingPlan };
type Props = {
  plans: BillingPlan[];
  stepUp: ReturnType<typeof useAdministrativeStepUp>;
  onCreated: (subscription: BillingSubscription) => void;
};

export function BillingSubscriptionSetup({ plans, stepUp, onCreated }: Props) {
  const [planId, setPlanId] = useState("");
  const [document, setDocument] = useState("");
  const [trial, setTrial] = useState(false);
  const [confirmation, setConfirmation] = useState<Confirmation | null>(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const inFlight = useRef(false);
  const selected = plans.find((plan) => plan.plan_id === planId);

  function review(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!selected || !document.trim() || !selected.fingerprint) return;
    setError(null);
    setConfirmation({ key: crypto.randomUUID(), plan: selected, body: {
      plan_id: selected.plan_id,
      customer_document: document.trim(),
      start_trial: Boolean(trial && selected.trial_days),
      initial_only: true,
      expected_plan_fingerprint: selected.fingerprint,
    } });
  }

  async function confirm() {
    if (!confirmation || inFlight.current || !stepUp.ready) return;
    inFlight.current = true;
    setBusy(true);
    setError(null);
    try {
      const result = await api.put<BillingSubscription>("/billing/subscription", confirmation.body,
        { idempotencyKey: confirmation.key, headers: stepUp.headers() });
      stepUp.consumePresentedToken();
      setDocument("");
      onCreated(result);
    } catch (failure) {
      stepUp.noteError(failure);
      setError(failure instanceof ApiClientError && failure.status < 500
        ? failure.message
        : "Resultado não confirmado. Tente novamente nesta confirmação para consultar a mesma solicitação.");
    } finally {
      inFlight.current = false;
      setBusy(false);
    }
  }

  return <Card>
    <h2 className={styles.title}>Configurar assinatura</h2>
    {confirmation ? <section aria-label="Confirmar contratação">
      <StatusPanel title="Revise sua seleção" items={[
        { label: "Plano selecionado", value: confirmation.plan.name },
        { label: "Mensalidade", value: new Intl.NumberFormat("pt-BR", { style: "currency", currency: confirmation.plan.currency, maximumFractionDigits: 20 }).format(Number(confirmation.plan.monthly_price)) },
        { label: "Créditos mensais incluídos", value: confirmation.plan.included_credits },
        { label: "Entrada", value: confirmation.body.start_trial ? `Período de teste: ${confirmation.plan.trial_days} dias` : "Assinatura aguardando pagamento" },
      ]} />
      <p>{confirmation.body.start_trial
        ? "O teste começa após a confirmação e termina na data informada pela assinatura."
        : "A seleção do plano registra a assinatura aguardando pagamento. Os recursos pagos serão liberados após a confirmação financeira."}</p>
      <p>Esta confirmação não emite cobrança. O fluxo de pagamento ainda está em conclusão.</p>
      <div className={styles.actions}>
        <Button disabled={busy || !stepUp.ready} onClick={confirm}>{busy ? "Enviando…" : "Confirmar contratação"}</Button>
        <Button variant="secondary" disabled={busy} onClick={() => { setConfirmation(null); setError(null); }}>Voltar à seleção</Button>
      </div>
    </section> : <form onSubmit={review} className={styles.form}>
      <label htmlFor="initial-billing-plan">Plano</label>
      <select id="initial-billing-plan" required value={planId} onChange={(event) => { setPlanId(event.target.value); setTrial(false); }} className={styles.select}>
        <option value="">Selecione um plano</option>
        {plans.map((plan) => <option key={plan.plan_id} value={plan.plan_id}>{plan.name}</option>)}
      </select>
      <Input label="CPF ou CNPJ do titular" required maxLength={64} autoComplete="off" value={document} onChange={(event) => setDocument(event.target.value)} />
      <p className={styles.description}>Informe o documento do titular da cobrança, conforme cadastrado no provedor de pagamento.</p>
      {selected?.trial_days ? <label className={styles.choice}>
        <input type="checkbox" checked={trial} onChange={(event) => setTrial(event.target.checked)} />
        Iniciar período de teste de {selected.trial_days} dias
      </label> : null}
      <Button type="submit" disabled={!selected?.fingerprint || !document.trim()}>Revisar contratação</Button>
    </form>}
    {error ? <ErrorState title="Contratação não confirmada" description={error} /> : null}
  </Card>;
}
