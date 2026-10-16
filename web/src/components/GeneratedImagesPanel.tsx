"use client";

import { useEffect, useState } from "react";
import { api, ApiClientError } from "@/lib/api/client";
import { Button } from "./Button";
import { Card } from "./Card";
import { ErrorState } from "./ErrorState";
import { Spinner } from "./Spinner";

type ImageItem = {
  id: string; campaign_id: string; campaign_version: number;
  state: string; width: number; height: number; revision: number;
  content_type: string; available: boolean;
};
type ImagePage = { items: ImageItem[]; has_more: boolean; generation_enabled: boolean };
type ImageQuote = { mode: string; action: string; credits: number | null; extra_amount: string | null };

export function GeneratedImagesPanel({ campaignId }: { campaignId: string }) {
  const [page, setPage] = useState<ImagePage | null>(null);
  const [quote, setQuote] = useState<ImageQuote | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);
  useEffect(() => {
    let active = true;
    Promise.all([
      api.get<ImagePage>("/campaigns/" + encodeURIComponent(campaignId) + "/images"),
      api.get<ImageQuote>("/campaigns/" + encodeURIComponent(campaignId) + "/images/quote")
        .catch(() => null),
    ]).then(([found, cost]) => {
      if (!active) return;
      setPage(found); setQuote(cost); setError(null);
    }).catch((cause) => {
      if (active) setError(cause instanceof ApiClientError ? cause.message : "Falha ao consultar criativos.");
    }).finally(() => { if (active) setLoading(false); });
    return () => { active = false; };
  }, [campaignId]);
  return <Card><section aria-label="Imagens da campanha">
    <h2>Imagens da campanha</h2>
    <p>Histórico privado de criativos gerados. As imagens não são publicadas automaticamente.</p>
    {loading ? <Spinner label="Consultando imagens" /> : null}
    {error ? <ErrorState title="Imagens indisponíveis" description={error} /> : null}
    {quote?.mode === "COMMERCIAL" && quote.credits !== null
      ? <p>Créditos previstos por geração: {quote.credits}. Extra previsto: {quote.extra_amount ?? "não disponível"}.</p>
      : null}
    {!page?.generation_enabled
      ? <p role="status">Geração de imagens indisponível enquanto os controles de entrega e cobrança são certificados.</p>
      : null}
    <Button disabled={true} variant="secondary">Gerar imagem</Button>
    {page && page.items.length === 0 ? <p>Nenhum criativo registrado nesta campanha.</p> : null}
    {page?.items.map((item) => <div key={item.id}>
      <p>Criativo {item.id} · versão {item.campaign_version} · {item.width} × {item.height} · {item.state}</p>
      {!item.available ? <p>Entrega ainda não confirmada.</p> : null}
    </div>)}
    {page?.has_more ? <p>Há mais registros; a paginação será habilitada com o contrato de cursor.</p> : null}
  </section></Card>;
}
