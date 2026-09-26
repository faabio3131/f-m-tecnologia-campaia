import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";
import { Badge } from "@/components/Badge";
import { Button } from "@/components/Button";
import { Card } from "@/components/Card";
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
