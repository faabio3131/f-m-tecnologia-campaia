from __future__ import annotations

import uuid
from datetime import datetime, timezone

from starlette.requests import Request
from starlette.responses import JSONResponse, Response

from campaia_core.connectors import ConnectionMode, SecretRef
from campaia_core.permissions import Permission, Resource, authorize

from .deps import (
    build_domain_principal,
    get_state,
    note_step_up_header,
    require_auth,
    require_idempotency_key,
    require_step_up,
)
from .errors import ApiError
from .helpers import json_response, list_response, parse_body, serialize_connection
from .models import (
    CapabilityResponse,
    ConnectionResponse,
    OAuthCallbackRequest,
    OAuthStartRequest,
    OAuthStartResponse,
)


def _authorize(request: Request, permission: Permission):
    fixture = require_auth(request)
    state = get_state(request)
    note_step_up_header(request, fixture)
    principal = build_domain_principal(state, fixture)
    resource = Resource(tenant_id=fixture.tenant_id, business_unit_id=fixture.business_unit_id)
    decision = authorize(principal, permission, resource, now=datetime.now(timezone.utc))
    if not decision.allowed:
        raise ApiError(decision.code.value, decision.reason)
    return fixture, state


async def list_connections(request: Request) -> JSONResponse:
    fixture, state = _authorize(request, Permission.CAMPAIGN_VIEW)
    conns = state.connections.list_for_tenant(fixture.tenant_id)
    return list_response([serialize_connection(c) for c in conns])


async def oauth_start(request: Request) -> JSONResponse:
    """Synthesizes a fake authorization URL under a clearly-fake domain.

    This NEVER calls a real OAuth provider. No real network call is made here at all --
    the "authorization_url" is a placeholder string pointing at a domain that does not
    resolve to anything, purely to exercise the shape of the flow in this sandbox.
    """
    fixture, state = _authorize(request, Permission.CONNECTION_MANAGE)
    require_step_up(request, fixture)
    body = await parse_body(request, OAuthStartRequest)

    oauth_state = uuid.uuid4().hex
    fake_url = (
        f"https://auth.simulated-ads-provider.invalid/oauth/authorize"
        f"?provider={body.provider}&state={oauth_state}&client_id=sandbox-fixture"
    )
    state.start_oauth_state(
        oauth_state,
        tenant_id=fixture.tenant_id,
        provider=body.provider,
        now=datetime.now(timezone.utc),
    )
    state.audit.append(
        tenant_id=fixture.tenant_id,
        actor=fixture.user_id,
        action="OAUTH_START",
        target=body.provider,
        # ACHADO 22 (Fase 3, item 4 -- mineracao tecnica da PR#6, 26/09/2026): o valor
        # anti-replay `state` nao tem lugar numa trilha de auditoria legivel por humanos,
        # mesmo ja sendo devolvido ao chamador nesta mesma resposta -- uma trilha de
        # auditoria e para revisar acoes, nao para guardar tokens de seguranca. Nao e uma
        # exposicao real hoje (valor single-use, escopado por tenant, TTL curto, este
        # fluxo nunca contata um provider real), mas e higiene de auditoria correta
        # independente disso -- mesma correcao ja feita pela PR#6 (commit 9a0e6b3).
        details={"note": "simulated, no real provider contacted"},
    )
    return json_response(OAuthStartResponse(authorization_url=fake_url, state=oauth_state))


