// Logica compartilhada das fronteiras de seguranca do WP-01.
// Usada pelo CLI (scripts/check-security-boundaries.mjs) e pelos testes
// (tests/boundaries.test.ts), para evitar spawn de subprocesso nos testes.
import { readFileSync, readdirSync, statSync } from "node:fs";
import { join, extname } from "node:path";

const SCAN_EXTENSIONS = new Set([".ts", ".tsx", ".css"]);
const EXCLUDED_FILES = new Set(["bff-openapi.generated.ts"]);

// WP-01's rule was "no BFF calls anywhere in web/src" because no session existed to call
// with. WP-02 introduced two legitimate real calls to the BFF: a server-only session read
// (never reaches the client bundle, forwards the HttpOnly cookie the browser itself cannot
// read) and a client-side logout action explicitly protected by the double-submit CSRF
// token. WP-03 adds a third, same discipline: a client-side tenant-switch action, also
// CSRF-protected via the same non-HttpOnly campaia_csrf cookie, never a client-typed
// tenant id (see TenantSwitcher.tsx -- it only ever offers tenant ids the server itself
// returned). Every other file in web/src must remain at zero network calls; this allowlist
// is intentionally three files, not a blanket rule.
const NETWORK_CALL_ALLOWED_FILES = new Set([
  "session.ts",
  "LogoutButton.tsx",
  "TenantSwitcher.tsx",
]);

/** @type {{name: string, pattern: RegExp, message: string, exemptFiles?: Set<string>}[]} */
export const FORBIDDEN_PATTERNS = [
  {
    name: "network-call",
    pattern: /\b(fetch|axios|XMLHttpRequest)\s*\(/,
    message:
      "chamada de rede detectada (fetch/axios/XMLHttpRequest) fora da lista de excecoes do WP-02/WP-03 (session.ts, LogoutButton.tsx, TenantSwitcher.tsx)",
    exemptFiles: NETWORK_CALL_ALLOWED_FILES,
  },
  {
    name: "browser-storage",
    pattern: /\b(localStorage|sessionStorage)\s*\.\s*(setItem|getItem)/,
    message:
      "uso de localStorage/sessionStorage detectado -- proibido para credenciais no WP-01",
  },
  {
    name: "bearer-literal",
    pattern: /Bearer\s+[A-Za-z0-9\-_.]{10,}/,
    message: "valor literal de Bearer token detectado no codigo-fonte",
  },
  {
    name: "hardcoded-secret-assignment",
    pattern:
      /\b(token|secret|password|apiKey|api_key)\s*[:=]\s*["'][^"'{}]{8,}["']/i,
    message:
      "atribuicao de valor literal a uma variavel de nome sensivel (token/secret/password/apiKey)",
  },
  {
    name: "next-public-secret",
    pattern:
      /NEXT_PUBLIC_[A-Z0-9_]*(TOKEN|SECRET|KEY|PASSWORD|CREDENTIAL)[A-Z0-9_]*/,
    message:
      "variavel NEXT_PUBLIC_* com nome sensivel -- variaveis NEXT_PUBLIC_* sao expostas ao navegador",
  },
  {
    name: "aws-style-key",
    pattern: /AKIA[0-9A-Z]{16}/,
    message: "padrao de chave de acesso estilo AWS detectado",
  },
];

/** @param {string} dir */
function walk(dir) {
  /** @type {string[]} */
  const files = [];
  for (const entry of readdirSync(dir)) {
    const fullPath = join(dir, entry);
    const stat = statSync(fullPath);
    if (stat.isDirectory()) {
      files.push(...walk(fullPath));
    } else if (
      SCAN_EXTENSIONS.has(extname(entry)) &&
      !EXCLUDED_FILES.has(entry)
    ) {
      files.push(fullPath);
    }
  }
  return files;
}

/**
 * @param {string} srcRoot absolute path to web/src
 * @returns {{violations: {file: string, rule: string, message: string, line: number}[], scannedFileCount: number}}
 */
export function checkSecurityBoundaries(srcRoot) {
  const files = walk(srcRoot);
  /** @type {{file: string, rule: string, message: string, line: number}[]} */
  const violations = [];

  for (const file of files) {
    const baseName = file.split("/").pop();
    const content = readFileSync(file, "utf8");
    const lines = content.split("\n");
    for (const { name, pattern, message, exemptFiles } of FORBIDDEN_PATTERNS) {
      if (exemptFiles?.has(baseName)) continue;
      lines.forEach((line, index) => {
        if (pattern.test(line)) {
          violations.push({ file, rule: name, message, line: index + 1 });
        }
      });
    }
  }

  return { violations, scannedFileCount: files.length };
}
