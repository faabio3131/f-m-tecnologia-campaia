import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";
import { Badge } from "@/components/Badge";
import { Button } from "@/components/Button";
import { Card } from "@/components/Card";
import { EmptyState } from "@/components/EmptyState";
import { ErrorState } from "@/components/ErrorState";
import { LoadingState } from "@/components/LoadingState";
import { StatusPanel } from "@/components/StatusPanel";

describe("Button", () => {
  it("renders children and responds to click", async () => {
    const onClick = vi.fn();
    render(<Button onClick={onClick}>Continuar</Button>);
    const button = screen.getByRole("button", { name: "Continuar" });
    await userEvent.click(button);
    expect(onClick).toHaveBeenCalledOnce();
  });

  it("is reachable and operable by keyboard", async () => {
    const onClick = vi.fn();
    render(<Button onClick={onClick}>Continuar</Button>);
    await userEvent.tab();
    expect(screen.getByRole("button")).toHaveFocus();
    await userEvent.keyboard("{Enter}");
    expect(onClick).toHaveBeenCalled();
  });
});

describe("Badge", () => {
  it("renders its label text", () => {
    render(<Badge tone="warning">Aviso</Badge>);
    expect(screen.getByText("Aviso")).toBeInTheDocument();
  });
});

describe("Card", () => {
  it("renders children content", () => {
    render(
      <Card>
        <p>Conteudo do card</p>
      </Card>,
    );
    expect(screen.getByText("Conteudo do card")).toBeInTheDocument();
  });
});

describe("StatusPanel", () => {
  it("renders a heading and each label/value row", () => {
    render(
      <StatusPanel
        title="Estado"
        items={[{ label: "Framework", value: "Next.js" }]}
      />,
    );
    expect(
      screen.getByRole("heading", { name: "Estado" }),
    ).toBeInTheDocument();
    expect(screen.getByText("Framework")).toBeInTheDocument();
    expect(screen.getByText("Next.js")).toBeInTheDocument();
  });
});

describe("LoadingState", () => {
  it("announces itself via role=status with a default label", () => {
    render(<LoadingState />);
    expect(screen.getByRole("status")).toHaveTextContent("Carregando…");
  });

  it("accepts a custom label", () => {
    render(<LoadingState label="Carregando sessão…" />);
    expect(screen.getByRole("status")).toHaveTextContent("Carregando sessão…");
  });
});

describe("ErrorState", () => {
  it("announces itself via role=alert with title and optional description", () => {
    render(<ErrorState title="Falhou" description="Detalhe do erro." />);
    const alert = screen.getByRole("alert");
    expect(alert).toHaveTextContent("Falhou");
    expect(alert).toHaveTextContent("Detalhe do erro.");
  });

  it("renders without a description", () => {
    render(<ErrorState title="Falhou" />);
    expect(screen.getByRole("alert")).toHaveTextContent("Falhou");
  });
});

describe("EmptyState", () => {
  it("renders a title and optional description, no alert role", () => {
    render(<EmptyState title="Nada aqui" description="Ainda sem conteúdo." />);
    expect(screen.getByText("Nada aqui")).toBeInTheDocument();
    expect(screen.getByText("Ainda sem conteúdo.")).toBeInTheDocument();
    expect(screen.queryByRole("alert")).not.toBeInTheDocument();
  });
});
