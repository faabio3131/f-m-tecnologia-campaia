"use client";
import { useRef, useState } from "react";
import type { StrategyCreditQuote, CreditConfirmation } from "@/contracts/types";
import { api, ApiClientError } from "@/lib/api/client";
import { Button } from "./Button";

type Props = { campaignId: string; hasPlan: boolean; busy: boolean;
  onBusy: (busy: boolean) => void; onError: (message: string | null) => void;
  onGenerated: () => Promise<void> };
type Prepared = { key: string; body: { credit_confirmation?: CreditConfirmation } };
const money = (value: string) => new Intl.NumberFormat("pt-BR", { style: "currency", currency: "BRL" }).format(Number(value));

export function StrategyGenerateButton({ campaignId, hasPlan, busy, onBusy, onError, onGenerated }: Props) {
  const [prepared, setPrepared] = useState<Prepared | null>(null);
  const inFlight = useRef(false);

  async function execute(request: Prepared) {
    try {
      await api.post(`/campaigns/${campaignId}/plan/regenerate`, request.body, { idempotencyKey: request.key });
      await onGenerated();
      setPrepared(null);
    } catch (err) {
      // Preserve this exact body/key after an uncertain response. A repeated request
      // recovers the delivery; the backend will never redispatch a pending operation.
      setPrepared(request);
      onError(err instanceof ApiClientError ? err.message : "Resultado não confirmado. Reutilize esta confirmação para consultar a mesma operação.");
    }
  }

  async function review() {
    if (inFlight.current) return;
    inFlight.current = true; onBusy(true); onError(null);
    try {
      const quote = await api.get<StrategyCreditQuote>(`/campaigns/${campaignId}/plan/quote`);
      const key = `plan-regenerate-${campaignId}-${crypto.randomUUID()}`;
      if (quote.mode === "LEGACY") {
        await execute({ key, body: {} });
      } else if (quote.cycle_id && quote.policy_version && quote.credits !== null && quote.extra_amount !== null) {
        setPrepared({ key, body: { credit_confirmation: { cycle_id: quote.cycle_id,
          policy_version: quote.policy_version, credits: quote.credits, extra_amount: quote.extra_amount } } });
      } else {
        onError("Cotação incompleta. Recarregue antes de gerar a estratégia.");
      }
    } catch (err) {
      onError(err instanceof ApiClientError ? err.message : "Não foi possível consultar o débito da operação.");
    } finally { inFlight.current = false; onBusy(false); }
  }
  async function confirm() {
    if (!prepared || inFlight.current) return;
    inFlight.current = true; onBusy(true); onError(null);
    try { await execute(prepared); }
    finally { inFlight.current = false; onBusy(false); }
  }

  return prepared ? <section aria-label="Confirmar geração de estratégia">
    {prepared.body.credit_confirmation ? <p>Esta entrega utiliza {prepared.body.credit_confirmation.credits} créditos.
      Excedente estimado: {money(prepared.body.credit_confirmation.extra_amount)}. Falha conhecida ou bloqueio de política não gera consumo.</p>
      : <p>Consulte o resultado da mesma solicitação.</p>}
    <Button disabled={busy} onClick={confirm}>Confirmar geração</Button>
    <Button variant="secondary" disabled={busy} onClick={() => setPrepared(null)}>Voltar</Button>
  </section> : <Button disabled={busy} onClick={review}>{hasPlan ? "Regenerar estratégia" : "Gerar estratégia"}</Button>;
}
