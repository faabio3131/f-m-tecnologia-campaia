"""Motor de assinatura, entitlements e lifecycle comercial do CampaIA.

Planos e regras comerciais sao dados externos. Este modulo modela os estados e transicoes
permitidas sem fixar nomes, precos, franquias ou duracao real de trial em codigo.

F5 / WP-F05-02:
- assinatura nova nunca nasce ACTIVE por simples selecao de plano;
- trial so existe quando a duracao foi configurada no catalogo;
- expiracao e deterministica;
- pagamento confirmado e a autoridade que ativa entitlement pago;
- plano pode declarar limites/canais/capacidades sem hardcode por tenant.
"""

from __future__ import annotations

from dataclasses import dataclass, replace
from datetime import datetime, timedelta, timezone
from decimal import Decimal
from enum import StrEnum


def _d(value: Decimal | int | str) -> Decimal:
    return value if isinstance(value, Decimal) else Decimal(str(value))


class SubscriptionStatus(StrEnum):
    PENDING_PAYMENT = "PENDING_PAYMENT"
    TRIAL = "TRIAL"
    ACTIVE = "ACTIVE"
    PAST_DUE = "PAST_DUE"
    EXPIRED = "EXPIRED"
    CANCELED = "CANCELED"


class ChargeStatus(StrEnum):
    OPEN = "OPEN"
    AWAITING_PAYMENT = "AWAITING_PAYMENT"
    SETTLED = "SETTLED"
    FAILED = "FAILED"


class PlanChangeKind(StrEnum):
    UPGRADE = "UPGRADE"
    DOWNGRADE = "DOWNGRADE"


class PlanChangeActivation(StrEnum):
    SETTLED_PAYMENT = "SETTLED_PAYMENT"


class PlanChangeBillingMode(StrEnum):
    TARGET_PLAN_FULL_CYCLE = "TARGET_PLAN_FULL_CYCLE"


class ChargePurpose(StrEnum):
    REGULAR = "REGULAR"
    PLAN_CHANGE = "PLAN_CHANGE"
    REACTIVATION = "REACTIVATION"


class CancellationMode(StrEnum):
    IMMEDIATE = "IMMEDIATE"


class ReactivationMode(StrEnum):
    PAYMENT_REQUIRED = "PAYMENT_REQUIRED"


class ReactivationBillingMode(StrEnum):
    CURRENT_PLAN_FULL_CYCLE = "CURRENT_PLAN_FULL_CYCLE"


class PastDueAccessMode(StrEnum):
    ALLOW_DURING_GRACE = "ALLOW_DURING_GRACE"
    BLOCK_IMMEDIATELY = "BLOCK_IMMEDIATELY"


@dataclass(frozen=True, slots=True)
class DunningPolicy:
    """Politica comercial de inadimplencia do plano.

    O motor interpreta esta configuracao; nao inventa dias, cadencia ou acesso.
    reminder_offsets_days sao offsets inteiros a partir de past_due_at.
    """

    grace_period_days: int
    access_mode: PastDueAccessMode
    reminder_offsets_days: tuple[int, ...] = ()

    def __post_init__(self) -> None:
        if (
            isinstance(self.grace_period_days, bool)
            or not isinstance(self.grace_period_days, int)
            or self.grace_period_days < 0
        ):
            raise ValueError("grace_period_days deve ser inteiro >= 0.")

        previous: int | None = None
        for offset in self.reminder_offsets_days:
            if isinstance(offset, bool) or not isinstance(offset, int) or offset < 0:
                raise ValueError("reminder_offsets_days deve conter inteiros >= 0.")
            if previous is not None and offset <= previous:
                raise ValueError(
                    "reminder_offsets_days deve estar em ordem estritamente crescente."
                )
            previous = offset


@dataclass(frozen=True, slots=True)
class PlanChangeRule:
    target_plan_id: str
    kind: PlanChangeKind
    activation: PlanChangeActivation = PlanChangeActivation.SETTLED_PAYMENT
    billing_mode: PlanChangeBillingMode | None = None

    def __post_init__(self) -> None:
        if not self.target_plan_id.strip():
            raise ValueError("target_plan_id e obrigatorio.")


