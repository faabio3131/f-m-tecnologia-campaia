// Logica compartilhada da verificacao de drift do contrato OpenAPI.
// Usada pelo CLI (scripts/check-contract-drift.mjs) e pelos testes
// (tests/boundaries.test.ts). Usa a API programatica de openapi-typescript
// (em vez de spawnar `npx`), para funcionar tambem dentro do processo do
// test runner.
import { readFileSync } from "node:fs";
import openapiTS, { astToString, COMMENT_HEADER } from "openapi-typescript";

/**
 * @param {string} contractPath absolute path to contracts/bff-openapi.yaml
 * @param {string} committedPath absolute path to the committed generated file
 * @returns {Promise<{inSync: boolean, committed: string, fresh: string}>}
 */
export async function checkContractDrift(contractPath, committedPath) {
  const ast = await openapiTS(new URL(`file://${contractPath}`));
  const fresh = COMMENT_HEADER + astToString(ast);
  const committed = readFileSync(committedPath, "utf8");
  return { inSync: committed === fresh, committed, fresh };
}
