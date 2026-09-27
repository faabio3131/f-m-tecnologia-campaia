"""Testes de autorizacao: RBAC + ABAC.

Ordem Mestre, item 14: testes de autorizacao e de isolamento multi-tenant sao obrigatorios
e bloqueiam o Gate de Seguranca (G2).
"""

from __future__ import annotations

import unittest
from datetime import datetime, timedelta, timezone
from decimal import Decimal

from campaia_core.permissions import (
    ROLE_PERMISSIONS,
    AccessDecision,
    DenialCode,
    Permission,
    Principal,
    Resource,
    Role,
    authorize,
    can_approve,
    dual_approval_complete,
)

NOW = datetime(2026, 8, 25, 12, 0, tzinfo=timezone.utc)
T1 = "tenant-1"
T2 = "tenant-2"


def _p(
    *roles: Role,
    user_id="u1",
    tenant=T1,
    units=None,
    mfa=True,
    step_up_min_ago: int | None = 1,
) -> Principal:
    return Principal(
        user_id=user_id,
        tenant_id=tenant,
        roles=frozenset(roles),
        business_unit_ids=units,
        mfa_enabled=mfa,
        step_up_at=None if step_up_min_ago is None else NOW - timedelta(minutes=step_up_min_ago),
    )


def _r(tenant=T1, unit=None, created_by=None) -> Resource:
    return Resource(tenant_id=tenant, business_unit_id=unit, created_by=created_by)


class TestIsolamentoPorTenant(unittest.TestCase):
    """I-04: o teste mais importante deste modulo."""

    def test_recurso_de_outro_tenant_responde_not_found(self):
        """NOT_FOUND, nao PERMISSION_DENIED: negar por permissao revelaria que existe."""
        d = authorize(_p(Role.OWNER), Permission.CAMPAIGN_VIEW, _r(tenant=T2), now=NOW)
        self.assertFalse(d.allowed)
        self.assertIs(d.code, DenialCode.NOT_FOUND)

    def test_nem_o_owner_atravessa_o_tenant(self):
        for perm in Permission:
            with self.subTest(perm=perm):
                d = authorize(_p(Role.OWNER), perm, _r(tenant=T2), now=NOW)
                self.assertFalse(d.allowed)
                self.assertIs(d.code, DenialCode.NOT_FOUND)

    def test_tenant_e_verificado_antes_de_qualquer_outra_regra(self):
        """Sem MFA, sem step-up, papel fraco: ainda assim a resposta e NOT_FOUND."""
        fraco = _p(Role.VIEWER, mfa=False, step_up_min_ago=None)
        d = authorize(fraco, Permission.BUDGET_CHANGE, _r(tenant=T2), now=NOW)
        self.assertIs(d.code, DenialCode.NOT_FOUND)


class TestEscopoDeUnidade(unittest.TestCase):
    def test_usuario_restrito_nao_acessa_outra_unidade(self):
        p = _p(Role.ADMIN, units=frozenset({"loja-a"}))
        d = authorize(p, Permission.CAMPAIGN_VIEW, _r(unit="loja-b"), now=NOW)
        self.assertFalse(d.allowed)
        self.assertIs(d.code, DenialCode.NOT_FOUND)

    def test_usuario_restrito_acessa_a_propria_unidade(self):
        p = _p(Role.ADMIN, units=frozenset({"loja-a"}))
        self.assertTrue(authorize(p, Permission.CAMPAIGN_VIEW, _r(unit="loja-a"), now=NOW))

    def test_sem_restricao_de_unidade_acessa_todas(self):
        p = _p(Role.ADMIN, units=None)
        self.assertTrue(authorize(p, Permission.CAMPAIGN_VIEW, _r(unit="loja-z"), now=NOW))

    def test_conjunto_vazio_de_unidades_nao_acessa_nenhuma(self):
        p = _p(Role.ADMIN, units=frozenset())
        self.assertFalse(authorize(p, Permission.CAMPAIGN_VIEW, _r(unit="loja-a"), now=NOW))