@dataclass(frozen=True, slots=True)
class PlanEntitlements:
    """Entitlements estruturados do plano.

    Todos os valores sao configuracao comercial. None significa "nao congelado/configurado",
    nunca "ilimitado". Listas vazias significam que a capacidade nao foi concedida.
    """

    max_users: int | None = None
    max_active_campaigns: int | None = None
    channels: tuple[str, ...] = ()
    ai_capabilities: tuple[str, ...] = ()
    resources: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        for name, value in (
            ("max_users", self.max_users),
            ("max_active_campaigns", self.max_active_campaigns),
        ):
            if value is not None and (
                isinstance(value, bool) or not isinstance(value, int) or value < 1
            ):
                raise ValueError(f"{name} deve ser inteiro positivo quando configurado.")

        for name, values in (
            ("channels", self.channels),
            ("ai_capabilities", self.ai_capabilities),
            ("resources", self.resources),
        ):
            cleaned = tuple(v.strip() for v in values)
            if any(not v for v in cleaned):
                raise ValueError(f"{name} nao pode conter valores vazios.")
            if len(set(cleaned)) != len(cleaned):
                raise ValueError(f"{name} nao pode conter valores duplicados.")


@dataclass(frozen=True, slots=True)
class PlanDefinition:
    """Um plano comercial. Dado de configuracao — nunca um valor fixo em codigo."""

    plan_id: str
    name: str
    monthly_price: Decimal
    included_credits: Decimal
    extra_credit_unit_price: Decimal
    # Compatibilidade com o CURRENT historico. O carregador sincroniza este valor com
    # entitlements.max_users quando ambos forem fornecidos.
    max_users: int | None = None
    currency: str = "BRL"
    trial_days: int | None = None
    entitlements: PlanEntitlements | None = None
    plan_changes: tuple[PlanChangeRule, ...] = ()
    cancellation_mode: CancellationMode | None = None
    reactivation_mode: ReactivationMode | None = None
    reactivation_billing_mode: ReactivationBillingMode | None = None
    dunning_policy: DunningPolicy | None = None

    def __post_init__(self) -> None:
        if not self.plan_id.strip():
            raise ValueError("plan_id e obrigatorio.")
        if not self.name.strip():
            raise ValueError("name e obrigatorio.")
        if self.monthly_price <= 0:
            raise ValueError("monthly_price deve ser positivo.")
        if self.included_credits < 0:
            raise ValueError("included_credits nao pode ser negativo.")
        if self.extra_credit_unit_price < 0:
            raise ValueError("extra_credit_unit_price nao pode ser negativo.")
        if self.max_users is not None and (
            isinstance(self.max_users, bool)
            or not isinstance(self.max_users, int)
            or self.max_users < 1
        ):
            raise ValueError("max_users deve ser inteiro positivo quando configurado.")
        if self.currency != "BRL":
            raise ValueError("apenas BRL e suportado nesta versao.")
        if self.trial_days is not None and (
            isinstance(self.trial_days, bool)
            or not isinstance(self.trial_days, int)
            or self.trial_days < 1
        ):
            raise ValueError("trial_days deve ser inteiro positivo quando configurado.")
        if (
            self.entitlements is not None
            and self.max_users is not None
            and self.entitlements.max_users is not None
            and self.max_users != self.entitlements.max_users
        ):
            raise ValueError(
                "max_users historico e entitlements.max_users precisam coincidir."
            )
        targets = [rule.target_plan_id for rule in self.plan_changes]
        if len(set(targets)) != len(targets):
            raise ValueError("plan_changes nao pode repetir target_plan_id.")
        if self.plan_id in targets:
            raise ValueError("plan_changes nao pode apontar para o proprio plano.")

    @property
    def effective_max_users(self) -> int | None:
        if self.entitlements is not None and self.entitlements.max_users is not None:
            return self.entitlements.max_users
        return self.max_users


