"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import { AdministrativeStepUpCard } from "@/components/AdministrativeStepUpCard";
import { ApprovalMaterialsReview } from "@/components/ApprovalMaterialsReview";
import { Button } from "@/components/Button";
import { Card } from "@/components/Card";
import { EmptyState } from "@/components/EmptyState";
import { ErrorState } from "@/components/ErrorState";
import { PageContainer } from "@/components/PageContainer";
import { PageHeader } from "@/components/PageHeader";
import { Spinner } from "@/components/Spinner";
import { useAdministrativeStepUp } from "@/hooks/useAdministrativeStepUp";
import { useAuth } from "@/providers/AuthProvider";
import type { ApprovalRequest } from "@/contracts/types";
import { ApiClientError, api } from "@/lib/api/client";
import styles from "./page.module.css";

type Decision = "APPROVE" | "REJECT" | "REQUEST_CHANGES";
type Intent = { key: string; approvalId: string; body: { decision: Decision; reason?: string }; sent: boolean };

export default function ApprovalsPage() {
  const { me, session } = useAuth();
  const scope = [session?.tenant_id, session?.user_id, me?.business_unit_id].join(":");
  return <ApprovalsContent key={scope} userId={session?.user_id ?? me?.user_id}
    canDecide={me?.permissions?.includes("APPROVAL_DECIDE") ?? false} />;
}

