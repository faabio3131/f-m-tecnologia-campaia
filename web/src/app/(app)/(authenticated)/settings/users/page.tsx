"use client";

import { useEffect, useRef, useState } from "react";
import { AdministrativeStepUpCard } from "../../../../../components/AdministrativeStepUpCard";
import { Button } from "../../../../../components/Button";
import { Card } from "../../../../../components/Card";
import { ErrorState } from "../../../../../components/ErrorState";
import { Input } from "../../../../../components/Input";
import { PageContainer } from "../../../../../components/PageContainer";
import { PageHeader } from "../../../../../components/PageHeader";
import { Spinner } from "../../../../../components/Spinner";
import { ApiClientError, api } from "../../../../../lib/api/client";
import { useAdministrativeStepUp } from "../../../../../hooks/useAdministrativeStepUp";
import { useAuth } from "../../../../../providers/AuthProvider";
import type {
  BusinessUnit,
  CommercialMembership,
  MemberInvitation,
} from "../../../../../types/onboarding";
import styles from "./page.module.css";

const BASE_ROLES = ["VIEWER", "MARKETER", "APPROVER", "FINANCE", "ADMIN"] as const;
const ALL_ROLES = [...BASE_ROLES, "OWNER"] as const;

function MemberAccessEditor({
  member,
  units,
  actorIsOwner,
  disabled,
  onSave,
}: {
  member: CommercialMembership;
  units: BusinessUnit[];
  actorIsOwner: boolean;
  disabled: boolean;
  onSave: (roles: string[], businessUnitId: string) => Promise<void>;
}) {
  const [roles, setRoles] = useState<string[]>(member.roles);
  const [businessUnitId, setBusinessUnitId] = useState(
    member.business_unit_id ?? units.find((unit) => unit.status === "ACTIVE")?.id ?? "",
  );
  const activeUnits = units.filter((unit) => unit.status === "ACTIVE");

  function toggleRole(role: string) {
    setRoles((current) =>
      current.includes(role)
        ? current.filter((item) => item !== role)
        : [...current, role],
    );
  }

  return (
    <div className={styles.accessEditor}>
      <div className={styles.roles}>
        {ALL_ROLES.map((role) => (
          <label key={role} className={styles.roleOption}>
            <input
              type="checkbox"
              checked={roles.includes(role)}
              disabled={disabled || (role === "OWNER" && !actorIsOwner)}
              onChange={() => toggleRole(role)}
              data-testid={"role-" + member.id + "-" + role}
            />
            {role}
          </label>
        ))}
      </div>
      <label className={styles.selectLabel}>
        Unidade de negócio
        <select
          className={styles.select}
          value={businessUnitId}
          disabled={disabled}
          onChange={(event) => setBusinessUnitId(event.target.value)}
          data-testid={"unit-select-" + member.id}
        >
          {activeUnits.map((unit) => (
            <option key={unit.id} value={unit.id}>
              {unit.name}
            </option>
          ))}
        </select>
      </label>
      <Button
        variant="secondary"
        disabled={disabled || roles.length === 0 || !businessUnitId}
        onClick={() => onSave(roles, businessUnitId)}
        data-testid={"save-access-" + member.id}
      >
        Salvar acesso
      </Button>
    </div>
  );
}

