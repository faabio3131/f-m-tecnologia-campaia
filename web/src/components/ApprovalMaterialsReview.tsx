"use client";
import { useEffect, useState } from "react";
import type { ApprovalRequest, Campaign, CreativeProposalPage } from "@/contracts/types";
import { api } from "@/lib/api/client";
import { CampaignBrandSnapshot } from "./CampaignBrandSnapshot";
import { ErrorState } from "./ErrorState";
import { Spinner } from "./Spinner";

type Plan = { campaign_id: string; plan_version: number; plan: Record<string, unknown> | null };
type Props = { approval: ApprovalRequest; onReviewed: (id: string, ready: boolean) => void };
type Data = { campaign: Campaign; plan: Plan; copy: CreativeProposalPage; audience: CreativeProposalPage };

export function ApprovalMaterialsReview(props: Props) {
  return <MaterialsContent key={[props.approval.id, props.approval.campaign_id, props.approval.plan_version].join(":")} {...props} />;
}
function MaterialsContent({ approval, onReviewed }: Props) {
  const [data, setData] = useState<Data | null>(null), [error, setError] = useState(false);
  useEffect(() => {
    let active = true;
    const base = "/campaigns/" + encodeURIComponent(approval.campaign_id);
    Promise.all([api.get<Campaign>(base), api.get<Plan>(base + "/plan"),
      api.get<CreativeProposalPage>(base + "/proposals/copy"), api.get<CreativeProposalPage>(base + "/proposals/audience")])
      .then(([campaign, plan, copy, audience]) => {
        if (!active) return;
        const matches = plan.plan_version === approval.plan_version && plan.plan !== null;
        setData({ campaign, plan, copy, audience }); onReviewed(approval.id + ":" + String(approval.plan_version), matches);
      }).catch(() => { if (active) { setError(true); onReviewed(approval.id + ":" + String(approval.plan_version), false); } });
    return () => { active = false; };
  }, [approval.id, approval.campaign_id, approval.plan_version, onReviewed]);
  if (error) return <ErrorState title="Materiais indisponíveis" description="Não foi possível conferir esta versão. Recarregue a fila antes de decidir." />;
  if (!data) return <Spinner label="Conferindo materiais da campanha" />;
  const current = data.plan.plan_version === approval.plan_version && data.plan.plan !== null;
  const copy = data.copy.items.find(item => item.current);
  const audience = data.audience.items.find(item => item.current);
  return <section aria-label={"Materiais do pedido " + approval.id} style={{ overflowWrap: "anywhere" }}>
    <p>Pedido: plano {approval.plan_version ?? "não informado"} · campanha atual: plano {data.plan.plan_version}.</p>
    {!current ? <p role="alert">A campanha mudou. Este pedido não autoriza a versão atual; solicite uma nova revisão.</p> : null}
    <p>Leitura dos materiais registrados. O formato final do anúncio depende da preparação por canal.</p>
    {data.campaign.brief?.brand_snapshot_v1 ? <CampaignBrandSnapshot snapshot={data.campaign.brief.brand_snapshot_v1} /> : null}
    <h4>Estratégia atual</h4>
    <pre style={{ whiteSpace: "pre-wrap" }}>{JSON.stringify(data.plan.plan, null, 2)}</pre>
    <h4>Textos vigentes</h4>
    {copy && "variacoes" in copy.output ? <>
      <p>Textos · versão {copy.version} · {String(copy.request_summary.channel ?? "")}</p>
      <ol>{copy.output.variacoes.map((text, index) => <li key={index}>{text}</li>)}</ol>
      <p>Origem: {copy.provider} · {copy.model} · prompt {copy.prompt_version}.</p>
    </> : <p>Nenhum texto entregue para a estratégia atual.</p>}
    <h4>Público vigente</h4>
    {audience && "segmentos" in audience.output ? <>
      <p>Segmentos: {audience.output.segmentos.join("; ")}.</p>
      <p>Exclusões: {audience.output.exclusoes.join("; ") || "Nenhuma"}.</p>
      <p>Tema sensível declarado ou identificado: {audience.output.sensivel || audience.request_summary.sensitive_declared === true ? "Sim" : "Não"}.</p>
      <p>Origem: {audience.provider} · {audience.model} · prompt {audience.prompt_version}.</p>
    </> : <p>Nenhum público entregue para a estratégia atual.</p>}
    <p>{approval.requires_dual_approval ? "Este pedido exige dois aprovadores distintos." : "Este pedido exige aprovação humana."}</p>
  </section>;
}
