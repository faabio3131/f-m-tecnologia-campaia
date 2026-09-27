#!/usr/bin/env node
// CLI que confirma que src/contracts/bff-openapi.generated.ts esta em
// sincronia com contracts/bff-openapi.yaml. Logica compartilhada com
// tests/boundaries.test.ts em scripts/lib/contract-drift.mjs.
import path from "node:path";
import { fileURLToPath } from "node:url";
import { checkContractDrift } from "./lib/contract-drift.mjs";

const WEB_ROOT = path.resolve(fileURLToPath(import.meta.url), "../..");
const COMMITTED_PATH = path.join(
  WEB_ROOT,
  "src",
  "contracts",
  "bff-openapi.generated.ts",
);
const CONTRACT_PATH = path.join(
  WEB_ROOT,
  "..",
  "contracts",
  "bff-openapi.yaml",
);

const { inSync } = await checkContractDrift(CONTRACT_PATH, COMMITTED_PATH);

if (!inSync) {
  console.error(
    "DRIFT DETECTADO: src/contracts/bff-openapi.generated.ts esta desatualizado em relacao a contracts/bff-openapi.yaml.",
  );
  console.error(
    "Execute `npm run contracts:generate` em web/ e faca commit do resultado.",
  );
  process.exit(1);
}

console.log(
  "OK: src/contracts/bff-openapi.generated.ts esta em sincronia com contracts/bff-openapi.yaml.",
);