@dataclass(frozen=True, slots=True)
class Subscription:
    tenant_id: str
    customer_ref: str
    customer_document: str
    plan: PlanDefinition
    status: SubscriptionStatus = SubscriptionStatus.PENDING_PAYMENT
    trial_started_at: datetime | None = None
    trial_ends_at: datetime | None = None
    activated_at: datetime | None = None
    pending_plan: PlanDefinition | None = None
    pending_plan_change_kind: PlanChangeKind | None = None
    pending_plan_change_billing_mode: PlanChangeBillingMode | None = None
    canceled_at: datetime | None = None
    reactivation_requested_at: datetime | None = None
    past_due_at: datetime | None = None
    grace_period_ends_at: datetime | None = None
    dunning_reminders_sent: int = 0
    last_dunning_at: datetime | None = None

    def __post_init__(self) -> None:
        if not self.customer_document.strip():
            raise ValueError("customer_document (CPF/CNPJ) e obrigatorio.")
        if self.status is SubscriptionStatus.TRIAL:
            if self.trial_started_at is None or self.trial_ends_at is None:
                raise ValueError("assinatura TRIAL exige trial_started_at e trial_ends_at.")
            if self.trial_ends_at <= self.trial_started_at:
                raise ValueError("trial_ends_at deve ser posterior a trial_started_at.")
        if self.status is SubscriptionStatus.ACTIVE and self.activated_at is None:
            # Objetos historicos/testes podem informar ACTIVE explicitamente; mantemos
            # compatibilidade sem inventar timestamp de ativacao.
            pass
        if (
            isinstance(self.dunning_reminders_sent, bool)
            or not isinstance(self.dunning_reminders_sent, int)
            or self.dunning_reminders_sent < 0
        ):
            raise ValueError("dunning_reminders_sent deve ser inteiro >= 0.")


@dataclass(frozen=True, slots=True)
class ChargeLineItem:
    description: str
    amount: Decimal


@dataclass(frozen=True, slots=True)
class SubscriptionCharge:
    """Cobranca de UM ciclo (competencia). Determinada — nunca recalculada em silencio."""

    billing_id: str
    tenant_id: str
    customer_ref: str
    customer_document: str
    competence: str
    currency: str
    line_items: tuple[ChargeLineItem, ...]
    status: ChargeStatus = ChargeStatus.OPEN
    # Defaults preserve decoding of charges persisted before WP-F05-03.
    plan_id: str | None = None
    purpose: ChargePurpose = ChargePurpose.REGULAR

    @property
    def amount(self) -> Decimal:
        return sum((item.amount for item in self.line_items), start=Decimal("0"))


def start_trial(subscription: Subscription, *, now: datetime | None = None) -> Subscription:
    """Inicia trial somente quando a duracao foi configurada no plano.

    Nao ha duracao default. Ausencia de trial_days e HUMAN_DECISION pendente e falha fechada.
    """

    if subscription.status is not SubscriptionStatus.PENDING_PAYMENT:
        raise ValueError(
            f"trial nao pode iniciar a partir de {subscription.status.value}; "
            "novo trial apos expiracao exige politica comercial explicita."
        )
    if subscription.plan.trial_days is None:
        raise ValueError("plano sem trial_days configurado nao pode iniciar trial.")
    if subscription.plan.entitlements is None:
        raise ValueError("plano sem entitlements configurados nao pode iniciar trial.")

    started_at = now or datetime.now(timezone.utc)
    return replace(
        subscription,
        status=SubscriptionStatus.TRIAL,
        trial_started_at=started_at,
        trial_ends_at=started_at + timedelta(days=subscription.plan.trial_days),
        activated_at=None,
    )


def refresh_trial_status(
    subscription: Subscription, *, now: datetime | None = None
) -> Subscription:
    """Expira trial deterministica e idempotentemente quando o prazo termina."""

    if subscription.status is not SubscriptionStatus.TRIAL:
        return subscription
    if subscription.trial_ends_at is None:
        raise ValueError("assinatura TRIAL sem trial_ends_at e invalida.")

    reference = now or datetime.now(timezone.utc)
    if reference < subscription.trial_ends_at:
        return subscription
    return replace(subscription, status=SubscriptionStatus.EXPIRED)




def mark_past_due(
    subscription: Subscription,
    *,
    overdue_at: datetime | None = None,
    billed_plan_id: str | None,
    billed_purpose: ChargePurpose = ChargePurpose.REGULAR,
) -> Subscription:
    """Marca inadimplencia somente a partir de uma cobranca regular identificada.

    A politica de grace/dunning precisa existir no catalogo. Ausencia de configuracao,
    cobranca legada sem plan_id ou outro proposito falham fechados.
    """

    if billed_purpose is not ChargePurpose.REGULAR:
        raise ValueError("somente cobranca REGULAR pode marcar assinatura PAST_DUE.")
    if billed_plan_id is None:
        raise ValueError("cobranca sem plan_id nao pode marcar assinatura PAST_DUE.")
    if billed_plan_id != subscription.plan.plan_id:
        raise ValueError("cobranca vencida nao corresponde ao plano vigente.")
    if subscription.status is SubscriptionStatus.PAST_DUE:
        return subscription
    if subscription.status is not SubscriptionStatus.ACTIVE:
        raise ValueError("PAST_DUE exige assinatura ACTIVE.")

    policy = subscription.plan.dunning_policy
    if policy is None:
        raise ValueError("plano sem dunning_policy nao pode entrar em PAST_DUE.")

    at = overdue_at or datetime.now(timezone.utc)
    if at.tzinfo is None:
        raise ValueError("overdue_at deve ser timezone-aware.")

    return replace(
        subscription,
        status=SubscriptionStatus.PAST_DUE,
        past_due_at=at,
        grace_period_ends_at=at + timedelta(days=policy.grace_period_days),
        dunning_reminders_sent=0,
        last_dunning_at=None,
    )


