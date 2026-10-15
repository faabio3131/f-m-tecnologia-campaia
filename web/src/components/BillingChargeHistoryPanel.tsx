"use client";

import { useEffect, useRef, useState } from "react";
import type { BillingChargeHistory, BillingChargeHistoryItem } from "@/contracts/types";
import { safeBillingInvoiceUrl } from "@/lib/billing";
import type { useAdministrativeStepUp } from "@/hooks/useAdministrativeStepUp";
import { api } from "@/lib/api/client";
import { Button } from "./Button";
import { Card } from "./Card";
import { EmptyState } from "./EmptyState";
import { ErrorState } from "./ErrorState";
import { Spinner } from "./Spinner";
import { StatusPanel } from "./StatusPanel";
import styles from "./BillingChargeHistoryPanel.module.css";

const STATUS: Record<string, string> = {
  PENDING: "Pendente", OVERDUE: "Vencida", CONFIRMED: "Confirmada", FAILED: "Falha ou reversão",
};
const MODES: Record<string, string> = {
  SIMULATOR: "Simulação", SANDBOX: "Sandbox (teste)", PRODUCTION: "Produção",
};
const PURPOSES: Record<string, string> = {
  FINAL_USAGE: "Excedente final", REGULAR: "Assinatura", PLAN_CHANGE: "Troca de plano", REACTIVATION: "Reativação",
};

const REVIEW: Record<string, string> = {
  CANCELLATION_CONFLICT: "Pagamento ou restauração após pedido de retirada",
  MATCHED: "Valor conferido", AMOUNT_MISSING: "Valor recebido não informado",
  AMOUNT_MISMATCH: "Valor recebido divergente", TERMS_MISMATCH: "Valor da fatura alterado",
  REVERSAL_PENDING: "Estorno ou contestação em revisão", STATUS_MISMATCH: "Situação de pagamento divergente",
};
type Props = { canManage?: boolean; stepUp?: ReturnType<typeof useAdministrativeStepUp>; onReconciled?: () => void };

