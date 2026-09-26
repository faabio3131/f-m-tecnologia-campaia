"use client";

import { useEffect, useState, type FormEvent } from "react";
import Link from "next/link";
import { Button } from "../../../../components/Button";
import { Card } from "../../../../components/Card";
import { EmptyState } from "../../../../components/EmptyState";
import { ErrorState } from "../../../../components/ErrorState";
import { Input } from "../../../../components/Input";
import { PageContainer } from "../../../../components/PageContainer";
import { PageHeader } from "../../../../components/PageHeader";
import { Spinner } from "../../../../components/Spinner";
import type { Campaign } from "../../../../contracts/types";
import { ApiClientError, api } from "../../../../lib/api/client";
import styles from "./page.module.css";

/**
 * WP-05 (26/09/2026): Briefing real (F3.1) contra `POST /briefs` (backend/api/
 * routes_campaigns.py, ja implementado e testado) -- cria a campanha em DRAFT.
 * Estratégia/validação/aprovação ficam no detalhe da campanha
 * (`campaigns/[campaignId]/page.tsx`). Publicação real (Fases 5–7) fica fora de
 * escopo aqui, por decisão já registrada no roadmap (depende de credencial real de
 * provider).
 */
export default function CampaignsPage() {
  const [campaigns, setCampaigns] = useState<Campaign[] | null>(null);
  const [loadError, setLoadError] = useState<string | null>(null);

  const [objective, setObjective] = useState("");
  const [product, setProduct] = useState("");
  const [audience, setAudience] = useState("");
  const [totalBudget, setTotalBudget] = useState("10000");
  const [dailyCap, setDailyCap] = useState("1000");
  const [submitting, setSubmitting] = useState(false);
  const [submitError, setSubmitError] = useState<string | null>(null);

  useEffect(() => {
    let active = true;
    (async () => {
      try {
        const result = await api.get<{ items: Campaign[] }>("/campaigns");
        if (active) setCampaigns(result.items);
      } catch (err) {
        if (active) {
          setLoadError(
            err instanceof ApiClientError ? err.message : "Falha ao carregar campanhas.",
          );
        }
      }
    })();
    return () => {
      active = false;
    };
  }, []);

  async function handleSubmit(event: FormEvent) {
    event.preventDefault();
    setSubmitError(null);
    setSubmitting(true);
    try {
      const created = await api.post<Campaign>(
        "/briefs",
        {
          objective,
          product,
          audience,
          total_budget: totalBudget,
          daily_cap: dailyCap,
        },
        { idempotencyKey: `brief-create-${crypto.randomUUID()}` },
      );
      setCampaigns((prev) => [...(prev ?? []), created]);
      setObjective("");
      setProduct("");
      setAudience("");
    } catch (err) {
      setSubmitError(
        err instanceof ApiClientError ? err.message : "Falha ao criar a campanha.",
      );
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <PageContainer>
      <PageHeader
        title="Campanhas"
        description="Briefing → Estratégia (IA) → Validação → Aprovação. Publicação real depende de integração com provider (fora de escopo aqui)."
      />

      <Card>
        <h2 className={styles.sectionTitle}>Novo briefing</h2>
        <form onSubmit={handleSubmit} className={styles.form}>
          <Input
            label="Objetivo"
            required
            value={objective}
            onChange={(e) => setObjective(e.target.value)}
          />
          <Input label="Produto/serviço" value={product} onChange={(e) => setProduct(e.target.value)} />
          <Input label="Público-alvo" value={audience} onChange={(e) => setAudience(e.target.value)} />
          <Input
            label="Orçamento total (BRL)"
            type="number"
            value={totalBudget}
            onChange={(e) => setTotalBudget(e.target.value)}
          />
          <Input
            label="Teto diário (BRL)"
            type="number"
            value={dailyCap}
            onChange={(e) => setDailyCap(e.target.value)}
          />
          {submitError ? (
            <ErrorState title="Não foi possível criar a campanha" description={submitError} />
          ) : null}
          <Button type="submit" disabled={submitting}>
            {submitting ? "Enviando…" : "Enviar briefing"}
          </Button>
        </form>
      </Card>

      <Card>
        <h2 className={styles.sectionTitle}>Campanhas</h2>
        {loadError ? (
          <ErrorState title="Não foi possível carregar" description={loadError} />
        ) : campaigns === null ? (
          <Spinner label="Carregando campanhas" />
        ) : campaigns.length === 0 ? (
          <EmptyState title="Nenhuma campanha ainda" />
        ) : (
          <ul className={styles.list}>
            {campaigns.map((campaign) => (
              <li key={campaign.id} className={styles.listItem}>
                <Link href={`/campaigns/${campaign.id}`} className={styles.link}>
                  <p className={styles.itemName}>{campaign.name || campaign.objective}</p>
                  <p className={styles.itemDetail}>{campaign.state}</p>
                </Link>
              </li>
            ))}
          </ul>
        )}
      </Card>
    </PageContainer>
  );
}