def past_due_is_in_grace(
    subscription: Subscription, *, now: datetime | None = None
) -> bool:
    """Retorna True somente quando a politica explicita permite acesso dentro do grace."""

    if subscription.status is not SubscriptionStatus.PAST_DUE:
        return False
    policy = subscription.plan.dunning_policy
    if policy is None or policy.access_mode is PastDueAccessMode.BLOCK_IMMEDIATELY:
        return False
    if subscription.grace_period_ends_at is None:
        return False
    reference = now or datetime.now(timezone.utc)
    if reference.tzinfo is None:
        raise ValueError("now deve ser timezone-aware.")
    return reference < subscription.grace_period_ends_at


def next_dunning_reminder_at(subscription: Subscription) -> datetime | None:
    """Calcula a proxima acao de cobranca sem executar canal externo."""

    if subscription.status is not SubscriptionStatus.PAST_DUE:
        return None
    policy = subscription.plan.dunning_policy
    if policy is None or subscription.past_due_at is None:
        return None
    index = subscription.dunning_reminders_sent
    if index >= len(policy.reminder_offsets_days):
        return None
    return subscription.past_due_at + timedelta(days=policy.reminder_offsets_days[index])


def dunning_reminder_is_due(
    subscription: Subscription, *, now: datetime | None = None
) -> bool:
    due_at = next_dunning_reminder_at(subscription)
    if due_at is None:
        return False
    reference = now or datetime.now(timezone.utc)
    if reference.tzinfo is None:
        raise ValueError("now deve ser timezone-aware.")
    return reference >= due_at


def record_dunning_reminder(
    subscription: Subscription, *, now: datetime | None = None
) -> Subscription:
    """Registra uma tentativa ja executada pelo canal externo.

    Este dominio nao envia e-mail/SMS e nao solicita negativacao. O caller somente pode
    registrar o passo quando a agenda governada estiver vencida.
    """

    if subscription.status is not SubscriptionStatus.PAST_DUE:
        raise ValueError("dunning exige assinatura PAST_DUE.")
    at = now or datetime.now(timezone.utc)
    if at.tzinfo is None:
        raise ValueError("now deve ser timezone-aware.")
    if not dunning_reminder_is_due(subscription, now=at):
        raise ValueError("nenhum lembrete de dunning esta vencido neste momento.")
    return replace(
        subscription,
        dunning_reminders_sent=subscription.dunning_reminders_sent + 1,
        last_dunning_at=at,
    )



def request_plan_change(
    subscription: Subscription,
    target_plan: PlanDefinition,
) -> Subscription:
    """Registra troca permitida pelo catalogo sem liberar entitlement antes do pagamento."""

    if subscription.status is not SubscriptionStatus.ACTIVE:
        raise ValueError("troca de plano exige assinatura ACTIVE.")
    if subscription.pending_plan is not None:
        raise ValueError("ja existe uma troca de plano pendente.")
    if target_plan.entitlements is None:
        raise ValueError("plano alvo sem entitlements configurados nao pode ser ativado.")

    rule = next(
        (rule for rule in subscription.plan.plan_changes if rule.target_plan_id == target_plan.plan_id),
        None,
    )
    if rule is None:
        raise ValueError("transicao de plano nao permitida pelo catalogo comercial.")
    if rule.activation is not PlanChangeActivation.SETTLED_PAYMENT:
        raise ValueError("modo de ativacao da troca de plano nao suportado.")
    if rule.billing_mode is not PlanChangeBillingMode.TARGET_PLAN_FULL_CYCLE:
        raise ValueError("modo de cobranca da troca de plano nao configurado/suportado.")

    return replace(
        subscription,
        pending_plan=target_plan,
        pending_plan_change_kind=rule.kind,
        pending_plan_change_billing_mode=rule.billing_mode,
    )


