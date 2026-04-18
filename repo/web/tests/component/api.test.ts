import { describe, it, expect, beforeEach, vi, afterEach } from "vitest";
import { apiGet, apiPost } from "@/lib/api";

describe("api client", () => {
  beforeEach(() => {
    vi.stubGlobal("fetch", vi.fn());
  });
  afterEach(() => {
    vi.unstubAllGlobals();
  });

  it("returns ok result with parsed body on success", async () => {
    (globalThis.fetch as unknown as ReturnType<typeof vi.fn>).mockResolvedValueOnce(
      new Response(JSON.stringify({ status: "ok" }), {
        status: 200,
        headers: { "content-type": "application/json" },
      }),
    );

    const result = await apiGet<{ status: string }>("/api/health");
    expect(result.ok).toBe(true);
    if (result.ok) {
      expect(result.status).toBe(200);
      expect(result.data).toEqual({ status: "ok" });
    }
  });

  it("returns error envelope on non-2xx response", async () => {
    (globalThis.fetch as unknown as ReturnType<typeof vi.fn>).mockResolvedValueOnce(
      new Response(
        JSON.stringify({ error: "not_found", message: "missing", details: { id: "x" } }),
        { status: 404, headers: { "content-type": "application/json" } },
      ),
    );

    const result = await apiGet("/api/missing");
    expect(result.ok).toBe(false);
    if (!result.ok) {
      expect(result.status).toBe(404);
      expect(result.error).toBe("not_found");
      expect(result.message).toBe("missing");
      expect(result.details).toEqual({ id: "x" });
    }
  });

  it("serializes body on POST", async () => {
    const fetchMock = globalThis.fetch as unknown as ReturnType<typeof vi.fn>;
    fetchMock.mockResolvedValueOnce(new Response("{}", { status: 200 }));

    await apiPost("/api/things", { a: 1 });
    const call = fetchMock.mock.calls[0];
    expect(call[0]).toBe("/api/things");
    expect(call[1].method).toBe("POST");
    expect(call[1].body).toBe(JSON.stringify({ a: 1 }));
    expect(call[1].headers["Content-Type"]).toBe("application/json");
  });

  it("maps network errors to a network_error envelope", async () => {
    (globalThis.fetch as unknown as ReturnType<typeof vi.fn>).mockRejectedValueOnce(
      new TypeError("connection refused"),
    );

    const result = await apiGet("/api/health");
    expect(result.ok).toBe(false);
    if (!result.ok) {
      expect(result.status).toBe(0);
      expect(result.error).toBe("network_error");
    }
  });
});
