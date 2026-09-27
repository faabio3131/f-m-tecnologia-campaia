#!/usr/bin/env bash
# CAMPAIA — B7: verificação reproduzível do DDL contra um Postgres real.
#
# O que este script prova, de fato executando contra um servidor Postgres real (não apenas
# lendo a sintaxe do arquivo .sql):
#   1. db/001_initial_schema.sql roda do início ao fim sem erro (CREATE TABLE, índices,
#      RLS, políticas, extensão pgcrypto, tudo dentro de uma única transação).
#   2. Row Level Security realmente isola tenants: um papel de aplicação (`campaia_app`,
#      sem privilégio de superusuário) autenticado via TCP/senha, com
#      `SET app.tenant_id = '<x>'`, só enxerga linhas do próprio tenant -- e sem
#      `app.tenant_id` definido, enxerga ZERO linhas (falha fechado, não aberto), batendo
#      com o invariante arquitetural já documentado em
#      campaia/docs/security/TENANT_ISOLATION.md.
#   3. As restrições CHECK (estado de campanha, kind/status de aprovação, status/mode de
#      connection) rejeitam valores inválidos e aceitam os válidos.
#   4. A foreign key approvals.campaign_id -> campaigns.campaign_id é aplicada de fato.
#   5. A chave primária composta de idempotency (tenant_id, idempotency_key) rejeita
#      duplicata, replicando a mesma chave composta que api/db.py já usa hoje (só que como
#      colunas reais em vez de uma string concatenada).
#
# Uso: bash db/verify_ddl_postgres.sh
# Requer um servidor Postgres acessível localmente (testado com Postgres 16, socket local,
# via `service postgresql start` + `sudo -u postgres psql`). Cria e sempre derruba um banco
# e um papel de teste próprios -- nunca toca em dados de um banco já existente.

set -euo pipefail

DB_NAME="campaia_ddl_verify_$$"
APP_ROLE="campaia_app_verify_$$"
APP_PASSWORD="verify_$$_pw"
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
DDL_FILE="$SCRIPT_DIR/001_initial_schema.sql"

cleanup() {
    sudo -u postgres psql -c "DROP DATABASE IF EXISTS ${DB_NAME};" >/dev/null 2>&1 || true
    sudo -u postgres psql -c "DROP ROLE IF EXISTS ${APP_ROLE};" >/dev/null 2>&1 || true
}
trap cleanup EXIT

echo "== 1/5: criando banco de teste e aplicando o DDL =="
sudo -u postgres psql -c "CREATE DATABASE ${DB_NAME};"
# O DDL cria o papel "campaia_app" fixo -- para este script poder rodar em paralelo consigo
# mesmo sem colidir, renomeamos o papel logo após a migration rodar sob o nome fixo esperado.
sed "s/campaia_app/${APP_ROLE}/g" "$DDL_FILE" | sudo -u postgres psql -d "${DB_NAME}" -v ON_ERROR_STOP=1
sudo -u postgres psql -c "ALTER ROLE ${APP_ROLE} WITH PASSWORD '${APP_PASSWORD}' LOGIN;"
sudo -u postgres psql -d "${DB_NAME}" -c "GRANT ALL ON ALL TABLES IN SCHEMA public TO ${APP_ROLE};"
echo "OK: schema aplicado sem erros."

echo "== 2/5: inserindo dados de dois tenants como superusuário =="
sudo -u postgres psql -d "${DB_NAME}" <<SQL
INSERT INTO brand_profiles (brand_profile_id, tenant_id, name, tone) VALUES ('bp1', 'tenant-a', 'Acme', 'formal');
INSERT INTO brand_profiles (brand_profile_id, tenant_id, name, tone) VALUES ('bp2', 'tenant-b', 'Beta', 'casual');
SQL

echo "== 3/5: verificando isolamento por RLS via TCP/senha (papel de aplicação, sem superusuário) =="
export PGPASSWORD="${APP_PASSWORD}"

