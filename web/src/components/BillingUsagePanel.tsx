"use client";

import { useEffect, useRef, useState, type FormEvent } from "react";
import type { BillingUsage, BillingCreditConsent } from "@/contracts/types";
import type { useAdministrativeStepUp } from "@/hooks/useAdministrativeStepUp";
import { api, ApiClientError } from "@/lib/api/client";
import { Button } from "./Button";
import { Card } from "./Card";
import { ErrorState } from "./ErrorState";
import { Input } from "./Input";
import { Spinner } from "./Spinner";
import { StatusPanel } from "./StatusPanel";

const ALERTS: Record<string, string> = {
  INCLUDED_80: "80% da franquia está consumida ou reservada.",
  INCLUDED_100: "A franquia está totalmente consumida ou reservada.",
  EXTRA_CAP_80: "80% do teto adicional está consumido ou reservado.",
  EXTRA_CAP_100: "O teto adicional está totalmente consumido ou reservado.",
};
const money = (value: string) => new Intl.NumberFormat("pt-BR", { style: "currency", currency: "BRL" }).format(Number(value));
type Props = { canManage: boolean; stepUp: ReturnType<typeof useAdministrativeStepUp> };
type Confirmation = { key: string; body: BillingCreditConsent };

export function BillingUsagePanel({ canManage, stepUp }: Props) {
  const [usage, setUsage] = useState<BillingUsage | null>(null);
  const [loading, setLoading] = useState(true);
  const [cap, setCap] = useState("50.00");
  const [confirmation, setConfirmation] = useState<Confirmation | null>(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [success, setSuccess] = useState(false);
  const inFlight = useRef(false);

  useEffect(() => {
    let active = true;
    api.get<BillingUsage>("/billing/usage").then((result) => {
      if (active) setUsage(result);
    }).catch(() => {
      if (active) setError("Não foi possível consultar o consumo.");
    }).finally(() => { if (active) setLoading(false); });
    return () => { active = false; };
  }, []);

  const balance = usage?.balance;
  const cycle = usage?.cycle;
  function review(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!cycle || !balance) return;
    setError(null);
    setSuccess(false);
    setConfirmation({ key: crypto.randomUUID(), body: {
      cap: cap.replace(",", "."), cycle_id: cycle.id,
      policy_version: cycle.policy_version, extra_credit_price: balance.extra_credit_price,
    } });
  }

  async function confirm() {
    if (!confirmation || inFlight.current || !stepUp.ready) return;
    inFlight.current = true;
    setBusy(true);
    setError(null);
    try {
      const result = await api.post<BillingUsage>("/billing/usage/consent", confirmation.body,
        { idempotencyKey: confirmation.key, headers: stepUp.headers() });
      setUsage(result);
      stepUp.consumePresentedToken();
      setConfirmation(null);
      setSuccess(true);
    } catch (err) {
      stepUp.noteError(err);
      setError(err instanceof ApiClientError && err.status < 500 ? err.message
        : "Resultado não confirmado. Tente novamente nesta confirmação para consultar a mesma operação.");
    } finally { inFlight.current = false; setBusy(false); }
  }

  return <Card>
    <h2>Consumo de créditos</h2>
    {loading ? <Spinner label="Carregando consumo" /> : balance && cycle ? <>
      <StatusPanel title={cycle.trial ? "Franquia do período de teste" : "Franquia do ciclo pago"} items={[
        { label: "Início", value: new Date(cycle.starts_at).toLocaleString("pt-BR") },
        { label: "Fim", value: new Date(cycle.ends_at).toLocaleString("pt-BR") },
        { label: "Créditos incluídos", value: String(balance.included_credits) },
        { label: "Entregas consumidas", value: String(balance.consumed_credits) },
        { label: "Créditos reservados", value: String(balance.reserved_credits) },
        { label: "Franquia disponível", value: String(balance.included_available) },
        { label: "Excedente consumido", value: money(balance.extra_consumed_amount) },
        { label: "Teto adicional autorizado", value: money(balance.extra_cap) },
      ]} />
      {!usage?.access_active ? <p>Consulta do saldo registrado. A assinatura atual não permite novas gerações.</p> : null}
      <p>Reservas aguardam entrega ou reconciliação e ainda não são consumo cobrado. A franquia não acumula entre ciclos.</p>
      {usage.alerts.map((alert) => <p role="status" key={alert}>{ALERTS[alert]}</p>)}
      {cycle.trial ? <p>O teste não permite excedente nem conversão paga automática.</p> : canManage && usage?.can_authorize_extras ? <>
        <p>Excedente: {money(balance.extra_credit_price)} por crédito entregue. A autorização permanece até revogação; o teto reinicia a cada ciclo. Não é compra antecipada de créditos.</p>
        {!confirmation ? <form onSubmit={review}>
          <Input label="Teto adicional por ciclo (R$)" type="number" min="0" max="1000000000000" step="0.01" required value={cap} onChange={(event) => setCap(event.target.value)} />
          <p>Informe zero para revogar novas utilizações adicionais. Entregas e reservas já autorizadas permanecem registradas.</p>
          <Button type="submit">Revisar autorização de excedente</Button>
        </form> : <section aria-label="Confirmar autorização de excedente">
          <p>Confirmar teto de {money(confirmation.body.cap)} por ciclo a {money(confirmation.body.extra_credit_price)} por crédito. Política {confirmation.body.policy_version}.</p>
          <Button disabled={busy || !stepUp.ready} onClick={confirm}>{busy ? "Confirmando…" : "Confirmar autorização"}</Button>
          <Button variant="secondary" disabled={busy} onClick={() => setConfirmation(null)}>Voltar</Button>
        </section>}
      </> : null}
    </> : <p>Medição de consumo ainda indisponível</p>}
    {success ? <p role="status">Autorização de excedente registrada.</p> : null}
    {error ? <ErrorState title="Consumo indisponível ou alteração não confirmada" description={error} /> : null}
  </Card>;
}