def cancel_subscription(
    subscription: Subscription, *, now: datetime | None = None
) -> Subscription:
    """Cancela somente quando o catalogo do plano explicita cancelamento imediato."""

    if subscription.status is SubscriptionStatus.CANCELED:
        return subscription
    if subscription.plan.cancellation_mode is not CancellationMode.IMMEDIATE:
        raise ValueError("politica de cancelamento nao configurada como IMMEDIATE.")
    at = now or datetime.now(timezone.utc)
    return replace(
        subscription,
        status=SubscriptionStatus.CANCELED,
        pending_plan=None,
        pending_plan_change_kind=None,
        pending_plan_change_billing_mode=None,
        canceled_at=at,
        reactivation_requested_at=None,
        past_due_at=None,
        grace_period_ends_at=None,
        dunning_reminders_sent=0,
        last_dunning_at=None,
    )


def request_reactivation(
    subscription: Subscription, *, now: datetime | None = None
) -> Subscription:
    """Reabre uma assinatura cancelada como PENDING_PAYMENT sem restaurar entitlement."""

    if subscription.status is not SubscriptionStatus.CANCELED:
        raise ValueError("reativacao exige assinatura CANCELED.")
    if subscription.plan.reactivation_mode is not ReactivationMode.PAYMENT_REQUIRED:
        raise ValueError("politica de reativacao nao configurada como PAYMENT_REQUIRED.")
    if (
        subscription.plan.reactivation_billing_mode
        is not ReactivationBillingMode.CURRENT_PLAN_FULL_CYCLE
    ):
        raise ValueError("modo de cobranca da reativacao nao configurado/suportado.")
    at = now or datetime.now(timezone.utc)
    return replace(
        subscription,
        status=SubscriptionStatus.PENDING_PAYMENT,
        reactivation_requested_at=at,
        activated_at=None,
    )

def activate_from_settled_payment(
    subscription: Subscription,
    *,
    settled_at: datetime | None = None,
    billed_plan_id: str | None = None,
    billed_purpose: ChargePurpose = ChargePurpose.REGULAR,
) -> Subscription:
    """Ativa entitlement pago somente a partir de fato de pagamento confirmado.

    ACTIVE e idempotente. CANCELED permanece fail-closed porque reativacao apos cancelamento
    tem regra comercial propria e ainda pertence a outro item de F5.
    """

    if subscription.status is SubscriptionStatus.CANCELED:
        raise ValueError("assinatura cancelada exige fluxo explicito de reativacao.")

    if subscription.status is SubscriptionStatus.PAST_DUE:
        if billed_purpose is not ChargePurpose.REGULAR:
            raise ValueError(
                "recuperacao de PAST_DUE exige pagamento da cobranca REGULAR vencida."
            )
        if billed_plan_id is None:
            raise ValueError("cobranca sem plan_id nao pode recuperar PAST_DUE.")
        if billed_plan_id != subscription.plan.plan_id:
            raise ValueError("pagamento nao corresponde ao plano inadimplente.")
        if subscription.plan.entitlements is None:
            raise ValueError(
                "plano sem entitlements configurados nao pode recuperar acesso comercial."
            )
        activated_at = settled_at or datetime.now(timezone.utc)
        if activated_at.tzinfo is None:
            raise ValueError("settled_at deve ser timezone-aware.")
        return replace(
            subscription,
            status=SubscriptionStatus.ACTIVE,
            activated_at=activated_at,
            past_due_at=None,
            grace_period_ends_at=None,
            dunning_reminders_sent=0,
            last_dunning_at=None,
        )

    target_plan = subscription.pending_plan or subscription.plan
    if target_plan.entitlements is None:
        raise ValueError(
            "plano sem entitlements configurados nao pode ativar acesso comercial."
        )
    if subscription.pending_plan is not None:
        if billed_plan_id is None:
            raise ValueError("cobranca legada sem plan_id nao pode concluir troca de plano.")
        if billed_purpose is not ChargePurpose.PLAN_CHANGE:
            raise ValueError("pagamento nao pertence ao fluxo de troca de plano.")
    elif subscription.reactivation_requested_at is not None:
        if billed_purpose is not ChargePurpose.REACTIVATION:
            raise ValueError("pagamento nao pertence ao fluxo de reativacao.")
    if billed_plan_id is not None and billed_plan_id != target_plan.plan_id:
        raise ValueError("pagamento liquidado nao corresponde ao plano aguardado pela assinatura.")
    if subscription.status is SubscriptionStatus.ACTIVE and subscription.pending_plan is None:
        return subscription

    activated_at = settled_at or datetime.now(timezone.utc)
    return replace(
        subscription,
        plan=target_plan,
        status=SubscriptionStatus.ACTIVE,
        activated_at=activated_at,
        pending_plan=None,
        pending_plan_change_kind=None,
        pending_plan_change_billing_mode=None,
        reactivation_requested_at=None,
    )


