"use client";

import { useEffect, useRef, useState } from "react";
import type { BillingChargeHistory, BillingChargeHistoryItem } from "@/contracts/types";
import { safeBillingInvoiceUrl } from "@/lib/billing";
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

export function BillingChargeHistoryPanel() {
  const [items, setItems] = useState<BillingChargeHistoryItem[]>([]);
  const [cursor, setCursor] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(false);
  const inFlight = useRef(false);

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
        const url = safeBillingInvoiceUrl(item.invoice_url, item.gateway_provider, item.gateway_mode);
        return <article key={item.gateway_charge_id} className={styles.item} aria-label={`Cobrança ${item.billing_id}`}>
          <StatusPanel title={`Competência ${item.competence} · ${item.gateway_charge_id}`} items={[
            { label: "Identificador", value: item.billing_id },
            { label: "Finalidade", value: PURPOSES[item.purpose] ?? item.purpose },
            { label: "Valor", value: new Intl.NumberFormat("pt-BR", { style: "currency", currency: item.currency, maximumFractionDigits: 20 }).format(Number(item.amount)) },
            { label: "Última situação registrada", value: item.gateway_status ? STATUS[item.gateway_status] ?? item.gateway_status : "Sem observação registrada" },
            { label: "Ambiente", value: item.gateway_mode ? MODES[item.gateway_mode] ?? item.gateway_mode : "Não registrado" },
            { label: "Origem", value: item.status_source === "WEBHOOK" ? "Notificação recebida" : item.status_source === "CREATE" ? "Resposta da criação" : "Não registrada" },
            { label: "Observado em", value: item.status_observed_at ? new Date(item.status_observed_at).toLocaleString("pt-BR") : "Não registrado" },
          ]} />
          {url ? <a href={url} target="_blank" rel="noopener noreferrer" referrerPolicy="no-referrer">Abrir fatura no Asaas{item.gateway_mode === "SANDBOX" ? " — teste" : ""}</a>
            : <p className={styles.description}>Fatura hospedada indisponível neste registro.</p>}
        </article>;
      })}
    </div>
    {loading ? <Spinner label="Carregando cobranças" /> : null}
    {error ? <ErrorState title="Não foi possível consultar as cobranças" description="Verifique sua permissão de cobrança e tente novamente." action={<Button onClick={() => load(cursor)}>Tentar novamente</Button>} /> : null}
    {!loading && !error && items.length === 0 ? <EmptyState title="Nenhuma cobrança registrada" description="Cobranças aparecerão aqui quando forem emitidas." /> : null}
    {!loading && !error && cursor ? <Button variant="secondary" onClick={() => load(cursor)}>Carregar mais cobranças</Button> : null}
  </Card>;
}
