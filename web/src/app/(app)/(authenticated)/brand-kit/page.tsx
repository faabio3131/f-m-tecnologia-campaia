"use client";
import { useEffect, useRef, useState, type FormEvent } from "react";
import { BrandHistoryPanel } from "@/components/BrandHistoryPanel";
import { Button } from "@/components/Button";
import { Card } from "@/components/Card";
import { EmptyState } from "@/components/EmptyState";
import { ErrorState } from "@/components/ErrorState";
import { Input } from "@/components/Input";
import { PageContainer } from "@/components/PageContainer";
import { PageHeader } from "@/components/PageHeader";
import { Spinner } from "@/components/Spinner";
import { useAuth } from "@/providers/AuthProvider";
import type { BrandProfile, BrandProfileInput } from "@/contracts/types";
import { ApiClientError, api } from "@/lib/api/client";
import styles from "./page.module.css";

type Intent = { identity: string | null; key: string; body: BrandProfileInput & { expected_version?: number } };
export default function BrandKitPage() {
  const { me, session } = useAuth();
  const scope = [session?.tenant_id, session?.user_id, me?.business_unit_id].join(":");
  return <BrandKitContent key={scope} canManage={me?.permissions?.includes("BRAND_MANAGE") ?? false} />;
}
function BrandKitContent({ canManage }: { canManage: boolean }) {
  const [profiles, setProfiles] = useState<BrandProfile[] | null>(null);
  const [loadError, setLoadError] = useState<string | null>(null);
  const [editing, setEditing] = useState<{ id: string; version: number } | null>(null);
  const [history, setHistory] = useState<string | null>(null);
  const [name, setName] = useState("");
  const [tone, setTone] = useState("");
  const [colors, setColors] = useState("");
  const [differentiators, setDifferentiators] = useState("");
  const [restrictions, setRestrictions] = useState("");
  const [submitting, setSubmitting] = useState(false);
  const [uncertain, setUncertain] = useState(false);
  const [submitError, setSubmitError] = useState<string | null>(null);
  const [success, setSuccess] = useState<string | null>(null);
  const alive = useRef(true);
  const readEpoch = useRef(0);
  const inFlight = useRef(false);
  const intent = useRef<Intent | null>(null);
  const resetForm = () => {
    setName(""); setTone(""); setColors(""); setDifferentiators(""); setRestrictions("");
    setEditing(null); setSubmitError(null); setUncertain(false); intent.current = null;
  };
  useEffect(() => {
    let active = true; alive.current = true;
    const epoch = ++readEpoch.current;
    api.get<BrandProfile[]>("/brand-profiles").then(result => {
      if (!Array.isArray(result)) throw new Error("Brand profiles unavailable");
      if (active && epoch === readEpoch.current) setProfiles(result);
    }).catch(err => {
      if (active && epoch === readEpoch.current) setLoadError(err instanceof ApiClientError ? err.message : "Falha ao carregar o Brand Kit.");
    });
    return () => { active = false; alive.current = false; };
  }, []);
  async function refresh() {
    const epoch = ++readEpoch.current; setLoadError(null);
    try {
      const result = await api.get<BrandProfile[]>("/brand-profiles");
      if (!Array.isArray(result)) throw new Error("Brand profiles unavailable");
      if (alive.current && epoch === readEpoch.current) setProfiles(result);
    } catch (err) {
      if (alive.current && epoch === readEpoch.current) setLoadError(err instanceof ApiClientError ? err.message : "Falha ao carregar o Brand Kit.");
    }
  }
  function edit(profile: BrandProfile) {
    if (!profile.id || submitting || uncertain) return;
    setEditing({ id: profile.id, version: profile.version ?? 1 });
    setName(profile.name); setTone(profile.tone); setColors(profile.colors?.join("\n") ?? "");
    setDifferentiators(profile.differentiators?.join("\n") ?? ""); setRestrictions(profile.restrictions?.join("\n") ?? "");
    setSubmitError(null); setSuccess(null); intent.current = null;
  }
  const splitLines = (value: string) => value.split("\n").map(line => line.trim()).filter(Boolean);
  async function submit(event: FormEvent) {
    event.preventDefault();
    if (!canManage || inFlight.current) return;
    if (!intent.current) intent.current = {
      identity: editing?.id ?? null, key: crypto.randomUUID(),
      body: { name, tone, colors: splitLines(colors), differentiators: splitLines(differentiators),
        restrictions: splitLines(restrictions), ...(editing ? { expected_version: editing.version } : {}) },
    };
    const pending = intent.current;
    inFlight.current = true; setSubmitting(true); setSubmitError(null); setSuccess(null);
    try {
      const result = pending.identity
        ? await api.put<BrandProfile>(`/brand-profiles/${encodeURIComponent(pending.identity)}`, pending.body, { idempotencyKey: pending.key })
        : await api.post<BrandProfile>("/brand-profiles", pending.body, { idempotencyKey: pending.key });
      if (!alive.current) return;
      setProfiles(previous => previous?.some(profile => profile.id === result.id)
        ? previous.map(profile => profile.id === result.id ? result : profile) : [...previous ?? [], result]);
      resetForm(); setSuccess("Brand Kit salvo."); await refresh();
    } catch (err) {
      if (!alive.current) return;
      if (err instanceof ApiClientError && err.status < 500) {
        intent.current = null; setUncertain(false); setSubmitError(err.message);
      } else {
        setUncertain(true); setSubmitError("Resultado ainda não confirmado. Reutilize Salvar para consultar a mesma solicitação antes de alterar os dados.");
      }
    } finally {
      if (alive.current) { inFlight.current = false; setSubmitting(false); }
    }
  }
  const locked = submitting || uncertain;
  const visibleProfiles = profiles;
  return <PageContainer>
    <PageHeader title="Brand Kit" description="Defina o tom, as cores e as restrições da sua marca." />
    {canManage ? <Card>
      <h2 className={styles.sectionTitle}>{editing ? `Editar Brand Kit — versão ${editing.version}` : "Novo Brand Kit"}</h2>
      <form onSubmit={submit} className={styles.form}>
        <Input label="Nome" required maxLength={120} disabled={locked} value={name} onChange={e => setName(e.target.value)} />
        <Input label="Tom de voz" required maxLength={200} disabled={locked} value={tone} onChange={e => setTone(e.target.value)} />
        <label className={styles.textareaField}><span className={styles.textareaLabel}>Cores principais (uma por linha)</span>
          <textarea className={styles.textarea} disabled={locked} value={colors} onChange={e => setColors(e.target.value)} rows={3} /></label>
        <label className={styles.textareaField}><span className={styles.textareaLabel}>Diferenciais competitivos (um por linha)</span>
          <textarea className={styles.textarea} disabled={locked} value={differentiators} onChange={e => setDifferentiators(e.target.value)} rows={3} /></label>
        <label className={styles.textareaField}><span className={styles.textareaLabel}>Restrições de comunicação (uma por linha)</span>
          <textarea className={styles.textarea} disabled={locked} value={restrictions} onChange={e => setRestrictions(e.target.value)} rows={3} /></label>
        {submitError ? <ErrorState title="Não foi possível salvar" description={submitError} /> : null}
        <Button type="submit" disabled={submitting}>{submitting ? "Salvando…" : editing ? "Salvar alterações" : "Salvar Brand Kit"}</Button>
        {editing ? <Button type="button" variant="secondary" disabled={locked} onClick={resetForm}>Cancelar edição</Button> : null}
      </form>
    </Card> : <p>Você pode consultar os Brand Kits disponíveis.</p>}
    {success ? <p role="status">{success}</p> : null}
    <Card>
      <h2 className={styles.sectionTitle}>Brand Kits salvos</h2>
      {loadError ? <ErrorState title="Não foi possível carregar" description={loadError} />
        : visibleProfiles === null ? <Spinner label="Carregando Brand Kits" />
        : visibleProfiles.length === 0 ? <EmptyState title="Nenhum Brand Kit ainda" description="Cadastre os dados da marca para mantê-los organizados." />
        : <ul className={styles.list}>{visibleProfiles.map(profile => <li key={profile.id} data-testid={`brand-profile-${profile.id}`} className={styles.listItem} style={{ overflowWrap: "anywhere" }}>
          <p className={styles.itemName}>{profile.name}</p><p className={styles.itemDetail}>{profile.tone}</p>
          <p>Versão {profile.version ?? 1}{profile.updated_at ? ` · atualizada em ${new Date(profile.updated_at).toLocaleString("pt-BR")}` : ""}.</p>
          {canManage ? <Button variant="secondary" disabled={locked || !profile.id} onClick={() => edit(profile)}>Editar {profile.name}</Button> : null}
          <Button variant="secondary" disabled={!profile.id} onClick={() => setHistory(history === profile.id ? null : profile.id!)}>Histórico de {profile.name}</Button>
          {history === profile.id && profile.id ? <BrandHistoryPanel key={`${profile.id}:${profile.version ?? 1}`} identity={profile.id} name={profile.name} /> : null}
        </li>)}</ul>}
      <Button variant="secondary" disabled={submitting} onClick={refresh}>Atualizar lista</Button>
    </Card>
  </PageContainer>;
}
