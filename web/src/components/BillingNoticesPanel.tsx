"use client";
import { useEffect, useRef, useState } from "react";
import type { BillingNotice, BillingNotices, BillingNoticeRead } from "@/contracts/types";
import { api } from "@/lib/api/client";
import { Button } from "./Button";
import { Card } from "./Card";
import { ErrorState } from "./ErrorState";
import { Spinner } from "./Spinner";

const STATE: Record<BillingNotice["invoice_state"], string> = {
  PENDING_CONFIRMATION: "A confirmação do pagamento ainda não foi registrada. Se você já pagou, use Conferir pagamento no histórico de cobranças.",
  PAYMENT_CONFIRMED: "O pagamento foi confirmado. Este aviso faz parte do histórico.",
  VOID: "A retirada da fatura foi confirmada. Este aviso faz parte do histórico.",
  FINANCIALLY_ADJUSTED: "O ajuste financeiro da garantia foi registrado. Este aviso faz parte do histórico.",
  REVIEW_REQUIRED: "A fatura exige conferência. Este aviso não confirma uma dívida adicional.",
  INVOICE_UNAVAILABLE: "A fatura não está disponível para conferência neste momento.",
};
const date = (value: string) => new Date(value).toLocaleString("pt-BR");
const money = (value: string) => new Intl.NumberFormat("pt-BR", { style: "currency", currency: "BRL" }).format(Number(value));
export function BillingNoticesPanel() {
  const [items, setItems] = useState<BillingNotice[]>([]);
  const [cursor, setCursor] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const inFlight = useRef(false);
  const keys = useRef(new Map<string, string>());
  useEffect(() => {
    let active = true;
    api.get<BillingNotices>("/billing/notices").then(value => {
      if (!Array.isArray(value?.items)) throw new Error("Inbox unavailable");
      if (active) { setItems(value.items); setCursor(value.next_cursor); }
    }).catch(() => { if (active) setError("Não foi possível consultar os avisos."); })
      .finally(() => { if (active) setLoading(false); });
    return () => { active = false; };
  }, []);
  async function load(next: boolean) {
    if (inFlight.current) return;
    inFlight.current = true; setBusy(true); setError(null);
    try {
      const value = await api.get<BillingNotices>("/billing/notices" + (next && cursor ? `?cursor=${encodeURIComponent(cursor)}` : ""));
      if (!Array.isArray(value?.items)) throw new Error("Inbox unavailable");
      setItems(previous => next ? [...new Map([...previous, ...value.items].map(item => [item.id, item])).values()] : value.items);
      setCursor(value.next_cursor);
    } catch { setError("Não foi possível consultar os avisos."); }
    finally { inFlight.current = false; setBusy(false); }
  }
  async function markRead(item: BillingNotice) {
    if (inFlight.current || item.read_at) return;
    inFlight.current = true; setBusy(true); setError(null);
    if (!keys.current.has(item.id)) keys.current.set(item.id, crypto.randomUUID());
    try {
      const value = await api.post<BillingNoticeRead>(`/billing/notices/${encodeURIComponent(item.id)}/read`,
        undefined, { idempotencyKey: keys.current.get(item.id) });
      setItems(previous => previous.map(row => row.id === item.id ? { ...row, read_at: value.read_at } : row));
      keys.current.delete(item.id);
    } catch { setError("Leitura ainda não confirmada. Tente novamente para consultar a mesma solicitação."); }
    finally { inFlight.current = false; setBusy(false); }
  }
  return <Card>
    <h2>Avisos de cobrança no aplicativo</h2>
    <p>Disponíveis para consulta pelos responsáveis financeiros da organização. A disponibilidade aqui não confirma envio de e-mail ou SMS, leitura ou pagamento.</p>
    {loading ? <Spinner label="Consultando avisos" /> : <>
      {items.length === 0 ? <p>Nenhum aviso disponível.</p> : items.map(item => <section key={item.id} aria-label={`Aviso de cobrança D${item.offset_days}`}>
        <h3>Acompanhamento da fatura — D{item.offset_days}</h3>
        <p>Valor da fatura: {money(item.amount)}. Vencimento: {date(item.due_at)}.</p>
        <p>{STATE[item.invoice_state]}</p>
        <p>Marco previsto: {date(item.scheduled_at)}. Disponível no aplicativo em {date(item.created_at)}.</p>
        {item.mode === "SIMULATOR" ? <p>Aviso de simulação; não comprova movimentação bancária real.</p> : null}
        {item.read_at ? <p>Lido por você em {date(item.read_at)}.</p> :
          <Button variant="secondary" disabled={busy} onClick={() => markRead(item)}>Marcar como lido</Button>}
      </section>)}
      {cursor ? <Button variant="secondary" disabled={busy} onClick={() => load(true)}>Carregar mais avisos</Button> : null}
      <Button variant="secondary" disabled={busy} onClick={() => load(false)}>Atualizar avisos</Button>
    </>}
    {error ? <ErrorState title="Avisos indisponíveis" description={error} /> : null}
  </Card>;
}