def entitlement_access_is_active(
    subscription: Subscription, *, now: datetime | None = None
) -> bool:
    """Regra minima e segura do WP-F05-02.

    ACTIVE tem acesso. TRIAL tem acesso somente dentro da janela configurada.
    PENDING_PAYMENT/EXPIRED/CANCELED nao ativam entitlement.
    PAST_DUE so mantem acesso quando a politica explicita permite e ainda esta no grace.
    """

    current = refresh_trial_status(subscription, now=now)
    if current.status is SubscriptionStatus.ACTIVE:
        return True
    if current.status is SubscriptionStatus.TRIAL:
        return True
    if current.status is SubscriptionStatus.PAST_DUE:
        return past_due_is_in_grace(current, now=now)
    return False


def compute_cycle_charge(
    subscription: Subscription,
    *,
    competence: str,
    extra_credits_used: Decimal | int | str = 0,
    billing_plan: PlanDefinition | None = None,
    purpose: ChargePurpose = ChargePurpose.REGULAR,
) -> SubscriptionCharge:
    """Calcula a cobranca de UMA competencia. Puro — nao muda estado, nao chama gateway."""

    if subscription.status is SubscriptionStatus.CANCELED:
        raise ValueError("assinatura cancelada nao gera cobranca.")
    if subscription.status is SubscriptionStatus.PAST_DUE:
        raise ValueError(
            "assinatura PAST_DUE nao gera nova cobranca REGULAR ate reconciliar a pendencia."
        )
    if not competence.strip():
        raise ValueError("competence e obrigatoria.")

    extra = _d(extra_credits_used)
    if extra < 0:
        raise ValueError("extra_credits_used nao pode ser negativo.")

    plan = billing_plan or subscription.plan
    billable_extra = max(extra - plan.included_credits, Decimal("0"))

    line_items = [
        ChargeLineItem(f"Assinatura {plan.name} ({competence})", plan.monthly_price)
    ]
    if billable_extra > 0:
        line_items.append(
            ChargeLineItem(
                f"Creditos extras ({billable_extra} un.)",
                (billable_extra * plan.extra_credit_unit_price).quantize(Decimal("0.01")),
            )
        )

    billing_id = f"sub:{subscription.tenant_id}:{competence}"
    if purpose is ChargePurpose.PLAN_CHANGE:
        billing_id += f":plan:{plan.plan_id}"
    elif purpose is ChargePurpose.REACTIVATION:
        billing_id += ":reactivation"
    return SubscriptionCharge(
        billing_id=billing_id,
        tenant_id=subscription.tenant_id,
        customer_ref=subscription.customer_ref,
        customer_document=subscription.customer_document,
        competence=competence,
        currency=plan.currency,
        line_items=tuple(line_items),
        plan_id=plan.plan_id,
        purpose=purpose,
    )


__all__ = [
    "CancellationMode",
    "ChargeLineItem",
    "DunningPolicy",
    "ChargePurpose",
    "ChargeStatus",
    "PlanChangeActivation",
    "PlanChangeBillingMode",
    "PlanChangeKind",
    "PlanChangeRule",
    "PlanDefinition",
    "PlanEntitlements",
    "PastDueAccessMode",
    "Subscription",
    "SubscriptionCharge",
    "SubscriptionStatus",
    "ReactivationBillingMode",
    "ReactivationMode",
    "activate_from_settled_payment",
    "cancel_subscription",
    "compute_cycle_charge",
    "dunning_reminder_is_due",
    "entitlement_access_is_active",
    "mark_past_due",
    "next_dunning_reminder_at",
    "past_due_is_in_grace",
    "record_dunning_reminder",
    "refresh_trial_status",
    "request_plan_change",
    "request_reactivation",
    "start_trial",
]
