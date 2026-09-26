// Logica compartilhada das fronteiras de seguranca do WP-01.
// Usada pelo CLI (scripts/check-security-boundaries.mjs) e pelos testes
// (tests/boundaries.test.ts), para evitar spawn de subprocesso nos testes.
import { readFileSync, readdirSync, statSync } from "node:fs";
import { join, extname, sep } from "node:path";

const SCAN_EXTENSIONS = new Set([".ts", ".tsx", ".css"]);
const EXCLUDED_FILES = new Set(["bff-openapi.generated.ts"]);

/** @type {{name: string, pattern: RegExp, message: string, exemptPathSubstrings?: string[]}[]} */
export const FORBIDDEN_PATTERNS = [
  {
    name: "network-call",
    pattern: /\b(fetch|axios|XMLHttpRequest)\s*\(/,
    message:
      "chamada de rede detectada (fetch/axios/XMLHttpRequest) fora da camada de API " +
      "central da Etapa 2 -- so src/lib/api/ e src/providers/AuthProvider.tsx podem " +
      "chamar o BFF; a pagina de fundacao do WP-01 (app/page.tsx) continua com a " +
      "garantia original de zero chamada de rede.",
    // Etapa 2 (WP-02 Web): a camada real de API/sessao PRECISA chamar o BFF -- a
    // garantia de "zero rede" do WP-01 continua valendo para o resto de web/src
    // (em particular app/page.tsx, a pagina de fundacao com E2E proprio provando
    // isso), so essas duas localizacoes sao isentas desta regra especifica.
    exemptPathSubstrings: [
      `${sep}lib${sep}api${sep}`,
      `${sep}providers${sep}AuthProvider.tsx`,
    ],
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
  {
    name: "private-data-caching",
    // Etapa 2, secao 23: dado autenticado nunca pode ser cacheado globalmente
    // (static caching, ISR compartilhado, cache cross-user/cross-tenant).
    pattern: /export\s+const\s+revalidate|force-cache|unstable_cache/,
    message:
      "diretiva de cache estatico/ISR detectada em rota autenticada -- dado de " +
      "sessao/tenant nunca pode ser cacheado globalmente (Etapa 2, secao 23)",
    onlyPathSubstrings: [`${sep}app${sep}(app)${sep}(authenticated)${sep}`],
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
    const content = readFileSync(file, "utf8");
    const lines = content.split("\n");
    for (const {
      name,
      pattern,
      message,
      exemptPathSubstrings,
      onlyPathSubstrings,
    } of FORBIDDEN_PATTERNS) {
      const exempt = (exemptPathSubstrings ?? []).some((s) => file.includes(s));
      if (exempt) continue;
      if (onlyPathSubstrings && !onlyPathSubstrings.some((s) => file.includes(s))) {
        continue;
      }
      lines.forEach((line, index) => {
        if (pattern.test(line)) {
          violations.push({ file, rule: name, message, line: index + 1 });
        }
      });
    }
  }

  return { violations, scannedFileCount: files.length };
}
