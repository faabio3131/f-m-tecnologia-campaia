"use client";

import { useEffect, useState, type FormEvent } from "react";
import { Button } from "../../../../components/Button";
import { Card } from "../../../../components/Card";
import { EmptyState } from "../../../../components/EmptyState";
import { ErrorState } from "../../../../components/ErrorState";
import { Input } from "../../../../components/Input";
import { PageContainer } from "../../../../components/PageContainer";
import { PageHeader } from "../../../../components/PageHeader";
import { Spinner } from "../../../../components/Spinner";
import type { BrandProfile } from "../../../../contracts/types";
import { ApiClientError, api } from "../../../../lib/api/client";
import styles from "./page.module.css";

/**
 * WP-04 (26/09/2026): Brand Kit real, contra `GET/POST /brand-profiles`
 * (backend/api/routes_brand.py, ja implementado e testado). Campos exatamente os do
 * contrato real (`BrandProfileInput`) -- nunca os campos mais ricos da especificacao
 * de telas (logo/upload, tom por select fechado) que o backend nao suporta hoje.
 */
export default function BrandKitPage() {
  const [profiles, setProfiles] = useState<BrandProfile[] | null>(null);
  const [loadError, setLoadError] = useState<string | null>(null);

  const [name, setName] = useState("");
  const [tone, setTone] = useState("");
  const [colors, setColors] = useState("");
  const [differentiators, setDifferentiators] = useState("");
  const [restrictions, setRestrictions] = useState("");
  const [submitting, setSubmitting] = useState(false);
  const [submitError, setSubmitError] = useState<string | null>(null);

  async function fetchProfiles(): Promise<BrandProfile[]> {
    return api.get<BrandProfile[]>("/brand-profiles");
  }

  async function loadProfiles() {
    try {
      const result = await fetchProfiles();
      setProfiles(result);
    } catch (err) {
      setLoadError(
        err instanceof ApiClientError ? err.message : "Falha ao carregar o Brand Kit.",
      );
    }
  }

  useEffect(() => {
    let active = true;
    (async () => {
      try {
        const result = await fetchProfiles();
        if (active) setProfiles(result);
      } catch (err) {
        if (active) {
          setLoadError(
            err instanceof ApiClientError ? err.message : "Falha ao carregar o Brand Kit.",
          );
        }
      }
    })();
    return () => {
      active = false;
    };
  }, []);

  function splitLines(value: string): string[] {
    return value
      .split("\n")
      .map((line) => line.trim())
      .filter((line) => line.length > 0);
  }

  async function handleSubmit(event: FormEvent) {
    event.preventDefault();
    setSubmitError(null);
    setSubmitting(true);
    try {
      await api.post<BrandProfile>(
        "/brand-profiles",
        {
          name,
          tone,
          colors: splitLines(colors),
          differentiators: splitLines(differentiators),
          restrictions: splitLines(restrictions),
        },
        { idempotencyKey: `brand-profile-create-${crypto.randomUUID()}` },
      );
      setName("");
      setTone("");
      setColors("");
      setDifferentiators("");
      setRestrictions("");
      await loadProfiles();
    } catch (err) {
      setSubmitError(
        err instanceof ApiClientError
          ? err.message
          : "Falha ao salvar o Brand Kit. Tente novamente.",
      );
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <PageContainer>
      <PageHeader
        title="Brand Kit"
        description="Usado pela IA na geração de criativos. Pode ser editado a qualquer momento."
      />

      <Card>
        <h2 className={styles.sectionTitle}>Novo Brand Kit</h2>
        <form onSubmit={handleSubmit} className={styles.form}>
          <Input
            label="Nome"
            required
            maxLength={120}
            value={name}
            onChange={(e) => setName(e.target.value)}
          />
          <Input
            label="Tom de voz"
            required
            maxLength={200}
            placeholder="ex.: casual, técnico, inspirador"
            value={tone}
            onChange={(e) => setTone(e.target.value)}
          />
          <label className={styles.textareaField}>
            <span className={styles.textareaLabel}>Cores principais (uma por linha)</span>
            <textarea
              className={styles.textarea}
              value={colors}
              onChange={(e) => setColors(e.target.value)}
              rows={3}
            />
          </label>
          <label className={styles.textareaField}>
            <span className={styles.textareaLabel}>Diferenciais competitivos (um por linha)</span>
            <textarea
              className={styles.textarea}
              value={differentiators}
              onChange={(e) => setDifferentiators(e.target.value)}
              rows={3}
            />
          </label>
          <label className={styles.textareaField}>
            <span className={styles.textareaLabel}>
              Restrições de comunicação (uma por linha)
            </span>
            <textarea
              className={styles.textarea}
              value={restrictions}
              onChange={(e) => setRestrictions(e.target.value)}
              rows={3}
            />
          </label>
          {submitError ? <ErrorState title="Não foi possível salvar" description={submitError} /> : null}
          <Button type="submit" disabled={submitting}>
            {submitting ? "Salvando…" : "Salvar Brand Kit"}
          </Button>
        </form>
      </Card>

      <Card>
        <h2 className={styles.sectionTitle}>Brand Kits salvos</h2>
        {loadError ? (
          <ErrorState title="Não foi possível carregar" description={loadError} />
        ) : profiles === null ? (
          <Spinner label="Carregando Brand Kits" />
        ) : profiles.length === 0 ? (
          <EmptyState
            title="Nenhum Brand Kit ainda"
            description="Um aviso não-bloqueante aparece ao criar campanhas sem Brand Kit preenchido."
          />
        ) : (
          <ul className={styles.list}>
            {profiles.map((profile) => (
              <li key={profile.id} className={styles.listItem}>
                <p className={styles.itemName}>{profile.name}</p>
                <p className={styles.itemDetail}>{profile.tone}</p>
              </li>
            ))}
          </ul>
        )}
      </Card>
    </PageContainer>
  );
}