export function BillingChargeHistoryPanel({ canManage = false, stepUp, onReconciled }: Props) {
  const [items, setItems] = useState<BillingChargeHistoryItem[]>([]);
  const [cursor, setCursor] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(false);
  const inFlight = useRef(false);
  const lookupInFlight = useRef(false);
  const lookupKeys = useRef(new Map<string, string>());
  const [lookupBusy, setLookupBusy] = useState(false);
  const [lookupMessage, setLookupMessage] = useState<string | null>(null);
  const [withdrawReview, setWithdrawReview] = useState<{ id: string; fingerprint: string; key: string } | null>(null);
  const [withdrawAccepted, setWithdrawAccepted] = useState(false);

  async function withdraw() {
    if (!canManage || !stepUp?.ready || !withdrawReview || !withdrawAccepted || lookupInFlight.current) return;
    lookupInFlight.current = true; setLookupBusy(true); setLookupMessage(null);
    try {
      await api.post(`/billing/charges/${encodeURIComponent(withdrawReview.id)}/withdraw`,
        { fingerprint: withdrawReview.fingerprint, accept: true },
        { idempotencyKey: withdrawReview.key, headers: stepUp.headers() });
      stepUp.consumePresentedToken(); setWithdrawReview(null); setWithdrawAccepted(false);
      await load(); onReconciled?.();
      setLookupMessage("Retirada da fatura aberta confirmada. Nenhum pagamento ou reembolso foi registrado por esta retirada. Consulte o fechamento do consumo final.");
    } catch (error) {
      stepUp.noteError(error);
      setLookupMessage("Retirada não confirmada. Reutilize esta confirmação para consultar o resultado; uma exclusão incerta não será repetida.");
    } finally { lookupInFlight.current = false; setLookupBusy(false); }
  }

  async function reconcile(id: string) {
    if (!canManage || !stepUp?.ready || lookupInFlight.current) return;
    lookupInFlight.current = true;
    setLookupBusy(true);
    setLookupMessage(null);
    const key = lookupKeys.current.get(id) ?? crypto.randomUUID();
    lookupKeys.current.set(id, key);
    try {
      await api.post(`/billing/charges/${encodeURIComponent(id)}/reconcile`, undefined,
        { idempotencyKey: key, headers: stepUp.headers() });
      lookupKeys.current.delete(id);
      stepUp.consumePresentedToken();
      await load();
      setLookupMessage("Consulta registrada. Confira a situação e o valor informado no histórico.");
      onReconciled?.();
    } catch (error) {
      stepUp.noteError(error);
      setLookupMessage("Não foi possível confirmar a consulta. Tente novamente para consultar a mesma operação.");
    } finally {
      lookupInFlight.current = false;
      setLookupBusy(false);
    }
  }

  async function load(after: string | null = null) {
    if (inFlight.current) return;
    inFlight.current = true;
    setLoading(true);
    setError(false);
    try {
      const result = await api.get<BillingChargeHistory>(`/billing/charges${after ? `?cursor=${encodeURIComponent(after)}` : ""}`);
      setItems((existing) => after ? [...existing, ...result.items] : result.items);
      setCursor(result.next_cursor);
    } catch {
      setError(true);
    } finally {
      inFlight.current = false;
      setLoading(false);
    }
  }

  useEffect(() => {
    let active = true;
    api.get<BillingChargeHistory>("/billing/charges").then((result) => {
      if (!active) return;
      setItems(result.items);
      setCursor(result.next_cursor);
    }).catch(() => {
      if (active) setError(true);
    }).finally(() => {
      if (active) setLoading(false);
    });
    return () => { active = false; };
  }, []);

  return <Card>
    <h2 className={styles.title}>Histórico de cobranças</h2>
    <p className={styles.description}>Situação da última resposta ou notificação registrada, com seu ambiente e horário de recebimento.</p>
    <div className={styles.list}>
      {items.map((item) => {
        const url = item.withdrawal_state ? null : safeBillingInvoiceUrl(item.invoice_url, item.gateway_provider, item.gateway_mode);
        return <article key={item.gateway_charge_id} className={styles.item} aria-label={`Cobrança ${item.billing_id}`}>
          <StatusPanel title={`Competência ${item.competence} · ${item.gateway_charge_id}`} items={[
            { label: "Identificador", value: item.billing_id },
            { label: "Finalidade", value: PURPOSES[item.purpose] ?? item.purpose },
            { label: "Valor", value: new Intl.NumberFormat("pt-BR", { style: "currency", currency: item.currency, maximumFractionDigits: 20 }).format(Number(item.amount)) },
            { label: "Última situação registrada", value: item.withdrawal_state === "VOID" ? "Retirada confirmada — sem quitação" : item.withdrawal_state === "REQUESTED" ? "Retirada em conferência" : item.payment_reconciliation_state && item.payment_reconciliation_state !== "MATCHED" ? "Recebimento em conferência" : item.gateway_status ? STATUS[item.gateway_status] ?? item.gateway_status : "Sem observação registrada" },
            ...(item.payment_reconciliation_state ? [
              { label: "Conferência do recebimento", value: REVIEW[item.payment_reconciliation_state] ?? "Revisão necessária" },
              { label: "Valor informado pelo provedor", value: item.gateway_observed_amount != null ? new Intl.NumberFormat("pt-BR", { style: "currency", currency: item.currency }).format(Number(item.gateway_observed_amount)) : "Não informado" },
            ] : []),
            ...(item.withdrawal_observed_at ? [{ label: "Retirada verificada em", value: new Date(item.withdrawal_observed_at).toLocaleString("pt-BR") }] : []),
            { label: "Ambiente", value: item.gateway_mode ? MODES[item.gateway_mode] ?? item.gateway_mode : "Não registrado" },
            { label: "Origem", value: item.status_source === "RECONCILIATION" ? "Consulta ao provedor" : item.status_source === "WEBHOOK" ? "Notificação recebida" : item.status_source === "CREATE" ? "Resposta da criação" : "Não registrada" },
            { label: "Observado em", value: item.status_observed_at ? new Date(item.status_observed_at).toLocaleString("pt-BR") : "Não registrado" },
          ]} />
          {url ? <a href={url} target="_blank" rel="noopener noreferrer" referrerPolicy="no-referrer">Abrir fatura no Asaas{item.gateway_mode === "SANDBOX" ? " — teste" : ""}</a>
            : <p className={styles.description}>Fatura hospedada indisponível neste registro.</p>}
          {canManage && stepUp && item.reconciliation_available ? <Button variant="secondary" disabled={lookupBusy || Boolean(withdrawReview) || !stepUp.ready} onClick={() => reconcile(item.gateway_charge_id)}>Conferir recebimento no provedor</Button> : null}
          {canManage && stepUp && item.withdrawal_fingerprint && !withdrawReview ? <Button variant="secondary" disabled={lookupBusy} onClick={() => {
            setWithdrawReview({ id: item.gateway_charge_id, fingerprint: item.withdrawal_fingerprint!, key: crypto.randomUUID() });
            setWithdrawAccepted(false); setLookupMessage(null);
          }}>Revisar retirada da fatura aberta</Button> : null}
          {withdrawReview?.id === item.gateway_charge_id ? <section aria-label="Confirmar retirada da fatura aberta">
            <p>A renovação foi encerrada. Esta solicitação retira a fatura ainda aberta, sem apagar o histórico ou devolver valores pagos. O excedente autorizado e entregue continua devido e será tratado no fechamento final.</p>
            {item.gateway_mode === "SIMULATOR" ? <p>Simulação: nenhuma movimentação de dinheiro real.</p> : null}
            <label><input type="checkbox" checked={withdrawAccepted} disabled={lookupBusy} onChange={event => setWithdrawAccepted(event.target.checked)} /> Conferi a fatura e entendo que o excedente entregue continua devido.</label>
            <Button disabled={lookupBusy || !withdrawAccepted || !stepUp?.ready} onClick={withdraw}>Confirmar retirada da fatura aberta</Button>
            <Button variant="secondary" disabled={lookupBusy} onClick={() => setWithdrawReview(null)}>Voltar</Button>
          </section> : null}
        </article>;
      })}
    </div>
    {lookupMessage ? <p role="status">{lookupMessage}</p> : null}
    {loading ? <Spinner label="Carregando cobranças" /> : null}
    {error ? <ErrorState title="Não foi possível consultar as cobranças" description="Verifique sua permissão de cobrança e tente novamente." action={<Button onClick={() => load(cursor)}>Tentar novamente</Button>} /> : null}
    {!loading && !error && items.length === 0 ? <EmptyState title="Nenhuma cobrança registrada" description="Cobranças aparecerão aqui quando forem emitidas." /> : null}
    {!loading && !error && cursor ? <Button variant="secondary" onClick={() => load(cursor)}>Carregar mais cobranças</Button> : null}
  </Card>;
}
