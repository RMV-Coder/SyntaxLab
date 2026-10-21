import type {
  Glossary,
  LanguageDetail,
  LanguageList,
  ParseRequest,
  ParseResponse,
} from "./types";

export const API_BASE_URL = (
  process.env.NEXT_PUBLIC_SYNTAXLAB_API_URL ?? "http://127.0.0.1:8710"
).replace(/\/+$/, "");

/** An error returned by the API (or a transport failure), with a stable machine code. */
export class ApiError extends Error {
  constructor(
    message: string,
    readonly code: string,
    readonly status: number,
    readonly details: Record<string, unknown> | null = null,
    readonly retryAfterSeconds: number | null = null,
  ) {
    super(message);
    this.name = "ApiError";
  }
}

type Fetcher = typeof fetch;

export async function apiRequest<T>(
  path: string,
  init: RequestInit = {},
  fetcher: Fetcher = fetch,
): Promise<T> {
  let response: Response;
  try {
    response = await fetcher(`${API_BASE_URL}${path}`, {
      ...init,
      headers: { "Content-Type": "application/json", ...init.headers },
    });
  } catch (cause) {
    if (cause instanceof DOMException && cause.name === "AbortError") throw cause;
    throw new ApiError(
      "Can't reach the analysis service. Check that the parser API is running.",
      "network_error",
      0,
    );
  }

  const body: unknown = await response.json().catch(() => null);
  if (!response.ok) {
    const error = (body as { error?: { code?: string; message?: string; details?: unknown } })
      ?.error;
    const retry = Number(response.headers.get("retry-after"));
    throw new ApiError(
      error?.message ?? `The analysis service returned HTTP ${response.status}.`,
      error?.code ?? "http_error",
      response.status,
      (error?.details as Record<string, unknown> | undefined) ?? null,
      Number.isFinite(retry) && retry > 0 ? retry : null,
    );
  }
  return body as T;
}

export const api = {
  languages: (signal?: AbortSignal) => apiRequest<LanguageList>("/api/v1/languages", { signal }),
  language: (code: string, signal?: AbortSignal) =>
    apiRequest<LanguageDetail>(`/api/v1/languages/${encodeURIComponent(code)}`, { signal }),
  parse: (request: ParseRequest, signal?: AbortSignal) =>
    apiRequest<ParseResponse>("/api/v1/parse", {
      method: "POST",
      body: JSON.stringify(request),
      signal,
    }),
  glossary: (schemeId: string, signal?: AbortSignal) =>
    apiRequest<Glossary>(`/api/v1/schemes/${encodeURIComponent(schemeId)}`, { signal }),
};