function ApprovalsContent({ userId, canDecide }: { userId?: string; canDecide: boolean }) {
  const [approvals, setApprovals] = useState<ApprovalRequest[] | null>(null);
  const [loadError, setLoadError] = useState<string | null>(null), [actionError, setActionError] = useState<string | null>(null);
  const [notice, setNotice] = useState<string | null>(null), [busyId, setBusyId] = useState<string | null>(null);
  const [intent, setIntent] = useState<Intent | null>(null);
  const [reasons, setReasons] = useState<Record<string, string>>({});
  const [expanded, setExpanded] = useState<Record<string, boolean>>({});
  const [reviewed, setReviewed] = useState<Record<string, boolean>>({});
  const active = useRef(false), alive = useRef(false);
  const stepUp = useAdministrativeStepUp();
  const onReviewed = useCallback((id: string, ready: boolean) => {
    setReviewed(previous => previous[id] === ready ? previous : { ...previous, [id]: ready });
  }, []);
  async function loadApprovals() {
    const result = await api.get<ApprovalRequest[]>("/approvals");
    if (alive.current) { setApprovals(result); setLoadError(null); }
  }
  useEffect(() => {
    let current = true; alive.current = true;
    api.get<ApprovalRequest[]>("/approvals").then(result => {
      if (current) setApprovals(result);
    }).catch(err => {
      if (current) setLoadError(err instanceof ApiClientError ? err.message : "Falha ao carregar aprovações.");
    });
    return () => { current = false; alive.current = false; };
  }, []);

  async function execute(request: Intent) {
    if (active.current || !canDecide || !stepUp.ready) return;
    active.current = true; setBusyId(request.approvalId); setActionError(null); setNotice(null);
    setIntent({ ...request, sent: true });
    try {
      let response: ApprovalRequest;
      try {
        response = await api.post<ApprovalRequest>("/approvals/" + encodeURIComponent(request.approvalId) + "/decision",
          request.body, { headers: stepUp.headers(), idempotencyKey: request.key });
      } catch (err) {
        if (!alive.current) return;
        stepUp.noteError(err);
        const known = err instanceof ApiClientError && (err.code === "APPROVAL_FINALIZED" || err.code === "APPROVAL_STALE"
          || (!request.sent && err.status < 500 && err.status !== 408));
        if (known) {
          setIntent(null); setActionError(err instanceof ApiClientError ? err.message : "Não foi possível registrar a decisão.");
        } else {
          setActionError("Resultado ainda não confirmado. Confira a mesma decisão antes de enviar outra.");
        }
        return;
      }
      if (!alive.current) return;
      setIntent(null); stepUp.consumePresentedToken(); setNotice("Decisão registrada.");
      setApprovals(previous => previous?.map(item => item.id === response.id ? response : item) ?? previous);
      try { await loadApprovals(); }
      catch { if (alive.current) setLoadError("Decisão registrada. Não foi possível atualizar a fila; recarregue para conferir."); }
    } finally { active.current = false; if (alive.current) setBusyId(null); }
  }
  function decide(approvalId: string, decision: Decision) {
    if (intent || active.current) return;
    const reason = reasons[approvalId]?.trim() || undefined;
    if (decision === "REQUEST_CHANGES" && !reason) {
      setActionError("Descreva o ajuste solicitado antes de enviar."); return;
    }
    void execute({ approvalId, key: "approval-decision-" + crypto.randomUUID(),
      body: { decision, ...(reason ? { reason } : {}) }, sent: false });
  }
  const locked = busyId !== null || intent !== null;
  return <PageContainer>
    <PageHeader title="Aprovações" description="Confira a versão e os materiais antes de decidir. Quem propôs não pode aprovar a própria proposta." />
    {canDecide ? <AdministrativeStepUpCard ready={stepUp.ready} testMode={stepUp.testMode} message={stepUp.stepUpMessage}
      onIdToken={stepUp.onIdToken} onError={setActionError}
      description="Decisões de aprovação exigem uma autenticação Google recente. " /> : null}
    {loadError ? <ErrorState title="Não foi possível carregar" description={loadError} /> : null}
    {actionError ? <ErrorState title="Não foi possível decidir" description={actionError} /> : null}
    {notice ? <p role="status">{notice}</p> : null}
    {intent ? <section aria-label="Conferir decisão pendente">
      <p>A decisão e o motivo foram preservados para consultar a mesma operação.</p>
      <Button disabled={busyId !== null || !canDecide || !stepUp.ready} onClick={() => execute(intent)}>Conferir mesma decisão</Button>
    </section> : null}
    {approvals === null && !loadError ? <Spinner label="Carregando aprovações" /> : null}
    {approvals !== null ? approvals.length === 0 ? <EmptyState title="Nenhuma aprovação pendente" />
      : <div className={styles.list}>{approvals.map(approval => {
        const own = userId === approval.requested_by;
        const voted = Boolean(userId && approval.decided_by.includes(userId));
        const eligible = canDecide && !own && !voted && stepUp.ready;
        const needsReview = approval.kind === "PUBLISH" && !reviewed[approval.id + ":" + String(approval.plan_version)];
        return <Card key={approval.id} className={styles.card} data-testid={"approval-" + approval.id}>
          <p className={styles.itemTitle}>Campanha {approval.campaign_id} — {approval.reason || approval.kind}</p>
          <p className={styles.itemDetail}>Status: {approval.status} · Solicitado por: {approval.requested_by} · Plano {approval.plan_version ?? "não informado"}</p>
          <p>{approval.requires_dual_approval ? "Revisão dupla" : "Revisão humana"} · Votos registrados: {approval.decided_by.length}</p>
          {approval.amount ? <p>Valor do pedido: {approval.amount}.</p> : null}
          {approval.decision_reason ? <p>Motivo da decisão: {approval.decision_reason}</p> : null}
          <a href={"/campaigns/" + encodeURIComponent(approval.campaign_id)}>Abrir campanha</a>
          {approval.kind === "PUBLISH" ? <>
            <Button variant="secondary" disabled={busyId !== null} onClick={() => {
              if (!expanded[approval.id]) onReviewed(approval.id + ":" + String(approval.plan_version), false);
              setExpanded(previous => ({ ...previous, [approval.id]: !previous[approval.id] }));
            }}>
              {expanded[approval.id] ? "Ocultar materiais" : "Ver materiais para revisar"}
            </Button>
            {expanded[approval.id] ? <ApprovalMaterialsReview approval={approval} onReviewed={onReviewed} /> : null}
          </> : null}
          {approval.status === "PENDING" && canDecide ? <>
            {own ? <p>Quem propôs não pode decidir este pedido.</p> : voted ? <p>Seu voto já foi registrado. Aguarde outro aprovador.</p> : null}
            <label>Motivo da decisão para {approval.id}
              <textarea maxLength={1000} value={reasons[approval.id] ?? ""} disabled={locked || !eligible}
                onChange={event => setReasons(previous => ({ ...previous, [approval.id]: event.target.value }))} />
            </label>
            <p>Para solicitar ajustes, descreva o que precisa mudar.</p>
            {needsReview ? <p>Abra os materiais e confira a versão antes de aprovar.</p> : null}
            <div className={styles.actions}>
              <Button disabled={locked || !eligible || needsReview} onClick={() => decide(approval.id, "APPROVE")} data-testid={"approve-" + approval.id}>Aprovar</Button>
              <Button variant="secondary" disabled={locked || !eligible} onClick={() => decide(approval.id, "REQUEST_CHANGES")} data-testid={"changes-" + approval.id}>Solicitar ajustes</Button>
              <Button variant="secondary" disabled={locked || !eligible} onClick={() => decide(approval.id, "REJECT")} data-testid={"reject-" + approval.id}>Rejeitar</Button>
            </div>
          </> : null}
        </Card>;
      })}</div> : null}
  </PageContainer>;
}