export default function UsersPage() {
  const { me } = useAuth();
  const [members, setMembers] = useState<CommercialMembership[] | null>(null);
  const [units, setUnits] = useState<BusinessUnit[] | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [email, setEmail] = useState("");
  const [role, setRole] = useState("VIEWER");
  const [inviteUnitId, setInviteUnitId] = useState("");
  const [busy, setBusy] = useState(false);
  const [invite, setInvite] = useState<MemberInvitation | null>(null);
  const inviteIdem = useRef<string | null>(null);
  const stepUp = useAdministrativeStepUp();
  const canManage = (me?.roles ?? []).some((r) => r === "OWNER" || r === "ADMIN");
  const isOwner = (me?.roles ?? []).includes("OWNER");
  const roleOptions = isOwner ? [...BASE_ROLES, "OWNER"] : [...BASE_ROLES];

  async function loadData() {
    try {
      setError(null);
      const [memberResult, unitResult] = await Promise.all([
        api.get<CommercialMembership[]>("/memberships"),
        api.get<BusinessUnit[]>("/business-units"),
      ]);
      setMembers(memberResult);
      setUnits(unitResult);
      if (!inviteUnitId) {
        setInviteUnitId(unitResult.find((unit) => unit.status === "ACTIVE")?.id ?? "");
      }
    } catch (err) {
      setError(err instanceof ApiClientError ? err.message : "Falha ao carregar usuários.");
    }
  }

  useEffect(() => {
    if (!canManage) return;
    let active = true;
    (async () => {
      try {
        const [memberResult, unitResult] = await Promise.all([
          api.get<CommercialMembership[]>("/memberships"),
          api.get<BusinessUnit[]>("/business-units"),
        ]);
        if (!active) return;
        setMembers(memberResult);
        setUnits(unitResult);
        setInviteUnitId(unitResult.find((unit) => unit.status === "ACTIVE")?.id ?? "");
      } catch (err) {
        if (active) {
          setError(
            err instanceof ApiClientError ? err.message : "Falha ao carregar usuários.",
          );
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
        <PageHeader title="Usuários" />
        <ErrorState
          title="Acesso restrito"
          description="Somente Owner ou Admin pode administrar usuários deste tenant."
        />
      </PageContainer>
    );
  }

  async function handleInvite() {
    if (!email.trim() || !inviteUnitId) return;
    setBusy(true);
    setError(null);
    setInvite(null);
    try {
      inviteIdem.current ??= "invite-" + crypto.randomUUID();
      const result = await api.post<MemberInvitation>(
        "/member-invitations",
        { email: email.trim(), roles: [role], business_unit_id: inviteUnitId },
        {
          headers: stepUp.headers(),
          idempotencyKey: inviteIdem.current,
        },
      );
      stepUp.consumePresentedToken();
      setInvite(result);
      setEmail("");
      inviteIdem.current = null;
    } catch (err) {
      stepUp.noteError(err);
      setError(err instanceof ApiClientError ? err.message : "Falha ao criar convite.");
    } finally {
      setBusy(false);
    }
  }

  async function changeStatus(
    member: CommercialMembership,
    action: "deactivate" | "reactivate",
  ) {
    setBusy(true);
    setError(null);
    try {
      await api.post<CommercialMembership>(
        "/memberships/" + member.id + "/" + action,
        undefined,
        {
          headers: stepUp.headers(),
          idempotencyKey: action + "-" + member.id + "-" + crypto.randomUUID(),
        },
      );
      stepUp.consumePresentedToken();
      await loadData();
    } catch (err) {
      stepUp.noteError(err);
      setError(
        err instanceof ApiClientError ? err.message : "Falha ao atualizar o acesso do usuário.",
      );
    } finally {
      setBusy(false);
    }
  }

  async function saveAccess(
    member: CommercialMembership,
    roles: string[],
    businessUnitId: string,
  ) {
    setBusy(true);
    setError(null);
    try {
      await api.patch<CommercialMembership>(
        "/memberships/" + member.id,
        { roles, business_unit_id: businessUnitId },
        {
          headers: stepUp.headers(),
          idempotencyKey: "member-access-" + member.id + "-" + crypto.randomUUID(),
        },
      );
      stepUp.consumePresentedToken();
      await loadData();
    } catch (err) {
      stepUp.noteError(err);
      setError(
        err instanceof ApiClientError ? err.message : "Falha ao atualizar papéis/unidade.",
      );
    } finally {
      setBusy(false);
    }
  }

  const activeUnits = (units ?? []).filter((unit) => unit.status === "ACTIVE");
  const sensitiveDisabled = busy || (!stepUp.testMode && !stepUp.ready);

  return (
    <PageContainer>
      <PageHeader
        title="Usuários"
        description="Convites, papéis, unidade e ciclo de acesso pertencem ao tenant atual. Mudanças de autoridade revogam sessões antigas."
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
        <h2 className={styles.title}>Convidar usuário</h2>
        <div className={styles.form}>
          <Input
            label="E-mail"
            type="email"
            value={email}
            onChange={(e) => setEmail(e.target.value)}
          />
          <label className={styles.selectLabel}>
            Papel
            <select
              className={styles.select}
              value={role}
              onChange={(e) => setRole(e.target.value)}
            >
              {roleOptions.map((item) => (
                <option key={item} value={item}>
                  {item}
                </option>
              ))}
            </select>
          </label>
          <label className={styles.selectLabel}>
            Unidade de negócio
            <select
              className={styles.select}
              value={inviteUnitId}
              onChange={(e) => setInviteUnitId(e.target.value)}
            >
              {activeUnits.map((unit) => (
                <option key={unit.id} value={unit.id}>
                  {unit.name}
                </option>
              ))}
            </select>
          </label>
          <Button
            onClick={handleInvite}
            disabled={sensitiveDisabled || !email.trim() || !inviteUnitId}
            data-testid="create-member-invitation"
          >
            Criar convite
          </Button>
        </div>
        {invite?.accept_token ? (
          <div className={styles.inviteResult} data-testid="invitation-result">
            <p>Convite criado para {invite.email}.</p>
            <p className={styles.token}>/accept-invite?token={invite.accept_token}</p>
            <p className={styles.notice}>
              O token é exibido apenas nesta criação. O servidor guarda somente seu hash.
            </p>
          </div>
        ) : null}
      </Card>

      <Card>
        <h2 className={styles.title}>Acessos deste tenant</h2>
        {members === null || units === null ? (
          <Spinner label="Carregando usuários" />
        ) : (
          <div className={styles.list}>
            {members.map((member) => (
              <div key={member.id} className={styles.memberCard} data-testid={"member-" + member.id}>
                <div className={styles.row}>
                  <div>
                    <strong>{member.email}</strong>
                    <p className={styles.detail}>
                      {member.roles.join(", ")} · {member.status}
                    </p>
                  </div>
                  {member.status === "ACTIVE" ? (
                    <Button
                      variant="secondary"
                      disabled={sensitiveDisabled}
                      onClick={() => changeStatus(member, "deactivate")}
                      data-testid={"deactivate-" + member.id}
                    >
                      Desativar
                    </Button>
                  ) : (
                    <Button
                      variant="secondary"
                      disabled={sensitiveDisabled}
                      onClick={() => changeStatus(member, "reactivate")}
                      data-testid={"reactivate-" + member.id}
                    >
                      Reativar
                    </Button>
                  )}
                </div>
                <MemberAccessEditor
                  member={member}
                  units={units}
                  actorIsOwner={isOwner}
                  disabled={sensitiveDisabled || member.status !== "ACTIVE"}
                  onSave={(roles, unitId) => saveAccess(member, roles, unitId)}
                />
              </div>
            ))}
          </div>
        )}
      </Card>
    </PageContainer>
  );
}
