"use client";
import Image from "next/image";
import { useState } from "react";
import type { CampaignBrandSnapshot as Snapshot } from "@/contracts/types";
import { Card } from "@/components/Card";

export function CampaignBrandSnapshot({ snapshot }: { snapshot: Snapshot }) {
  const [unavailable, setUnavailable] = useState<string[]>([]);
  const profile = snapshot.profile;
  return <Card>
    <section aria-label="Marca registrada nesta campanha" style={{ overflowWrap: "anywhere" }}>
      <h2>Marca desta campanha</h2>
      <p>{profile.name} · versão {profile.version ?? 1}</p>
      <p>Esta versão foi registrada no briefing. Edições posteriores da marca não alteram esta campanha.</p>
      <p>Tom de voz: {profile.tone}</p>
      {profile.colors?.length ? <p>Cores: {profile.colors.join(", ")}</p> : null}
      {profile.differentiators?.length ? <><h3>Diferenciais</h3><ul>{profile.differentiators.map((text, index) => <li key={index}>{text}</li>)}</ul></> : null}
      {profile.restrictions?.length ? <>
        <h3>Restrições para revisão humana</h3>
        <ul>{profile.restrictions.map((text, index) => <li key={index}>{text}</li>)}</ul>
        <p>Confira essas orientações na estratégia e nos criativos antes da aprovação.</p>
      </> : null}
      {snapshot.assets.length ? <><h3>Arquivos selecionados no briefing</h3><ul style={{ paddingInlineStart: "1rem" }}>
        {snapshot.assets.map(asset => <li key={asset.id}>
          <p>{asset.kind === "LOGO" ? "Logo" : "Referência"} · {asset.width} × {asset.height}</p>
          {asset.content_url && !unavailable.includes(asset.id) ? <Image src={asset.content_url}
            alt={`Arquivo selecionado de ${profile.name}`} width={asset.width} height={asset.height} unoptimized
            onError={() => setUnavailable(previous => previous.includes(asset.id) ? previous : [...previous, asset.id])}
            style={{ maxHeight: "180px", maxWidth: "100%", width: "auto", height: "auto" }} />
            : <p>Arquivo removido ou indisponível. Para gerar ou publicar, crie um novo briefing com arquivos disponíveis.</p>}
        </li>)}
      </ul></> : null}
    </section>
  </Card>;
}