async def oauth_callback(request: Request) -> JSONResponse:
    """Resgata o `state` de POST /connections/oauth/start e cria a Connection real.

    WP-04 (26/09/2026): antes desta rota, `oauth_start` devolvia uma URL e nada mais --
    nenhuma Connection era jamais criada (achado confirmado por leitura do codigo real
    antes de codificar, nao presumido). Ainda simulado (nenhum provider real e
    contatado); `external_account_id`/`display_name` vem do cliente (conta que o
    usuario "selecionaria" no provedor) -- nunca inventados aqui.
    """
    fixture, state = _authorize(request, Permission.CONNECTION_MANAGE)
    require_step_up(request, fixture)
    idem_key = require_idempotency_key(request)
    body = await parse_body(request, OAuthCallbackRequest)

    # Decisao do Diretor (27/09/2026, SaaS multi-tenant): a redecao automatica para a
    # tela real de consentimento do provedor ainda depende de um dominio de callback
    # publicado (pendencia registrada, nao simulada como pronta). Enquanto isso, se
    # `body.credential` vier preenchido (token real obtido por outro meio -- hoje, so o
    # fluxo manual de sandbox), este endpoint guarda-o de verdade no cofre
    # (criptografado, por tenant) em vez de descartar; sem `credential`, comportamento
    # idêntico ao anterior. Este guard fica ANTES do check de replay (achado 24) porque
    # e' uma validacao de entrada pura -- nao depende de nenhum estado de uso-unico.
    if body.credential is not None and state.vault_cipher is None:
        raise ApiError(
            "VALIDATION_FAILED",
            "CAMPAIA_VAULT_KEY nao configurada -- o cofre de credenciais nao esta "
            "disponivel para guardar um token real neste ambiente.",
        )

    # ACHADO 24 (Fase 3, item 6 -- mineracao de testes da PR#6, 26/09/2026, REPRODUZIDO por
    # execucao real nesta sessao): mesma classe de bug de ordenacao ja corrigida no achado
    # 19 (patch_budget/publish_campaign/put_autonomy) -- aqui o recurso de uso-unico e o
    # OAuth `state` (consumido por `redeem_oauth_state`) em vez do status de uma
    # ApprovalRequest, mas o efeito e identico: antes desta correcao, um replay legitimo da
    # MESMA Idempotency-Key (ex.: cliente retransmitindo apos timeout de rede) chegava a
    # `redeem_oauth_state` de novo, encontrava o state ja consumido pela primeira chamada, e
    # falhava com 403 PERMISSION_DENIED em vez de devolver o 201 original -- confirmado por
    # execucao real: FIRST 201, SECOND (mesma Idempotency-Key, mesmo state) 403 antes desta
    # correcao. O gate de replay precisa vir ANTES do resgate do state, que so pode
    # acontecer uma vez.
    existing = state.idempotency.get(fixture.tenant_id, f"http:oauth_callback:{idem_key}")
    if existing is not None:
        return JSONResponse(existing.result, status_code=201)

    pending = state.redeem_oauth_state(
        body.state, tenant_id=fixture.tenant_id, now=datetime.now(timezone.utc)
    )
    if pending is None:
        raise ApiError(
            "PERMISSION_DENIED",
            "state de OAuth invalido, expirado, ja usado, ou de outro tenant.",
        )

    def _do_create():
        secret_ref = None
        mode = ConnectionMode.SIMULATOR
        if body.credential is not None:
            secret_ref = state.vault.store(
                fixture.tenant_id,
                provider=pending.provider,
                external_account_id=body.external_account_id,
                payload=body.credential,
                cipher=state.vault_cipher,
            ).handle
            mode = ConnectionMode.TEST
        conn = state.connections.create(
            fixture.tenant_id,
            provider=pending.provider,
            external_account_id=body.external_account_id,
            display_name=body.display_name,
            secret_ref=secret_ref,
            mode=mode,
        )
        state.audit.append(
            tenant_id=fixture.tenant_id,
            actor=fixture.user_id,
            action="CONNECTION_CREATE",
            target=conn.connection_id,
            details={"provider": pending.provider},
        )
        return serialize_connection(conn).model_dump(mode="json")

    result, _replay = state.idempotency.execute(
        fixture.tenant_id, f"http:oauth_callback:{idem_key}", _do_create
    )
    return JSONResponse(result, status_code=201)


async def revoke_connection(request: Request) -> Response:
    fixture, state = _authorize(request, Permission.CONNECTION_MANAGE)
    require_step_up(request, fixture)
    idem_key = require_idempotency_key(request)
    connection_id = request.path_params["connectionId"]

    conn = state.connections.get(fixture.tenant_id, connection_id)
    if conn is None:
        raise ApiError("NOT_FOUND", "Connection not found.")

    def _do_revoke():
        if conn.secret_ref is not None:
            state.vault.revoke(fixture.tenant_id, SecretRef(handle=conn.secret_ref))
        state.connections.revoke(fixture.tenant_id, connection_id)
        state.audit.append(
            tenant_id=fixture.tenant_id,
            actor=fixture.user_id,
            action="CONNECTION_REVOKE",
            target=connection_id,
        )
        return None

    state.idempotency.execute(fixture.tenant_id, idem_key, _do_revoke)
    # Contract: 204 with no body (achado 4) -- previously returned 200 with the revoked
    # connection's JSON representation.
    return Response(status_code=204)