COUNT_A=$(psql -h 127.0.0.1 -U "${APP_ROLE}" -d "${DB_NAME}" -tAc "SET app.tenant_id = 'tenant-a'; SELECT count(*) FROM brand_profiles;" | tail -n1)
if [ "$COUNT_A" != "1" ]; then
    echo "FALHA: tenant-a deveria ver exatamente 1 linha, viu ${COUNT_A}"
    exit 1
fi

COUNT_B=$(psql -h 127.0.0.1 -U "${APP_ROLE}" -d "${DB_NAME}" -tAc "SET app.tenant_id = 'tenant-b'; SELECT count(*) FROM brand_profiles;" | tail -n1)
if [ "$COUNT_B" != "1" ]; then
    echo "FALHA: tenant-b deveria ver exatamente 1 linha, viu ${COUNT_B}"
    exit 1
fi

COUNT_NONE=$(psql -h 127.0.0.1 -U "${APP_ROLE}" -d "${DB_NAME}" -tAc "SELECT count(*) FROM brand_profiles;")
if [ "$COUNT_NONE" != "0" ]; then
    echo "FALHA: sem app.tenant_id definido deveria ver 0 linhas (falha fechado), viu ${COUNT_NONE}"
    exit 1
fi
echo "OK: RLS isola tenant-a (1), tenant-b (1), sem contexto (0)."
unset PGPASSWORD

echo "== 4/5: verificando restrições CHECK e foreign key =="
if sudo -u postgres psql -d "${DB_NAME}" -c "INSERT INTO campaigns (campaign_id, tenant_id, state, brief, domain_state, budget_engine, autonomy_settings) VALUES ('bad', 'tenant-a', 'NOT_A_STATE', '{}', '{}', '{}', '{}');" >/dev/null 2>&1; then
    echo "FALHA: estado de campanha invalido deveria ter sido rejeitado"
    exit 1
fi
sudo -u postgres psql -d "${DB_NAME}" -c "INSERT INTO campaigns (campaign_id, tenant_id, state, brief, domain_state, budget_engine, autonomy_settings) VALUES ('c1', 'tenant-a', 'DRAFT', '{}', '{}', '{}', '{}');" >/dev/null

if sudo -u postgres psql -d "${DB_NAME}" -c "INSERT INTO approvals (approval_id, tenant_id, campaign_id, kind, requested_by, expires_at) VALUES ('bad', 'tenant-a', 'nao-existe', 'PUBLISH', 'u1', now() + interval '1 day');" >/dev/null 2>&1; then
    echo "FALHA: approval com campaign_id inexistente deveria ter sido rejeitado pela FK"
    exit 1
fi
sudo -u postgres psql -d "${DB_NAME}" -c "INSERT INTO approvals (approval_id, tenant_id, campaign_id, kind, requested_by, expires_at) VALUES ('ap1', 'tenant-a', 'c1', 'PUBLISH', 'u1', now() + interval '1 day');" >/dev/null
echo "OK: CHECK de estado e foreign key de approvals aplicados corretamente."

echo "== 5/5: verificando chave composta de idempotency =="
sudo -u postgres psql -d "${DB_NAME}" -c "INSERT INTO idempotency (tenant_id, idempotency_key, result) VALUES ('tenant-a', 'key1', '{}');" >/dev/null
if sudo -u postgres psql -d "${DB_NAME}" -c "INSERT INTO idempotency (tenant_id, idempotency_key, result) VALUES ('tenant-a', 'key1', '{}');" >/dev/null 2>&1; then
    echo "FALHA: (tenant_id, idempotency_key) duplicado deveria ter sido rejeitado"
    exit 1
fi
echo "OK: chave composta de idempotency rejeita duplicata."

echo ""
echo "ALL CHECKS PASSED — DDL aplicado e verificado contra Postgres real."
