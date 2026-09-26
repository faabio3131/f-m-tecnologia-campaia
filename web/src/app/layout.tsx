import type { Metadata } from "next";
import "../styles/tokens.css";
import "./globals.css";

export const metadata: Metadata = {
  title: "CampaIA — Fundação Web (WP-01)",
  description:
    "Fundação técnica do frontend Web do CampaIA. Não é um produto comercial concluído.",
};

export default function RootLayout({ children }: LayoutProps<"/">) {
  return (
    <html lang="pt-BR">
      <body>{children}</body>
    </html>
  );
}