class TestRBAC(unittest.TestCase):
    def test_marketer_cria_mas_nao_publica(self):
        p = _p(Role.MARKETER)
        self.assertTrue(authorize(p, Permission.CAMPAIGN_CREATE, _r(), now=NOW))
        d = authorize(p, Permission.CAMPAIGN_PUBLISH, _r(), now=NOW)
        self.assertFalse(d.allowed)
        self.assertIs(d.code, DenialCode.PERMISSION_DENIED)

    def test_marketer_ve_verba_mas_nao_altera(self):
        p = _p(Role.MARKETER)
        self.assertTrue(authorize(p, Permission.BUDGET_VIEW, _r(), now=NOW))
        self.assertFalse(authorize(p, Permission.BUDGET_CHANGE, _r(), now=NOW))

    def test_viewer_nao_altera_nada(self):
        p = _p(Role.VIEWER)
        for perm in (
            Permission.CAMPAIGN_CREATE,
            Permission.CAMPAIGN_PUBLISH,
            Permission.BUDGET_CHANGE,
            Permission.APPROVAL_DECIDE,
            Permission.CONNECTION_MANAGE,
            Permission.AUTONOMY_CHANGE,
        ):
            with self.subTest(perm=perm):
                self.assertFalse(authorize(p, perm, _r(), now=NOW))

    def test_papeis_somam_permissoes(self):
        p = _p(Role.MARKETER, Role.APPROVER)
        self.assertTrue(authorize(p, Permission.CAMPAIGN_CREATE, _r(), now=NOW))
        self.assertTrue(authorize(p, Permission.APPROVAL_DECIDE, _r(), now=NOW))

    def test_somente_owner_muda_autonomia(self):
        self.assertTrue(authorize(_p(Role.OWNER), Permission.AUTONOMY_CHANGE, _r(), now=NOW))
        for role in (Role.ADMIN, Role.FINANCE, Role.APPROVER, Role.MARKETER, Role.VIEWER):
            with self.subTest(role=role):
                self.assertFalse(
                    authorize(_p(role), Permission.AUTONOMY_CHANGE, _r(), now=NOW)
                )

    def test_nenhum_papel_alem_do_owner_tem_todas_as_permissoes(self):
        for role, perms in ROLE_PERMISSIONS.items():
            if role is Role.OWNER:
                continue
            with self.subTest(role=role):
                self.assertNotEqual(perms, frozenset(Permission))


class TestStepUpEMfa(unittest.TestCase):
    """T-01: sessao aberta no passado nao autoriza acao sensivel agora."""

    def test_step_up_vencido_bloqueia(self):
        p = _p(Role.ADMIN, step_up_min_ago=30)
        d = authorize(p, Permission.BUDGET_CHANGE, _r(), now=NOW)
        self.assertFalse(d.allowed)
        self.assertIs(d.code, DenialCode.STEP_UP_REQUIRED)

    def test_step_up_ausente_bloqueia(self):
        p = _p(Role.ADMIN, step_up_min_ago=None)
        self.assertIs(
            authorize(p, Permission.CONNECTION_MANAGE, _r(), now=NOW).code,
            DenialCode.STEP_UP_REQUIRED,
        )

    def test_step_up_recente_libera(self):
        p = _p(Role.ADMIN, step_up_min_ago=2)
        self.assertTrue(authorize(p, Permission.CONNECTION_MANAGE, _r(), now=NOW))

    def test_leitura_nao_exige_step_up(self):
        p = _p(Role.VIEWER, step_up_min_ago=None)
        self.assertTrue(authorize(p, Permission.CAMPAIGN_VIEW, _r(), now=NOW))

    def test_kill_switch_nao_exige_step_up(self):
        """Emergencia nao espera reautenticacao: o kill switch so REDUZ efeito."""
        p = _p(Role.APPROVER, step_up_min_ago=None, mfa=False)
        self.assertTrue(authorize(p, Permission.KILL_SWITCH, _r(), now=NOW))

    def test_sem_mfa_nao_altera_verba(self):
        p = _p(Role.FINANCE, mfa=False)
        self.assertIs(
            authorize(p, Permission.BUDGET_CHANGE, _r(), now=NOW).code,
            DenialCode.MFA_REQUIRED,
        )

    def test_sem_mfa_ainda_consulta(self):
        p = _p(Role.FINANCE, mfa=False)
        self.assertTrue(authorize(p, Permission.BUDGET_VIEW, _r(), now=NOW))