#: ACHADO 20 (Fase 3, reproduzido por execucao real nesta sessao): `CapabilityRegistry`
#: e indexado por `(provider, capability_key, country, api_version)`, mas `provider` ali
#: sempre significou "qual conector/execucao realmente atende esta capacidade" -- e
#: `routes_campaigns.py::validate_campaign` ja consulta esse registro com o literal
#: `"SIMULATOR"`, independente da conta OAuth escolhida, porque HOJE toda publicacao real
#: passa pelo `ProviderSimulator` (nao existe nenhum adaptador REST real para
#: GOOGLE_ADS/META/WHATSAPP ainda -- ver docs/nova-fm ou o Capability Matrix histórico da
#: PR#6, docs/08_CAPABILITY_MATRIX.md, que classifica esses tres providers como "NAO
#: VERIFICADO"). Este handler, porem, consultava o registro com `conn.provider` (o RÓTULO
#: da conta OAuth conectada -- GOOGLE_ADS/META/WHATSAPP, contrato `Provider`), que NUNCA
#: bate com a unica chave seedada ("SIMULATOR") -- um descasamento de indexacao genuino,
#: nao uma decisao deliberada de honestidade: `GET /connections/{id}/capabilities`
#: reportava `supported: false` para QUALQUER conta real, inclusive quando a MESMA
#: campanha, no MESMO tenant, publica de fato com sucesso via `POST
#: /campaigns/{id}/publish` (que usa exatamente essa mesma capacidade "SIMULATOR" para
#: decidir se a policy libera a publicacao). As duas rotas respondiam perguntas
#: inconsistentes sobre o mesmo fato real.
#:
#: `ConnectionMode` (`campaia_core/connectors.py`) e o eixo certo para essa pergunta --
#: seu proprio docstring diz "Estado real da conta. A interface mostra isto ao usuario,
#: sem maquiagem." Toda `Connection` hoje tem `mode == ConnectionMode.SIMULATOR` (nao
#: existe fluxo real de OAuth nem adaptador de producao ainda), entao mapeamos o MODO da
#: conexao (nao o rotulo do provider OAuth) para a chave real do registro de
#: capacidades -- a mesma que `validate_campaign` ja usa e confia. Um modo sem
#: adaptador real seedado (`TEST`/`PRODUCTION`, nenhum hoje) cai honestamente em
#: `supported: false`/`verified_at: None`, nunca em `True` fabricado.
#:
#: IMPORTANTE (instrucao explicita da missao): isto NAO afirma que GOOGLE_ADS/META/
#: WHATSAPP estao homologados externamente -- `supported: true` aqui significa apenas
#: "a plataforma sabe executar esta acao para esta conexao hoje" (via simulador), o que
#: e verdade e ja e a base real usada por `validate_campaign`. O campo `notes` do
#: registro ja disclosa isso ("Simulated capability, verified in-process at startup.");
#: `evidence_url` continua sempre `None` (achado 7, nenhuma evidencia real existe).
_CONNECTION_MODE_TO_CAPABILITY_PROVIDER: dict[str, str] = {
    "SIMULATOR": "SIMULATOR",
    # TEST/PRODUCTION: nenhum adaptador real de execucao existe ainda para nenhum modo
    # alem do simulador -- deliberadamente NAO mapeado, para que is_supported() caia no
    # `False` honesto abaixo em vez de qualquer suposicao.
}


async def connection_capabilities(request: Request) -> JSONResponse:
    fixture, state = _authorize(request, Permission.CAMPAIGN_VIEW)
    connection_id = request.path_params["connectionId"]
    conn = state.connections.get(fixture.tenant_id, connection_id)
    if conn is None:
        raise ApiError("NOT_FOUND", "Connection not found.")

    now = datetime.now(timezone.utc)
    channels = ("GOOGLE_ADS", "META_ADS")
    capability_provider = _CONNECTION_MODE_TO_CAPABILITY_PROVIDER.get(str(conn.mode))
    results = []
    for channel in channels:
        key = f"PUBLISH:{channel}"
        if capability_provider is not None:
            supported = state.capabilities.is_supported(
                capability_provider, key, country="BR", api_version=conn.api_version, now=now
            )
            cap = state.capabilities._items.get((capability_provider, key, "BR", conn.api_version))
        else:
            # Modo de conexao sem nenhum conector de execucao real seedado (achado 20) --
            # nunca fabricar supported=true nem um verified_at que nunca aconteceu.
            supported = False
            cap = None
        results.append(
            CapabilityResponse(
                # `provider` no corpo da resposta continua sendo o rotulo da conta OAuth
                # (GOOGLE_ADS/META/WHATSAPP) -- e a identidade da CONTA que o cliente quer
                # ver, distinta da chave interna usada para decidir `supported` acima.
                provider=conn.provider,
                capability_key=key,
                country="BR",
                api_version=conn.api_version,
                supported=supported,
                # ACHADO 20: nunca fabricar "verificado agora" quando nenhuma verificacao
                # de fato ocorreu -- None quando nao ha registro real de capacidade.
                verified_at=cap.verified_at if cap else None,
                requires_approval=cap.requires_approval if cap else False,
                # No evidence-URL source exists yet in campaia_core.infra.Capability
                # (achado 7) -- always None until that tracking exists.
                evidence_url=None,
                notes=cap.notes if cap else None,
            )
        )
    return list_response(results)
