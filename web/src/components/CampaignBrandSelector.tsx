"use client";
import Image from "next/image";
import { useCallback, useEffect, useRef, useState } from "react";
import type { BrandAsset, BrandAssetPage, BrandProfile, BrandSelectionInput } from "@/contracts/types";
import { api } from "@/lib/api/client";
import { Button } from "@/components/Button";
import { ErrorState } from "@/components/ErrorState";

export function CampaignBrandSelector({ value, onChange, disabled }: {
  value: BrandSelectionInput | null; onChange: (value: BrandSelectionInput | null) => void; disabled: boolean;
}) {
  const [profiles, setProfiles] = useState<BrandProfile[]>([]);
  const [assets, setAssets] = useState<BrandAsset[]>([]);
  const [cursor, setCursor] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const alive = useRef(false), epoch = useRef(0);
  const identity = value?.brand_profile_id ?? "";
  const profileEpoch = useRef(0);
  const loadProfiles = useCallback(() => {
    const current = ++profileEpoch.current;
    return api.get<BrandProfile[]>("/brand-profiles").then(result => {
      if (alive.current && current === profileEpoch.current) setProfiles(result);
    }).catch(() => { if (alive.current && current === profileEpoch.current) setError("Não foi possível consultar as marcas."); });
  }, []);
  useEffect(() => {
    alive.current = true; loadProfiles();
    return () => { alive.current = false; };
  }, [loadProfiles]);
  const loadAssets = useCallback((before?: string) => {
    const current = ++epoch.current;
    if (!identity) return;
    return api.get<BrandAssetPage>(`/brand-profiles/${encodeURIComponent(identity)}/assets` +
      (before ? `?cursor=${encodeURIComponent(before)}` : "")).then(result => {
      if (alive.current && current === epoch.current) {
        const ready = result.capability.enabled ? result.items.filter(asset => asset.status === "READY") : [];
        setAssets(previous => before ? [...previous, ...ready.filter(asset => !previous.some(item => item.id === asset.id))] : ready);
        setCursor(result.next_cursor);
      }
    }).catch(() => { if (alive.current && current === epoch.current) setError("Não foi possível consultar os arquivos da marca."); });
  }, [identity]);
  useEffect(() => { loadAssets(); }, [loadAssets]);
  function choose(identity: string) {
    epoch.current++;
    setError(null); setAssets([]); setCursor(null);
    const profile = profiles.find(item => item.id === identity);
    onChange(profile && profile.id ? { brand_profile_id: profile.id, expected_version: profile.version ?? 1, asset_ids: [] } : null);
  }
  function toggle(asset: BrandAsset, checked: boolean) {
    if (!value || disabled) return;
    const previous = value.asset_ids ?? [];
    if (checked && previous.length >= 20) { setError("Selecione até 20 arquivos."); return; }
    onChange({ ...value, asset_ids: checked ? [...previous, asset.id] : previous.filter(identity => identity !== asset.id) });
  }
  return <fieldset disabled={disabled}>
    <legend>Marca desta campanha</legend>
    <label>Brand Kit <select aria-label="Brand Kit da campanha" value={identity} onChange={event => choose(event.target.value)}>
      <option value="">Sem Brand Kit</option>
      {profiles.filter(profile => profile.id).map(profile =>
        <option key={profile.id} value={profile.id}>{profile.name} · versão {profile.version ?? 1}</option>)}
    </select></label>
    {value ? <p>Versão escolhida: {value.expected_version}. A campanha guardará esta versão.</p> : <p>Nenhuma marca será aplicada automaticamente.</p>}
    {error ? <ErrorState title="Confira a seleção" description={error} /> : null}
    {identity ? <>
      <p>Escolha os arquivos que devem acompanhar a campanha. A estratégia usa o contexto textual; a aplicação visual será feita nos criativos.</p>
      {assets.length === 0 ? <p>Nenhuma imagem disponível para esta marca.</p> : <ul style={{ paddingInlineStart: "1rem" }}>
        {assets.map(asset => <li key={asset.id} style={{ marginBlock: "0.75rem" }}>
          <label><input type="checkbox" checked={value?.asset_ids?.includes(asset.id) ?? false}
            onChange={event => toggle(asset, event.target.checked)} /> {asset.kind === "LOGO" ? "Logo" : "Referência"} · {asset.width} × {asset.height}</label>
          {asset.content_url ? <Image src={asset.content_url} alt={`Arquivo ${asset.kind === "LOGO" ? "logo" : "de referência"} para seleção`}
            width={asset.width} height={asset.height} unoptimized style={{ maxHeight: "120px", maxWidth: "100%", width: "auto", height: "auto" }} /> : null}
        </li>)}
      </ul>}
      {cursor ? <Button type="button" variant="secondary" onClick={() => loadAssets(cursor)}>Carregar mais arquivos</Button> : null}
      <Button type="button" variant="secondary" onClick={() => { choose(identity); loadAssets(); }}>Usar versão atual da lista</Button>
    </> : null}
    <Button type="button" variant="secondary" onClick={loadProfiles}>Atualizar marcas</Button>
  </fieldset>;
}
