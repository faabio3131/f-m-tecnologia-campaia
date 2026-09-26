import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { setCsrfToken } from "@/lib/api/client";
import { KillSwitchPanel } from "@/components/KillSwitchPanel";

function jsonResponse(status: number, body: unknown) {
  return Promise.resolve(
    new Response(JSON.stringify(body), {
      status,
      headers: { "content-type": "application/json" },
    }),
  );
}

describe("KillSwitchPanel", () => {
  beforeEach(() => {
    vi.restoreAllMocks();
    setCsrfToken("csrf-test-token");
  });

  afterEach(() => {
    vi.restoreAllMocks();
    setCsrfToken(null);
  });

  it("aciona POST /kill-switch com escopo CAMPAIGN e mostra as campanhas afetadas", async () => {
    let sentScope: string | null = null;
    let sentTargetId: string | null = null;
    let sentReason: string | null = null;

    vi.spyOn(globalThis, "fetch").mockImplementation((input, init) => {
      const url = String(input);
      if (url.endsWith("/kill-switch") && init?.method === "POST") {
        const body = JSON.parse(String(init.body)) as {
          scope: string;
          target_id: string | null;
          reason: string;
        };
        sentScope = body.scope;
        sentTargetId = body.target_id;
        sentReason = body.reason;
        return jsonResponse(202, { scope: "CAMPAIGN", affected_campaign_ids: ["camp-1"] });
      }
      throw new Error(`unexpected fetch: ${url}`);
    });

    const user = userEvent.setup();
    render(
      <KillSwitchPanel
        scope="CAMPAIGN"
        targetId="camp-1"
        title="Parada de emergência (esta campanha)"
        description="desc"
        confirmLabel="Parar esta campanha agora"
      />,
    );

    await user.click(screen.getByRole("button", { name: /parar esta campanha agora/i }));

    await waitFor(() => expect(sentScope).toBe("CAMPAIGN"));
    expect(sentTargetId).toBe("camp-1");
    expect(sentReason).toBeTruthy();
    await waitFor(() =>
      expect(screen.getByTestId("kill-switch-result-campaign")).toHaveTextContent(
        "1 campanha(s) afetada(s)",
      ),
    );
  });

  it("mostra uma mensagem honesta quando a campanha não está num estado pausável (409 INVALID_STATE)", async () => {
    vi.spyOn(globalThis, "fetch").mockImplementation((input, init) => {
      const url = String(input);
      if (url.endsWith("/kill-switch") && init?.method === "POST") {
        return jsonResponse(409, { code: "INVALID_STATE", message: "not pausable" });
      }
      throw new Error(`unexpected fetch: ${url}`);
    });

    const user = userEvent.setup();
    render(
      <KillSwitchPanel
        scope="CAMPAIGN"
        targetId="camp-2"
        title="Parada de emergência (esta campanha)"
        description="desc"
        confirmLabel="Parar esta campanha agora"
      />,
    );

    await user.click(screen.getByRole("button", { name: /parar esta campanha agora/i }));

    await waitFor(() =>
      expect(screen.getByText(/não está em um estado que possa ser pausado agora/i)).toBeInTheDocument(),
    );
  });

  it("aciona POST /kill-switch com escopo TENANT sem target_id", async () => {
    let sentScope: string | null = null;
    let sentTargetId: string | null = "unset";

    vi.spyOn(globalThis, "fetch").mockImplementation((input, init) => {
      const url = String(input);
      if (url.endsWith("/kill-switch") && init?.method === "POST") {
        const body = JSON.parse(String(init.body)) as { scope: string; target_id: string | null };
        sentScope = body.scope;
        sentTargetId = body.target_id;
        return jsonResponse(202, { scope: "TENANT", affected_campaign_ids: [] });
      }
      throw new Error(`unexpected fetch: ${url}`);
    });

    const user = userEvent.setup();
    render(
      <KillSwitchPanel
        scope="TENANT"
        title="Parada de emergência (todas as campanhas deste tenant)"
        description="desc"
        confirmLabel="Parar todas as campanhas deste tenant agora"
      />,
    );

    await user.click(
      screen.getByRole("button", { name: /parar todas as campanhas deste tenant agora/i }),
    );

    await waitFor(() => expect(sentScope).toBe("TENANT"));
    expect(sentTargetId).toBeNull();
    await waitFor(() =>
      expect(screen.getByTestId("kill-switch-result-tenant")).toHaveTextContent(
        "0 campanha(s) afetada(s)",
      ),
    );
  });
});
