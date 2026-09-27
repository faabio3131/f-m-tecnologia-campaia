/**
 * Cliente HTTP central para o BFF do CampaIA (Etapa 2, secao 17).
 *
 * Responsabilidades: base path same-origin, JSON, `credentials: "include"`,
 * CSRF (double-submit, em memoria), parsing do erro canonico, Idempotency-Key,
 * 401/403, timeout/abort. Nenhum componente deve chamar `fetch()` diretamente.
 *
 * O frontend NUNCA e autoridade de seguranca (Etapa 2, secao 6) -- este cliente
 * so fala com o BFF real; toda decisao de autenticacao/autorizacao/tenant/RBAC/ABAC
 * continua no backend.
 */
import type { ApiErrorBody } from "../../contracts/types";

const BASE_PATH = "/api/campaia";
const DEFAULT_TIMEOUT_MS = 15_000;
const CSRF_HEADER_NAME = "x-csrf-token";
const MUTATING_METHODS = new Set(["POST", "PUT", "PATCH", "DELETE"]);

// CSRF token em memoria apenas -- NUNCA localStorage/sessionStorage (Etapa 2,
// secoes 13 e 16). Definido pelo AuthProvider apos bootstrap/login, limpo no logout.
let csrfToken: string | null = null;

export function setCsrfToken(token: string | null): void {
  csrfToken = token;
}

export function getCsrfToken(): string | null {
  return csrfToken;
}

/** Callback global chamado sempre que qualquer chamada da API receber 401 --
 * o AuthProvider se inscreve uma vez para limpar o AuthContext e redirecionar.
 * Mantido separado do 403 de proposito: 401 e 403 nunca sao tratados como
 * sinonimos (Etapa 2, secao 18). */
type UnauthenticatedListener = () => void;
let onUnauthenticated: UnauthenticatedListener | null = null;

export function setUnauthenticatedListener(listener: UnauthenticatedListener | null): void {
  onUnauthenticated = listener;
}

export class ApiClientError extends Error {
  readonly status: number;
  readonly body: ApiErrorBody | null;

  constructor(status: number, body: ApiErrorBody | null) {
    super(body?.message ?? `Erro HTTP ${status}`);
    this.name = "ApiClientError";
    this.status = status;
    this.body = body;
  }

  get code(): string | undefined {
    return this.body?.code;
  }
}

/** CSRF indisponivel para uma mutacao -- a operacao NUNCA e enviada silenciosamente
 * (Etapa 2, secao 16). Falha local, antes de qualquer chamada de rede. */
export class CsrfUnavailableError extends Error {
  constructor() {
    super(
      "Nao e possivel executar esta operacao agora: token CSRF indisponivel. " +
        "Recarregue a sessao antes de tentar novamente.",
    );
    this.name = "CsrfUnavailableError";
  }
}

export class ApiTimeoutError extends Error {
  constructor() {
    super("A requisicao excedeu o tempo limite.");
    this.name = "ApiTimeoutError";
  }
}

export class ApiNetworkError extends Error {
  constructor(cause: unknown) {
    super("Falha de rede ao comunicar com o servidor.");
    this.name = "ApiNetworkError";
    this.cause = cause;
  }
}

export interface RequestOptions {
  /** Corpo JSON da requisicao. */
  json?: unknown;
  /** Idempotency-Key estavel para a MESMA acao logica -- nunca gerada aqui;
   * quem chama decide o valor e reusa nas tentativas/retries da mesma acao
   * (Etapa 2, secao 25). */
  idempotencyKey?: string;
  /** Cabecalhos adicionais especificos da chamada. */
  headers?: Record<string, string>;
  timeoutMs?: number;
}

async function parseBody(response: Response): Promise<ApiErrorBody | null> {
  if (response.status === 204) return null;
  const text = await response.text();
  if (!text) return null;
  try {
    return JSON.parse(text) as ApiErrorBody;
  } catch {
    return null;
  }
}

async function request<T>(
  method: string,
  path: string,
  options: RequestOptions = {},
): Promise<T> {
  const isMutating = MUTATING_METHODS.has(method);

  if (isMutating) {
    const token = getCsrfToken();
    if (!token) {
      // Fail-closed local: nunca envia a mutacao sem CSRF (Etapa 2, secao 16).
      throw new CsrfUnavailableError();
    }
  }

  const headers = new Headers(options.headers);
  if (options.json !== undefined) {
    headers.set("content-type", "application/json");
  }
  if (isMutating) {
    headers.set(CSRF_HEADER_NAME, getCsrfToken() as string);
    if (options.idempotencyKey) {
      headers.set("idempotency-key", options.idempotencyKey);
    }
  }

  const controller = new AbortController();
  const timeout = setTimeout(
    () => controller.abort(),
    options.timeoutMs ?? DEFAULT_TIMEOUT_MS,
  );

  let response: Response;
  try {
    response = await fetch(`${BASE_PATH}${path}`, {
      method,
      headers,
      credentials: "include",
      body: options.json !== undefined ? JSON.stringify(options.json) : undefined,
      signal: controller.signal,
    });
  } catch (cause) {
    if (controller.signal.aborted) {
      throw new ApiTimeoutError();
    }
    throw new ApiNetworkError(cause);
  } finally {
    clearTimeout(timeout);
  }

  if (response.status === 401) {
    onUnauthenticated?.();
  }

  const body = await parseBody(response);
  if (!response.ok) {
    throw new ApiClientError(response.status, body);
  }
  return body as T;
}

export const api = {
  get: <T>(path: string, options?: Omit<RequestOptions, "json" | "idempotencyKey">) =>
    request<T>("GET", path, options),
  post: <T>(path: string, json?: unknown, options?: RequestOptions) =>
    request<T>("POST", path, { ...options, json }),
  put: <T>(path: string, json?: unknown, options?: RequestOptions) =>
    request<T>("PUT", path, { ...options, json }),
  patch: <T>(path: string, json?: unknown, options?: RequestOptions) =>
    request<T>("PATCH", path, { ...options, json }),
  delete: <T>(path: string, options?: RequestOptions) => request<T>("DELETE", path, options),
};
