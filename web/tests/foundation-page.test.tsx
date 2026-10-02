import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import FoundationPage from "@/app/page";

describe("FoundationPage", () => {
  it("renders the CampaIA name and official slogan", () => {
    render(<FoundationPage />);
    expect(
      screen.getByRole("heading", { level: 1, name: "CampaIA" }),
    ).toBeInTheDocument();
    expect(
      screen.getByText("Campanhas inteligentes. Resultados reais."),
    ).toBeInTheDocument();
  });

  it("identifies itself explicitly as the WP-01 technical foundation", () => {
    render(<FoundationPage />);
    expect(
      screen.getByText("CampaIA Web Foundation — WP-01"),
    ).toBeInTheDocument();
  });

  it("shows a visible warning that no real session, tenant, or integration is active", () => {
    render(<FoundationPage />);
    expect(
      screen.getByText(
        "Nenhuma sessão, tenant ou integração real está ativa nesta tela.",
      ),
    ).toBeInTheDocument();
  });

  it("displays fixture-derived data explicitly labeled as a local fixture", () => {
    render(<FoundationPage />);
    expect(
      screen.getByText(/Fixture local \(schema Me, contrato bff-openapi\.yaml\)/),
    ).toBeInTheDocument();
    expect(screen.getByText("00000000-0000-0000-0000-000000000001")).toBeInTheDocument();
  });

  it("never renders a real session indicator (no logout, no user email)", () => {
    render(<FoundationPage />);
    expect(screen.queryByText(/logout|sair da conta/i)).not.toBeInTheDocument();
  });
});
