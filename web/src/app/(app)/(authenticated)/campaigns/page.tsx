"use client";
import { useEffect, useRef, useState, type FormEvent } from "react";
import Link from "next/link";
import { CampaignBrandSelector } from "@/components/CampaignBrandSelector";
import { Button } from "@/components/Button";
import { Card } from "@/components/Card";
import { EmptyState } from "@/components/EmptyState";
import { ErrorState } from "@/components/ErrorState";
import { Input } from "@/components/Input";
import { PageContainer } from "@/components/PageContainer";
import { PageHeader } from "@/components/PageHeader";
import { Spinner } from "@/components/Spinner";
import { useAuth } from "@/providers/AuthProvider";
import type { BrandSelectionInput, BriefInput, Campaign } from "@/contracts/types";
import { ApiClientError, api } from "@/lib/api/client";
import styles from "./page.module.css";

export default function CampaignsPage() {
  const { me, session } = useAuth();
  const scope = [session?.tenant_id, session?.user_id, me?.business_unit_id].join(":");
  return <CampaignsContent key={scope} canCreate={me?.permissions?.includes("CAMPAIGN_CREATE") ?? false} />;
}
function CampaignsContent({ canCreate }: { canCreate: boolean }) {
  const [campaigns, setCampaigns] = useState<Campaign[] | null>(null);
  const [loadError, setLoadError] = useState<string | null>(null);
  const [objective, setObjective] = useState(""), [product, setProduct] = useState(""), [audience, setAudience] = useState("");
  const [totalBudget, setTotalBudget] = useState("10000"), [dailyCap, setDailyCap] = useState("1000");
  const [selection, setSelection] = useState<BrandSelectionInput | null>(null);
  const [chooseBrand, setChooseBrand] = useState(false);
  const [submitting, setSubmitting] = useState(false), [uncertain, setUncertain] = useState(false);
  const [submitError, setSubmitError] = useState<string | null>(null);
  const intent = useRef<{ key: string; body: BriefInput } | null>(null);
  const alive = useRef(false), active = useRef(false);
  useEffect(() => {
    alive.current = true;
    api.get<{ items: Campaign[] }>("/campaigns").then(result => {
      if (alive.current) setCampaigns(result.items);
    }).catch(err => {
      if (alive.current) setLoadError(err instanceof ApiClientError ? err.message : "Falha ao carregar campanhas.");
    });
    return () => { alive.current = false; };
  }, []);
  async function submit(event: FormEvent) {
    event.preventDefault();
    if (!canCreate || active.current) return;
    if (!intent.current) intent.current = { key: "brief-create-" + crypto.randomUUID(),
      body: { objective, product, audience, total_budget: totalBudget, daily_cap: dailyCap, brand_selection: selection } };
    const current = intent.current;
    active.current = true; setSubmitting(true); setSubmitError(null);
    try {
      const created = await api.post<Campaign>("/briefs", current.body, { idempotencyKey: current.key });
      if (!alive.current) return;
      setCampaigns(previous => previous?.some(item => item.id === created.id) ? previous : [...previous ?? [], created]);
      intent.current = null; setUncertain(false); setObjective(""); setProduct(""); setAudience(""); setSelection(null);
    } catch (err) {
      if (!alive.current) return;
      if (err instanceof ApiClientError && err.status < 500) {
        intent.current = null; setUncertain(false); setSubmitError(err.message);
      } else {
        setUncertain(true); setSubmitError("Resultado ainda não confirmado. Confira o mesmo envio antes de alterar o briefing.");
      }
    } finally { active.current = false; if (alive.current) setSubmitting(false); }
  }
  const locked = submitting || uncertain;
  return <PageContainer>
    <PageHeader title="Campanhas" description="Prepare o briefing e acompanhe a estratégia, a revisão e a aprovação da campanha." />
    {canCreate ? <Card>
      <h2 className={styles.sectionTitle}>Novo briefing</h2>
      <form onSubmit={submit} className={styles.form}>
        <Input label="Objetivo" required disabled={locked} value={objective} onChange={event => setObjective(event.target.value)} />
        <Input label="Produto/serviço" disabled={locked} value={product} onChange={event => setProduct(event.target.value)} />
        <Input label="Público-alvo" disabled={locked} value={audience} onChange={event => setAudience(event.target.value)} />
        <Input label="Orçamento total (BRL)" type="number" disabled={locked} value={totalBudget} onChange={event => setTotalBudget(event.target.value)} />
        <Input label="Teto diário (BRL)" type="number" disabled={locked} value={dailyCap} onChange={event => setDailyCap(event.target.value)} />
        <Button variant="secondary" disabled={locked} onClick={() => setChooseBrand(previous => !previous)}>Escolher Brand Kit</Button>
        {chooseBrand ? <CampaignBrandSelector value={selection} onChange={setSelection} disabled={locked} />
          : <p>{selection ? `Brand Kit selecionado · versão ${selection.expected_version}` : "Sem Brand Kit selecionado."}</p>}
        {submitError ? <ErrorState title="Não foi possível criar a campanha" description={submitError} /> : null}
        <Button type="submit" disabled={submitting}>{submitting ? "Enviando…" : uncertain ? "Conferir envio do briefing" : "Enviar briefing"}</Button>
      </form>
    </Card> : <p>Você pode consultar as campanhas disponíveis.</p>}
    <Card>
      <h2 className={styles.sectionTitle}>Campanhas</h2>
      {loadError ? <ErrorState title="Não foi possível carregar" description={loadError} />
        : campaigns === null ? <Spinner label="Carregando campanhas" />
        : campaigns.length === 0 ? <EmptyState title="Nenhuma campanha ainda" />
        : <ul className={styles.list}>{campaigns.map(campaign => <li key={campaign.id} className={styles.listItem}>
          <Link href={`/campaigns/${campaign.id}`} className={styles.link}><p className={styles.itemName}>{campaign.name || campaign.objective}</p><p className={styles.itemDetail}>{campaign.state}</p></Link>
        </li>)}</ul>}
    </Card>
  </PageContainer>;
}
