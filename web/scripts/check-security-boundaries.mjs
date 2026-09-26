#!/usr/bin/env node
// CLI para a verificacao das fronteiras de seguranca do WP-01.
// Nao certifica seguranca formal do produto -- apenas confirma que as
// proibicoes explicitas do WP-01 (sem chamada real ao BFF, sem token ou
// segredo no bundle, sem credencial em storage do navegador) nao foram
// violadas no codigo-fonte do scaffold. Logica compartilhada com
// tests/boundaries.test.ts em scripts/lib/security-boundaries.mjs.
import { checkSecurityBoundaries } from "./lib/security-boundaries.mjs";

const SRC_ROOT = new URL("../src", import.meta.url).pathname;

const { violations, scannedFileCount } = checkSecurityBoundaries(SRC_ROOT);

if (violations.length > 0) {
  console.error("FRONTEIRAS DE SEGURANCA DO WP-01 VIOLADAS:\n");
  for (const v of violations) {
    console.error(`  ${v.file}:${v.line} [${v.rule}] ${v.message}`);
  }
  console.error(`\n${violations.length} violacao(oes) encontrada(s).`);
  process.exit(1);
}

console.log(
  `OK: nenhuma violacao das fronteiras de seguranca do WP-01 em ${scannedFileCount} arquivo(s) verificado(s) sob web/src.`,
);
console.log(
  "Nao certifica seguranca formal do produto -- apenas as fronteiras especificas do WP-01 (sem chamada real ao BFF, sem token/segredo, sem credencial em storage do navegador).",
);
