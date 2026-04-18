import { describe, it, expect, beforeEach, afterEach, vi } from "vitest";
import { mount, flushPromises } from "@vue/test-utils";
import { createPinia, setActivePinia } from "pinia";
import ShareLinkModal from "@/components/ShareLinkModal.vue";

function jsonResponse(body: unknown, status = 201): Response {
  return new Response(JSON.stringify(body), {
    status,
    headers: { "content-type": "application/json" },
  });
}

describe("ShareLinkModal", () => {
  beforeEach(() => {
    setActivePinia(createPinia());
    vi.stubGlobal("fetch", vi.fn());
  });
  afterEach(() => vi.unstubAllGlobals());

  it("issues a share link and reveals the one-time token", async () => {
    const m = globalThis.fetch as unknown as ReturnType<typeof vi.fn>;
    m.mockResolvedValueOnce(
      jsonResponse({
        id: "s1",
        plan_version_id: "v1",
        role: "Plan Owner",
        token: "shh-secret-token",
        expires_at: "2026-04-19T00:00:00+00:00",
        revoked: false,
      }),
    );
    const w = mount(ShareLinkModal, { props: { planId: "p1", versionId: "v1" } });
    await w.find('[data-testid="share-issue"]').trigger("click");
    await flushPromises();
    await flushPromises();
    expect(w.find('[data-testid="share-token"]').text()).toBe("shh-secret-token");

    const call = m.mock.calls[0];
    expect(call[0]).toBe("/api/plans/p1/versions/v1/share");
    expect(JSON.parse(call[1].body)).toMatchObject({ role: "Plan Owner", expires_in_days: 7 });
  });

  it("shows the server error when the API rejects the request", async () => {
    const m = globalThis.fetch as unknown as ReturnType<typeof vi.fn>;
    m.mockResolvedValueOnce(
      new Response(
        JSON.stringify({
          error: "forbidden",
          message: "permission denied",
          details: {},
        }),
        { status: 403, headers: { "content-type": "application/json" } },
      ),
    );
    const w = mount(ShareLinkModal, { props: { planId: "p1", versionId: "v1" } });
    await w.find('[data-testid="share-issue"]').trigger("click");
    await flushPromises();
    await flushPromises();
    expect(w.text()).toContain("permission denied");
    expect(w.find('[data-testid="share-token"]').exists()).toBe(false);
  });

  it("emits close when the close button is clicked", async () => {
    const w = mount(ShareLinkModal, { props: { planId: "p1", versionId: "v1" } });
    await w
      .findAll("button")
      .find((b) => b.text() === "Close")!
      .trigger("click");
    expect(w.emitted("close")).toBeTruthy();
  });
});
