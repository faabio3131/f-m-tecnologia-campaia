export function safeBillingInvoiceUrl(url: string | null | undefined, provider: string | null | undefined,
  mode: string | null | undefined): string | null {
  if (!url || /\s/.test(url) || provider !== "ASAAS") return null;
  const host = mode === "SANDBOX" ? "sandbox.asaas.com" : mode === "PRODUCTION" ? "www.asaas.com" : null;
  return host && new RegExp(`^https://${host.replaceAll(".", "\\.")}/i/[A-Za-z0-9_-]+$`).test(url) ? url : null;
}
