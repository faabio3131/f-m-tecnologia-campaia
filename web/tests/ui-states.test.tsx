import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";
import { AppShell } from "@/components/AppShell";
import { EmptyState } from "@/components/EmptyState";
import { ErrorState } from "@/components/ErrorState";
import { Spinner } from "@/components/Spinner";

describe("Etapa 2 — estados de UI", () => {
  it("Spinner (loading) expoe role=status e um rotulo acessivel", () => {
    render(<Spinner label="Verificando sessão" />);
    expect(screen.getByRole("status")).toBeInTheDocument();
    expect(screen.getByText("Verificando sessão")).toBeInTheDocument();
  });

  it("EmptyState renderiza titulo e descricao", () => {
    render(<EmptyState title="Nada aqui" description="Ainda não implementado." />);
    expect(screen.getByText("Nada aqui")).toBeInTheDocument();
    expect(screen.getByText("Ainda não implementado.")).toBeInTheDocument();
  });

  it("ErrorState (permission denied / erro) expoe role=alert, nunca detalhe interno", () => {
    render(
      <ErrorState
        title="Acesso negado"
        description="Você não tem permissão para ver este conteúdo."
      />,
    );
    const alert = screen.getByRole("alert");
    expect(alert.textContent).not.toMatch(/traceback|stack|secret|token/i);
    expect(screen.getByText("Acesso negado")).toBeInTheDocument();
  });

  it("AppShell (authenticated) mostra usuario/tenant/unidade e aciona logout", async () => {
    const onLogout = vi.fn();
    const user = userEvent.setup();

    render(
      <AppShell
        user={{
          userId: "user-owner-1",
          tenantId: "demo-tenant",
          businessUnitId: "bu-1",
          roles: ["OWNER"],
        }}
        onLogout={onLogout}
      >
        <p>conteúdo protegido</p>
      </AppShell>,
    );

    expect(screen.getByText("demo-tenant")).toBeInTheDocument();
    expect(screen.getByText("bu-1")).toBeInTheDocument();
    expect(screen.getByText("user-owner-1")).toBeInTheDocument();
    expect(screen.getByText("conteúdo protegido")).toBeInTheDocument();

    await user.click(screen.getByTestId("logout-button"));
    expect(onLogout).toHaveBeenCalledTimes(1);
  });
});
