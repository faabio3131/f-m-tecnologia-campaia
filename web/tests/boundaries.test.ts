import { fileURLToPath } from "node:url";
import path from "node:path";
import { describe, expect, it } from "vitest";
import { checkSecurityBoundaries } from "../scripts/lib/security-boundaries.mjs";
import { checkContractDrift } from "../scripts/lib/contract-drift.mjs";

const WEB_ROOT = path.resolve(fileURLToPath(import.meta.url), "../..");

describe("WP-01 automated boundary checks", () => {
  it("has no security boundary violations (no tokens, secrets, storage or BFF calls in src/)", () => {
    const { violations } = checkSecurityBoundaries(
      path.join(WEB_ROOT, "src"),
    );
    expect(violations).toEqual([]);
  });

  it("has no drift between the generated contract types and contracts/bff-openapi.yaml", async () => {
    const { inSync } = await checkContractDrift(
      path.join(WEB_ROOT, "..", "contracts", "bff-openapi.yaml"),
      path.join(WEB_ROOT, "src", "contracts", "bff-openapi.generated.ts"),
    );
    expect(inSync).toBe(true);
  });
});
