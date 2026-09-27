"use client";

import { useEffect, useRef, useState } from "react";
import { Button } from "../../../../../components/Button";
import { Card } from "../../../../../components/Card";
import { ErrorState } from "../../../../../components/ErrorState";
import { Input } from "../../../../../components/Input";
import { PageContainer } from "../../../../../components/PageContainer";
import { PageHeader } from "../../../../../components/PageHeader";
import { Spinner } from "../../../../../components/Spinner";
import { ApiClientError, api } from "../../../../../lib/api/client";
import { isTestIdentityModeEnabled } from "../../../../../lib/auth/test-identity-client";
import { useAuth } from "../../../../../providers/AuthProvider";
import type {
  CommercialMembership,
  MemberInvitation,
} from "../../../../../types/onboarding";
import styles from "./page.module.css";

const BASE_ROLES = ["VIEWER", "MARKETER", "APPROVER", "FINANCE", "ADMIN"] as const;

export default function UsersPage() {
  const { me } = useAuth();
  const [members, setMembers] = useState<CommercialMembership[] | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [email, setEmail] = useState("");
  const [role, setRole] = useState("VIEWER");
  const [busy, setBusy] = useState(false);
  const [invite, setInvite] = useState<MemberInvitation | null>(null);
  const inviteIdem = useRef<string | null>(null);
  const testMode = isTestIdentityModeEnabled();
  const canManage = (me?.roles ?? []).some((r) => r === "OWNER" || r === "ADMIN");
  const isOwner = (me?.roles ?? []).includes("OWNER");
  const roleOptions = isOwner ? [...BASE_ROLES, "OWNER"] : [...BASE_ROLES];

  async function loadMembers() {
    try {
      setError(null);
      setMembers(await api.get<CommercialMembership[]>("/memberships"));
    } catch (err) {
      setError(err instanceof ApiClientError ? err.message : "Falha ao carregar usuários.");
    }
  }

  useEffect(() => {
    if (!canManage) return;
    let active = true;
    (async () => {
      try {
        const result = await api.get<CommercialMembership[]>("/memberships");
        if (active) setMembers(result);
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

  function stepUpHeaders(): Record<string, string> {
    // F1 exercises the existing dev/test step-up harness. In any non-test build this
    // header is deliberately absent and the backend remains fail-closed until F2 wires
    // the real reauthentication challenge.
    return testMode ? { "x-step-up-token": "f1-web-test-step-up" } : {};
  }

  async function handleInvite() {
    if (!email.trim()) return;
    setBusy(true);
    setError(null);
    setInvite(null);
    try {
      inviteIdem.current ??= "invite-" + crypto.randomUUID();
      const result = await api.post<MemberInvitation>(
        "/member-invitations",
        { email: email.trim(), roles: [role] },
        {
          headers: stepUpHeaders(),
          idempotencyKey: inviteIdem.current,
        },
      );
      setInvite(result);
      setEmail("");
      inviteIdem.current = null;
    } catch (err) {
      setError(err instanceof ApiClientError ? err.message : "Falha ao criar convite.");
    } finally {
      setBusy(false);
    }
  }

  async function changeStatus(member: CommercialMembership, action: "deactivate" | "reactivate") {
    setBusy(true);
    setError(null);
    try {
      await api.post<CommercialMembership>(
        "/memberships/" + member.id + "/" + action,
        undefined,
        {
          headers: stepUpHeaders(),
          idempotencyKey: action + "-" + member.id + "-" + crypto.randomUUID(),
        },
      );
      await loadMembers();
    } catch (err) {
      setError(
        err instanceof ApiClientError ? err.message : "Falha ao atualizar o acesso do usuário.",
      );
    } finally {
      setBusy(false);
    }
  }

  return (
    <PageContainer>
      <PageHeader
        title="Usuários"
        description="Convites e acessos pertencem ao tenant atual. Desativar preserva o histórico e revoga as sessões associadas."
      />

      {!testMode ? (
        <Card>
          <p className={styles.notice}>
            Operações administrativas exigem step-up real. O backend está fail-closed; o
            desafio de reautenticação da Web será conectado na Fase 2.
          </p>
        </Card>
      ) : null}

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
          <Button
            onClick={handleInvite}
            disabled={busy || !email.trim() || !testMode}
            data-testid="create-member-invitation"
          >
            Criar convite
          </Button>
        </div>
        {invite?.accept_token ? (
          <div className={styles.inviteResult} data-testid="invitation-result">
            <p>Convite criado para {invite.email}.</p>
            <p className={styles.token}>
              /accept-invite?token={invite.accept_token}
            </p>
            <p className={styles.notice}>
              O token é exibido apenas nesta criação. O servidor guarda somente seu hash.
            </p>
          </div>
        ) : null}
      </Card>

      <Card>
        <h2 className={styles.title}>Acessos deste tenant</h2>
        {members === null ? (
          <Spinner label="Carregando usuários" />
        ) : (
          <div className={styles.list}>
            {members.map((member) => (
              <div key={member.id} className={styles.row} data-testid={"member-" + member.id}>
                <div>
                  <strong>{member.email}</strong>
                  <p className={styles.detail}>
                    {member.roles.join(", ")} · {member.status}
                  </p>
                </div>
                {member.status === "ACTIVE" ? (
                  <Button
                    variant="secondary"
                    disabled={busy || !testMode}
                    onClick={() => changeStatus(member, "deactivate")}
                    data-testid={"deactivate-" + member.id}
                  >
                    Desativar
                  </Button>
                ) : (
                  <Button
                    variant="secondary"
                    disabled={busy || !testMode}
                    onClick={() => changeStatus(member, "reactivate")}
                    data-testid={"reactivate-" + member.id}
                  >
                    Reativar
                  </Button>
                )}
              </div>
            ))}
          </div>
        )}
      </Card>
    </PageContainer>
  );
}
