"use client";
import Image from "next/image";
import { useCallback, useEffect, useRef, useState, type FormEvent } from "react";
import type { BrandAsset, BrandAssetPage } from "@/contracts/types";
import { api, ApiClientError } from "@/lib/api/client";
import { Button } from "@/components/Button";
import { ErrorState } from "@/components/ErrorState";
import { Spinner } from "@/components/Spinner";

type Intent = { key: string; file: File; kind: "LOGO" | "REFERENCE" };
const labels: Record<BrandAsset["status"], string> = {
  UPLOADING: "Envio em conferência", UPLOAD_UNCERTAIN: "Envio aguardando confirmação",
  READY: "Disponível", DELETE_REQUESTED: "Exclusão em conferência",
  DELETE_UNCERTAIN: "Exclusão aguardando confirmação", DELETED: "Acesso removido",
};
export function BrandAssetsPanel({ identity, name, canManage }: { identity: string; name: string; canManage: boolean }) {
  const path = `/brand-profiles/${encodeURIComponent(identity)}/assets`;
  const [page, setPage] = useState<BrandAssetPage | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [message, setMessage] = useState<string | null>(null);
  const [file, setFile] = useState<File | null>(null);
  const [kind, setKind] = useState<"LOGO" | "REFERENCE">("LOGO");
  const [busy, setBusy] = useState(false);
  const [uncertain, setUncertain] = useState(false);
  const [deleteTarget, setDeleteTarget] = useState<string | null>(null);
  const alive = useRef(false), active = useRef(false), epoch = useRef(0);
  const intent = useRef<Intent | null>(null);
  const input = useRef<HTMLInputElement>(null);
  const keys = useRef<Record<string, string>>({});
  const load = useCallback(async (cursor?: string) => {
    const read = ++epoch.current;
    const result = await api.get<BrandAssetPage>(path + (cursor ? `?cursor=${encodeURIComponent(cursor)}` : ""));
    if (alive.current && read === epoch.current) setPage(previous => cursor && previous
      ? { ...result, items: [...previous.items, ...result.items.filter(item => !previous.items.some(old => old.id === item.id))] } : result);
  }, [path]);
  const refresh = useCallback(async (cursor?: string) => {
    try { await load(cursor); } catch { if (alive.current) setError("Não foi possível consultar os arquivos."); }
  }, [load]);
  useEffect(() => {
    alive.current = true; refresh();
    return () => { alive.current = false; epoch.current++; };
  }, [refresh]);
  async function upload(event: FormEvent) {
    event.preventDefault();
    if (!canManage || active.current || !file || !page?.capability.enabled) return;
    if (!intent.current) intent.current = { key: crypto.randomUUID(), file, kind };
    const current = intent.current;
    if (current.file.size > page.capability.max_input_bytes) { setError("O arquivo deve ter até 5 MiB."); intent.current = null; return; }
    active.current = true; setBusy(true); setError(null); setMessage(null);
    try {
      const result = await api.upload<BrandAsset>(`${path}?kind=${current.kind}`, current.file,
        { idempotencyKey: current.key, timeoutMs: 45_000 });
      if (!alive.current) return;
      intent.current = null; setUncertain(false); setFile(null);
      if (input.current) input.current.value = "";
      setMessage(result.status === "READY" ? "Imagem salva." : "Envio registrado. Confira a confirmação antes de usar a imagem.");
      await refresh();
    } catch (err) {
      if (!alive.current) return;
      if (err instanceof ApiClientError && err.status < 500) {
        intent.current = null; setUncertain(false); setError(err.message);
      } else {
        setUncertain(true); setError("Resultado ainda não confirmado. Use Conferir envio para consultar a mesma solicitação.");
      }
    } finally { active.current = false; if (alive.current) setBusy(false); }
  }
  async function mutate(asset: BrandAsset, action: "delete" | "reconcile") {
    if (!canManage || active.current || uncertain) return;
    const key = keys.current[action + asset.id] ??= crypto.randomUUID();
    active.current = true; setBusy(true); setError(null); setMessage(null);
    try {
      const url = `${path}/${encodeURIComponent(asset.id)}`;
      const result = action === "delete" ? await api.delete<BrandAsset>(url, { idempotencyKey: key })
        : await api.post<BrandAsset>(url + "/reconcile", undefined, { idempotencyKey: key });
      if (!alive.current) return;
      setMessage(result.status === "DELETED" ? "Acesso à imagem removido." : result.status === "READY"
        ? "Imagem confirmada." : "Confirmação ainda pendente. O arquivo permanece reservado.");
      setDeleteTarget(null); await refresh();
    } catch (err) {
      if (alive.current) setError(err instanceof ApiClientError ? err.message : "Resultado ainda não confirmado. Confira a mesma ação novamente.");
    } finally { active.current = false; if (alive.current) setBusy(false); }
  }
  const locked = busy || uncertain;
  return <section aria-label={`Arquivos de ${name}`} style={{ marginTop: "1rem", overflowWrap: "anywhere" }}>
    <h3>Arquivos da marca</h3>
    <p>Logos e imagens de referência. A escolha para cada campanha será feita separadamente.</p>
    {error ? <ErrorState title="Não foi possível concluir" description={error} /> : null}
    {message ? <p role="status">{message}</p> : null}
    {!page ? <Spinner label="Consultando arquivos" /> : <>
      {!page.capability.enabled ? <p>Os arquivos da marca estão indisponíveis no momento.</p> : <>
        {page.capability.mode === "SIMULATOR" ? <p>Ambiente de teste: armazenamento simulado.</p> : null}
        <p>{(page.capability.used_bytes / 1048576).toFixed(2)} de {(page.capability.max_active_bytes / 1048576).toFixed(2)} MiB reservados pela organização.</p>
        {canManage ? <form onSubmit={upload}>
          <p>PNG, JPEG ou WebP estático, até 5 MiB e 4 megapixels. A imagem é normalizada sem metadados.</p>
          <label>Finalidade <select aria-label="Finalidade da imagem" value={kind} disabled={locked}
            onChange={event => setKind(event.target.value as "LOGO" | "REFERENCE")}>
            <option value="LOGO">Logo</option><option value="REFERENCE">Referência</option>
          </select></label>{" "}
          <label>Imagem <input ref={input} aria-label="Imagem da marca" type="file" accept="image/png,image/jpeg,image/webp"
            disabled={locked} onChange={event => { setFile(event.target.files?.[0] ?? null); setError(null); }} /></label>
          <Button type="submit" disabled={busy || !file}>{busy ? "Processando…" : uncertain ? "Conferir envio" : "Enviar imagem"}</Button>
        </form> : <p>Você pode consultar as imagens disponíveis.</p>}
      </>}
      {page.items.length === 0 ? <p>Nenhum arquivo registrado.</p> : <ul style={{ paddingInlineStart: "1rem" }}>
        {page.items.map(asset => <li key={asset.id} data-testid={`brand-asset-${asset.id}`} style={{ marginBlock: "1rem" }}>
          <p>{asset.kind === "LOGO" ? "Logo" : "Referência"} · {labels[asset.status]} · {asset.width} × {asset.height}</p>
          {asset.status === "READY" && asset.content_url && page.capability.enabled
            ? <Image src={asset.content_url} alt={`${asset.kind === "LOGO" ? "Logo" : "Referência"} de ${name}`}
                width={asset.width} height={asset.height} unoptimized
                style={{ maxWidth: "100%", width: "auto", height: "auto", maxHeight: "220px" }} /> : null}
          {canManage && page.capability.enabled && asset.status !== "READY" && asset.status !== "DELETED"
            ? <Button variant="secondary" disabled={locked} onClick={() => mutate(asset, "reconcile")}>Conferir arquivo</Button> : null}
          {canManage && page.capability.enabled && asset.status === "READY" ? deleteTarget === asset.id ? <div>
            <p>Remover o acesso a esta imagem? Campanhas que a selecionaram não poderão gerar ou publicar novamente. Anúncios já publicados devem ser pausados separadamente. A retenção do armazenamento pode conservar uma cópia.</p>
            <Button disabled={locked} onClick={() => mutate(asset, "delete")}>Confirmar remoção</Button>{" "}
            <Button variant="secondary" disabled={locked} onClick={() => setDeleteTarget(null)}>Voltar</Button>
          </div> : <Button variant="secondary" disabled={locked} onClick={() => setDeleteTarget(asset.id)}>Remover imagem</Button> : null}
        </li>)}
      </ul>}
      {page.next_cursor ? <Button variant="secondary" disabled={busy} onClick={() => refresh(page.next_cursor!)}>Carregar arquivos anteriores</Button> : null}
    </>}
    <Button variant="secondary" disabled={busy} onClick={() => { setError(null); refresh(); }}>Atualizar arquivos</Button>
  </section>;
}
