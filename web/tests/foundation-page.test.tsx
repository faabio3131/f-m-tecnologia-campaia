import { beforeEach, describe, expect, it, vi } from "vitest";

const { redirectMock } = vi.hoisted(() => ({
  redirectMock: vi.fn(),
}));

vi.mock("next/navigation", () => ({
  redirect: redirectMock,
}));

import RootPage from "@/app/page";

describe("RootPage", () => {
  beforeEach(() => {
    redirectMock.mockReset();
  });

  it("redirects the product root to the real login entrypoint", () => {
    RootPage();
    expect(redirectMock).toHaveBeenCalledTimes(1);
    expect(redirectMock).toHaveBeenCalledWith("/login");
  });
});
