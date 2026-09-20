#!/usr/bin/env node
// CLI para a verificacao das fronteiras de seguranca do frontend (WP-01 + WP-02).
// Nao certifica seguranca formal do produto -- apenas confirma que as proibicoes
// explicitas (sem token/segredo no bundle, sem credencial em storage do navegador, e sem
// chamada de rede ao BFF fora dos dois pontos legitimos do WP-02 -- leitura de sessao
// server-side e logout client-side protegido por CSRF) nao foram violadas no
// codigo-fonte. Logica compartilhada com tests/boundaries.test.ts em
// scripts/lib/security-boundaries.mjs.
import { checkSecurityBoundaries } from "./lib/security-boundaries.mjs";

const SRC_ROOT = new URL("../src", import.meta.url).pathname;

const { violations, scannedFileCount } = checkSecurityBoundaries(SRC_ROOT);

if (violations.length > 0) {
  console.error("FRONTEIRAS DE SEGURANCA VIOLADAS:\n");
  for (const v of violations) {
    console.error(`  ${v.file}:${v.line} [${v.rule}] ${v.message}`);
  }
  console.error(`\n${violations.length} violacao(oes) encontrada(s).`);
  process.exit(1);
}

console.log(
  `OK: nenhuma violacao das fronteiras de seguranca em ${scannedFileCount} arquivo(s) verificado(s) sob web/src.`,
);
console.log(
  "Nao certifica seguranca formal do produto -- apenas as fronteiras especificas do WP-01/WP-02 (sem token/segredo, sem credencial em storage do navegador, chamadas de rede ao BFF restritas a session.ts/LogoutButton.tsx).",
);
