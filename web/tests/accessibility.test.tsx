import { render } from "@testing-library/react";
import { axe } from "jest-axe";
import { describe, expect, it, vi } from "vitest";

vi.mock("next/navigation", () => ({
  useRouter: () => ({ replace: vi.fn() }),
  useSearchParams: () => new URLSearchParams(),
}));

vi.mock("@/providers/AuthProvider", () => ({
  useAuth: () => ({
    status: "unauthenticated",
    login: vi.fn(),
    onboardTenant: vi.fn(),
  }),
}));

vi.mock("@/lib/auth/test-identity-client", () => ({
  TEST_IDENTITY_OPTIONS: [
    { id: "owner", label: "Entrar como proprietário de teste" },
  ],
  isTestIdentityModeEnabled: () => true,
}));

import LoginPage from "@/app/(app)/login/page";

describe("LoginPage accessibility baseline", () => {
  it("has no detectable automated accessibility violations", async () => {
    const { container } = render(<LoginPage />);
    const results = await axe(container);
    expect(results).toHaveNoViolations();
  });
});
