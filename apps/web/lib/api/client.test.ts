import { describe, expect, it, vi } from "vitest";

import { API_BASE_URL, ApiError, apiRequest } from "./client";

function jsonResponse(status: number, body: unknown, headers: Record<string, string> = {}) {
  return new Response(JSON.stringify(body), {
    status,
    headers: { "content-type": "application/json", ...headers },
  });
}

describe("apiRequest", () => {
  it("returns the parsed body on success", async () => {
    const fetcher = vi.fn().mockResolvedValue(jsonResponse(200, { ok: true }));
    await expect(apiRequest("/x", {}, fetcher)).resolves.toEqual({ ok: true });
    expect(fetcher).toHaveBeenCalledWith(`${API_BASE_URL}/x`, expect.any(Object));
  });

  it("maps API error bodies to ApiError with code, details and Retry-After", async () => {
    const fetcher = vi.fn().mockResolvedValue(
      jsonResponse(
        503,
        { error: { code: "overloaded", message: "Busy.", details: { a: 1 } } },
        { "retry-after": "5" },
      ),
    );
    const error = await apiRequest("/x", {}, fetcher).catch((e: unknown) => e);
    expect(error).toBeInstanceOf(ApiError);
    expect(error).toMatchObject({
      code: "overloaded",
      status: 503,
      message: "Busy.",
      details: { a: 1 },
      retryAfterSeconds: 5,
    });
  });

  it("handles non-JSON error responses", async () => {
    const fetcher = vi.fn().mockResolvedValue(new Response("Bad gateway", { status: 502 }));
    await expect(apiRequest("/x", {}, fetcher)).rejects.toMatchObject({
      code: "http_error",
      status: 502,
    });
  });

  it("reports transport failures as network_error", async () => {
    const fetcher = vi.fn().mockRejectedValue(new TypeError("Failed to fetch"));
    await expect(apiRequest("/x", {}, fetcher)).rejects.toMatchObject({
      code: "network_error",
      status: 0,
    });
  });

  it("rethrows aborts untouched", async () => {
    const abort = new DOMException("aborted", "AbortError");
    const fetcher = vi.fn().mockRejectedValue(abort);
    await expect(apiRequest("/x", {}, fetcher)).rejects.toBe(abort);
  });
});