class TestTetoDeValor(unittest.TestCase):
    def test_valor_acima_do_teto_do_papel_bloqueia(self):
        p = _p(Role.APPROVER)  # teto 5000
        d = authorize(
            p, Permission.APPROVAL_DECIDE, _r(), now=NOW, amount=Decimal("7500")
        )
        self.assertFalse(d.allowed)
        self.assertIs(d.code, DenialCode.VALUE_CEILING)

    def test_valor_dentro_do_teto_passa(self):
        p = _p(Role.APPROVER)
        self.assertTrue(
            authorize(p, Permission.APPROVAL_DECIDE, _r(), now=NOW, amount=Decimal("4999"))
        )

    def test_owner_nao_tem_teto(self):
        p = _p(Role.OWNER)
        self.assertTrue(
            authorize(
                p, Permission.APPROVAL_DECIDE, _r(), now=NOW, amount=Decimal("999999")
            )
        )

    def test_papel_mais_alto_prevalece_no_teto(self):
        p = _p(Role.APPROVER, Role.FINANCE)  # 5000 e 50000
        self.assertTrue(
            authorize(p, Permission.APPROVAL_DECIDE, _r(), now=NOW, amount=Decimal("40000"))
        )


class TestSegregacaoDeFuncoes(unittest.TestCase):
    """I-09: sem isto, 'aprovacao dupla' vira a mesma pessoa clicando duas vezes."""

    def test_quem_propos_nao_aprova(self):
        p = _p(Role.ADMIN, user_id="u1")
        d = can_approve(p, _r(created_by="u1"), now=NOW, requester_id="u1")
        self.assertFalse(d.allowed)
        self.assertIs(d.code, DenialCode.SEPARATION_OF_DUTIES)

    def test_outro_usuario_aprova(self):
        p = _p(Role.ADMIN, user_id="u2")
        self.assertTrue(can_approve(p, _r(created_by="u1"), now=NOW, requester_id="u1"))

    def test_ninguem_vota_duas_vezes(self):
        p = _p(Role.ADMIN, user_id="u2")
        d = can_approve(
            p,
            _r(),
            now=NOW,
            requester_id="u1",
            already_decided_by=frozenset({"u2"}),
        )
        self.assertIs(d.code, DenialCode.SEPARATION_OF_DUTIES)

    def test_aprovacao_dupla_exige_dois_atores_distintos(self):
        self.assertFalse(dual_approval_complete(frozenset({"u2"})))
        self.assertTrue(dual_approval_complete(frozenset({"u2", "u3"})))

    def test_segregacao_nao_substitui_permissao(self):
        """Usuario sem APPROVAL_DECIDE e barrado antes da segregacao de funcoes."""
        p = _p(Role.MARKETER, user_id="u2")
        d = can_approve(p, _r(), now=NOW, requester_id="u1")
        self.assertIs(d.code, DenialCode.PERMISSION_DENIED)

    def test_aprovador_de_outro_tenant_nem_chega_na_segregacao(self):
        p = _p(Role.ADMIN, user_id="u2", tenant=T2)
        d = can_approve(p, _r(tenant=T1), now=NOW, requester_id="u1")
        self.assertIs(d.code, DenialCode.NOT_FOUND)


class TestDecisaoComoBooleano(unittest.TestCase):
    def test_decisao_pode_ser_usada_em_if(self):
        self.assertTrue(bool(AccessDecision(True)))
        self.assertFalse(bool(AccessDecision(False, DenialCode.PERMISSION_DENIED)))

    def test_toda_negativa_tem_codigo_e_motivo(self):
        p = _p(Role.VIEWER, mfa=False, step_up_min_ago=None)
        casos = [
            (Permission.BUDGET_CHANGE, _r()),
            (Permission.CAMPAIGN_VIEW, _r(tenant=T2)),
            (Permission.CAMPAIGN_PUBLISH, _r()),
        ]
        for perm, res in casos:
            with self.subTest(perm=perm):
                d = authorize(p, perm, res, now=NOW)
                self.assertFalse(d.allowed)
                self.assertIsNotNone(d.code)
                self.assertTrue(d.reason)


if __name__ == "__main__":
    unittest.main(verbosity=2)
