import { describe, expect, it } from "vitest";
import { localMeFixture } from "@/fixtures/me.local";

describe("localMeFixture", () => {
  it("is shaped like the Me schema from contracts/bff-openapi.yaml", () => {
    expect(typeof localMeFixture.user_id).toBe("string");
    expect(typeof localMeFixture.tenant_id).toBe("string");
    expect(localMeFixture.business_unit_id).toBeNull();
    expect(Array.isArray(localMeFixture.roles)).toBe(true);
    expect(Array.isArray(localMeFixture.permissions)).toBe(true);
    expect(typeof localMeFixture.mfa_enabled).toBe("boolean");
  });

  it("uses only fictional UUID-shaped identifiers, never a real-looking secret", () => {
    const uuidPattern =
      /^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/i;
    expect(localMeFixture.user_id).toMatch(uuidPattern);
    expect(localMeFixture.tenant_id).toMatch(uuidPattern);
  });
});
