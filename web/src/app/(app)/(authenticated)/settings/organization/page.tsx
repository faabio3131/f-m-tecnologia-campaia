"use client";

import { useEffect, useState } from "react";
import { AdministrativeStepUpCard } from "../../../../../components/AdministrativeStepUpCard";
import { Button } from "../../../../../components/Button";
import { Card } from "../../../../../components/Card";
import { ErrorState } from "../../../../../components/ErrorState";
import { Input } from "../../../../../components/Input";
import { PageContainer } from "../../../../../components/PageContainer";
import { PageHeader } from "../../../../../components/PageHeader";
import { Spinner } from "../../../../../components/Spinner";
import { useAdministrativeStepUp } from "../../../../../hooks/useAdministrativeStepUp";
import { ApiClientError, api } from "../../../../../lib/api/client";
import { useAuth } from "../../../../../providers/AuthProvider";
import type { BusinessUnit } from "../../../../../types/onboarding";
import styles from "./page.module.css";

function UnitRow({
  unit,
  disabled,
  onRename,
  onStatus,
}: {
  unit: BusinessUnit;
  disabled: boolean;
  onRename: (unit: BusinessUnit, name: string) => Promise<void>;
  onStatus: (unit: BusinessUnit, action: "deactivate" | "reactivate") => Promise<void>;
}) {
  const [name, setName] = useState(unit.name);
  return (
    <div className={styles.unit} data-testid={"business-unit-" + unit.id}>
      <div className={styles.unitHeader}>
        <div>
          <strong>{unit.name}</strong>
          <p className={styles.detail}>{unit.status}</p>
        </div>
        <Button
          variant="secondary"
          disabled={disabled}
          onClick={() =>
            onStatus(unit, unit.status === "ACTIVE" ? "deactivate" : "reactivate")
          }
          data-testid={(unit.status === "ACTIVE" ? "deactivate-unit-" : "reactivate-unit-") + unit.id}
        >
          {unit.status === "ACTIVE" ? "Desativar" : "Reativar"}
        </Button>
      </div>
      <div className={styles.rename}>
        <Input
          label={"Nome da unidade " + unit.name}
          value={name}
          onChange={(event) => setName(event.target.value)}
        />
        <Button
          variant="secondary"
          disabled={disabled || !name.trim() || name.trim() === unit.name}
          onClick={() => onRename(unit, name)}
          data-testid={"rename-unit-" + unit.id}
        >
          Renomear
        </Button>
      </div>
    </div>
  );
}

export default function OrganizationSettingsPage() {
  const { me } = useAuth();
  const [units, setUnits] = useState<BusinessUnit[] | null>(null);
  const [newName, setNewName] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const stepUp = useAdministrativeStepUp();
  const canManage = (me?.roles ?? []).some((role) => role === "OWNER" || role === "ADMIN");

  async function loadUnits() {
    try {
      setUnits(await api.get<BusinessUnit[]>("/business-units"));
    } catch (err) {
      setError(err instanceof ApiClientError ? err.message : "Falha ao carregar unidades.");
    }
  }

  useEffect(() => {
    if (!canManage) return;
    let active = true;
    (async () => {
      try {
        const result = await api.get<BusinessUnit[]>("/business-units");
        if (active) setUnits(result);
      } catch (err) {
        if (active) {
          setError(err instanceof ApiClientError ? err.message : "Falha ao carregar unidades.");
        }
      }
    })();
    return () => {
      active = false;
    };
  }, [canManage]);

  if (!canManage) {
    return (
      <PageContainer>
        <PageHeader title="Organização" />
        <ErrorState
          title="Acesso restrito"
          description="Somente Owner ou Admin pode administrar unidades deste tenant."
        />
      </PageContainer>
    );
  }

  const sensitiveDisabled = busy || (!stepUp.testMode && !stepUp.ready);

  async function createUnit() {
    if (!newName.trim()) return;
    setBusy(true);
    setError(null);
    try {
      await api.post<BusinessUnit>(
        "/business-units",
        { name: newName.trim() },
        {
          headers: stepUp.headers(),
          idempotencyKey: "business-unit-create-" + crypto.randomUUID(),
        },
      );
      stepUp.consumePresentedToken();
      setNewName("");
      await loadUnits();
    } catch (err) {
      stepUp.noteError(err);
      setError(err instanceof ApiClientError ? err.message : "Falha ao criar unidade.");
    } finally {
      setBusy(false);
    }
  }

  async function renameUnit(unit: BusinessUnit, name: string) {
    setBusy(true);
    setError(null);
    try {
      await api.patch<BusinessUnit>(
        "/business-units/" + unit.id,
        { name: name.trim() },
        {
          headers: stepUp.headers(),
          idempotencyKey: "business-unit-rename-" + unit.id + "-" + crypto.randomUUID(),
        },
      );
      stepUp.consumePresentedToken();
      await loadUnits();
    } catch (err) {
      stepUp.noteError(err);
      setError(err instanceof ApiClientError ? err.message : "Falha ao renomear unidade.");
    } finally {
      setBusy(false);
    }
  }

  async function setStatus(unit: BusinessUnit, action: "deactivate" | "reactivate") {
    setBusy(true);
    setError(null);
    try {
      await api.post<BusinessUnit>(
        "/business-units/" + unit.id + "/" + action,
        undefined,
        {
          headers: stepUp.headers(),
          idempotencyKey: "business-unit-" + action + "-" + unit.id + "-" + crypto.randomUUID(),
        },
      );
      stepUp.consumePresentedToken();
      await loadUnits();
    } catch (err) {
      stepUp.noteError(err);
      setError(
        err instanceof ApiClientError ? err.message : "Falha ao alterar estado da unidade.",
      );
    } finally {
      setBusy(false);
    }
  }

  return (
    <PageContainer>
      <PageHeader
        title="Organização"
        description="Unidades de negócio do tenant atual. Uma unidade com usuários ativos não pode ser desativada até que os vínculos sejam realocados."
      />

      <AdministrativeStepUpCard
        ready={stepUp.ready}
        testMode={stepUp.testMode}
        message={stepUp.stepUpMessage}
        onIdToken={stepUp.onIdToken}
        onError={setError}
      />

      {error ? <ErrorState title="Não foi possível continuar" description={error} /> : null}

      <Card>
        <h2 className={styles.title}>Nova unidade</h2>
        <div className={styles.create}>
          <Input
            label="Nome da unidade"
            value={newName}
            onChange={(event) => setNewName(event.target.value)}
          />
          <Button
            disabled={sensitiveDisabled || !newName.trim()}
            onClick={createUnit}
            data-testid="create-business-unit"
          >
            Criar unidade
          </Button>
        </div>
      </Card>

      <Card>
        <h2 className={styles.title}>Unidades do tenant</h2>
        {units === null ? (
          <Spinner label="Carregando unidades" />
        ) : (
          <div className={styles.list}>
            {units.map((unit) => (
              <UnitRow
                key={unit.id}
                unit={unit}
                disabled={sensitiveDisabled}
                onRename={renameUnit}
                onStatus={setStatus}
              />
            ))}
          </div>
        )}
      </Card>
    </PageContainer>
  );
}
