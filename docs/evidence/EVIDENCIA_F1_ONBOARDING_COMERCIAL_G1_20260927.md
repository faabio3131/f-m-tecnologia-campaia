# EVIDÊNCIA — F1 ONBOARDING COMERCIAL / G1 — 27/09/2026

**WP:** WP-F01-01  
**Fase/Gate:** F1 / G1  
**Status oficial:** `PARTIAL`  
**Repositório:** `faabio3131/f-m-tecnologia-campaia`  
**Branch:** `reconciliation/campaia-final-takeover`  
**HEAD funcional auditado:** `9add6f540f2d81e82f4a508db11dffb6dc943232`\n**Base documental consolidada:** `711e164526e741b6ff512af932a1d107dd03ffc4`

## 1. CURRENT confirmado

A implementação F1 está no produto real da branch, não apenas em documentação:
- `backend/api/organization.py`: agregado tenant/unidade/membership/invitation com persistência via RecordTable quando configurada;
- `backend/api/routes_onboarding.py`: criação de tenant, convites, aceite, listagem, desativação e reativação;
- `web/src/app/(app)/login/page.tsx`: entrada explícita no onboarding quando identidade verificada ainda não possui vínculo;
- `web/src/app/(app)/(authenticated)/settings/users/page.tsx`: administração de usuários/convites;
- `web/src/app/(app)/accept-invite/page.tsx`: aceite de convite;
- contrato público OpenAPI sincronizado com os tipos gerados.

## 2. Comportamento comprovado

O CURRENT cobre:
1. criação explícita de tenant comercial por identidade verificada, sem autoprovisionamento implícito no login;
2. empresa com nome, documento normalizado, segmento, idioma, timezone e modo de entrada;
3. unidade padrão `Principal`;
4. primeiro membership com papel `OWNER`;
5. sessão server-side após onboarding;
6. unicidade de documento/CNPJ normalizado;
7. convite com token bruto exposto somente na criação e digest persistido;
8. aceite vinculado ao e-mail/identidade e ao tenant/unidade corretos;
9. Owner/Admin com regra adicional de que somente Owner pode criar/administrar Owner;
10. soft deactivation, revogação de sessão e reactivation preservando membership/histórico;
11. tenant switching para identidade multiempresa;
12. limite de usuários derivado de configuração de plano no servidor;
13. navegador não pode autoatribuir `plan_id`/entitlement pago.

## 3. Segurança e isolamento adicionados nesta retomada

Commit `9add6f540f2d81e82f4a508db11dffb6dc943232` adicionou provas negativas específicas de F1:
- Owner do tenant A não pode criar convite apontando para business unit do tenant B: `404 NOT_FOUND`;
- Owner do tenant A não pode desativar ou reativar membership do tenant B: `404 NOT_FOUND`;
- o membership do tenant B permanece `ACTIVE` após as tentativas.

Não foi necessário corrigir regra de negócio: o backend já falhava fechado; a lacuna era de evidência reproduzível.

## 4. CI real do HEAD funcional

### Backend — run #128
Resultado: `success`.
- 377 testes de domínio: OK;
- 241 testes de API: OK;
- `pip-audit`: OK;
- validação AsyncAPI: OK.

### Frontend — run #66
Resultado: `success`.
- lint: OK;
- typecheck strict: OK;
- contract drift: OK;
- security boundary: OK;
- 20 arquivos / 67 testes Vitest: OK;
- production build: OK;
- 4 smoke E2E: OK;
- 27 E2E cross-stack backend real + frontend real: OK.

O cenário `commercial-onboarding.spec.ts` passou e cria, pela UI/API real do produto, um tenant sem tenant/membership previamente seedado, convida um segundo usuário em outro browser, aceita o convite, desativa, comprova revogação de sessão, reativa e autentica novamente.

## 5. Limite da evidência — por que G1 continua aberto

O Cronograma Mestre exige como evidência mínima um tenant totalmente novo “criado a partir de zero, sem fixture e sem alteração de código”.

O E2E atual não usa mock de rede e exercita frontend/backend reais, porém ainda usa infraestrutura de identidade determinística de teste:
- `FreshIdentityVerifier` nos testes de API;
- `NEXT_PUBLIC_CAMPAIA_IDENTITY_MODE=test` e harness de identidade no E2E.

O adaptador de produção `FirebaseIdTokenVerifier` está implementado e falha fechado quando `FIREBASE_PROJECT_ID` não está configurado. Esta retomada não possui evidência de uma jornada comercial completa com Google Identity Platform real.

Também não existe ainda prova de checkout/trial real concedendo entitlement e disparando onboarding: `entry_mode=TRIAL|PURCHASE` existe, mas `plan_id` permanece intencionalmente server-authoritative e o vínculo billing→entitlement pertence a F5.

Portanto:
- F1/WP-F01-01 = `PARTIAL`;
- G1 = aberto;
- não declarar `DONE_VERIFIED`, homologado ou produção pronta.

## 6. Dependências e fora de escopo

- IdP real/provisionamento externo: `EXTERNAL_INFRASTRUCTURE/EXTERNAL_CREDENTIAL` até o ambiente ser confirmado e exercitado;
- compra/trial/billing/entitlement: F5;
- transferência segura de ownership e IAM administrativo completo: F2;
- atomicidade multi-processo/multi-réplica e runtime produtivo: F3;
- merge/deploy/produção: não autorizados e não executados.

## 7. Rollback

O hardening desta retomada é apenas cobertura de testes e documentação. Reverter o commit de testes `9add6f5` remove somente as novas provas cross-tenant; não altera o comportamento funcional existente.
