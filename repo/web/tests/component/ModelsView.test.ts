import { describe, it, expect, beforeEach, afterEach, vi } from "vitest";
import { mount, flushPromises } from "@vue/test-utils";
import { createPinia, setActivePinia } from "pinia";
import ModelsView from "@/views/ModelsView.vue";
import { useSessionStore } from "@/stores/session";

function jsonResponse(body: unknown, status = 200): Response {
  return new Response(JSON.stringify(body), {
    status,
    headers: { "content-type": "application/json" },
  });
}

function fetchQueue(fns: Array<() => Response>) {
  const m = vi.fn();
  for (const fn of fns) m.mockResolvedValueOnce(fn());
  vi.stubGlobal("fetch", m);
  return m;
}

function adminSession() {
  const s = useSessionStore();
  s.user = {
    userId: "u1",
    username: "admin",
    displayName: "",
    roles: ["Administrator"],
    permissions: [{ resource: "*", action: "*" }],
    fieldViewAllowlist: ["*"],
  };
  return s;
}

function readOnlySession() {
  const s = useSessionStore();
  s.user = {
    userId: "u2",
    username: "obs",
    displayName: "",
    roles: ["Reviewer"],
    permissions: [],
    fieldViewAllowlist: [],
  };
  return s;
}

describe("ModelsView", () => {
  beforeEach(() => setActivePinia(createPinia()));
  afterEach(() => vi.unstubAllGlobals());

  it("renders empty states when no models or experiments", async () => {
    adminSession();
    fetchQueue([
      () => jsonResponse({ items: [] }),
      () => jsonResponse({ items: [] }),
    ]);
    const w = mount(ModelsView);
    await flushPromises();
    await flushPromises();
    expect(w.text()).toContain("No models registered.");
    expect(w.text()).toContain("No experiments configured.");
  });

  it("shows promote button only on DRAFT versions for admin role", async () => {
    adminSession();
    fetchQueue([
      () =>
        jsonResponse({
          items: [
            {
              id: "m1",
              name: "reco",
              description: "",
              live_schema_hash: "abc",
              versions: [
                {
                  id: "v1",
                  model_id: "m1",
                  version_no: 1,
                  status: "APPROVED",
                  feature_schema_hash: "a".repeat(64),
                  artifact_uri: "",
                  created_at: "2026-04-01T00:00:00+00:00",
                  approved_at: "2026-04-02T00:00:00+00:00",
                },
                {
                  id: "v2",
                  model_id: "m1",
                  version_no: 2,
                  status: "DRAFT",
                  feature_schema_hash: "b".repeat(64),
                  artifact_uri: "",
                  created_at: "2026-04-05T00:00:00+00:00",
                  approved_at: null,
                },
              ],
            },
          ],
        }),
      () => jsonResponse({ items: [] }),
    ]);
    const w = mount(ModelsView);
    await flushPromises();
    await flushPromises();
    expect(w.find('[data-testid="promote-v1"]').exists()).toBe(false);
    expect(w.find('[data-testid="promote-v2"]').exists()).toBe(true);
  });

  it("hides promote button for a user without model:promote permission", async () => {
    readOnlySession();
    fetchQueue([
      () =>
        jsonResponse({
          items: [
            {
              id: "m1",
              name: "reco",
              description: "",
              live_schema_hash: null,
              versions: [
                {
                  id: "v2",
                  model_id: "m1",
                  version_no: 1,
                  status: "DRAFT",
                  feature_schema_hash: "b".repeat(64),
                  artifact_uri: "",
                  created_at: "2026-04-05T00:00:00+00:00",
                  approved_at: null,
                },
              ],
            },
          ],
        }),
      () => jsonResponse({ items: [] }),
    ]);
    const w = mount(ModelsView);
    await flushPromises();
    await flushPromises();
    expect(w.find('[data-testid="promote-v2"]').exists()).toBe(false);
  });

  it("surfaces a schema mismatch error when promote returns 409", async () => {
    adminSession();
    fetchQueue([
      () =>
        jsonResponse({
          items: [
            {
              id: "m1",
              name: "reco",
              description: "",
              live_schema_hash: "abc",
              versions: [
                {
                  id: "v2",
                  model_id: "m1",
                  version_no: 2,
                  status: "DRAFT",
                  feature_schema_hash: "b".repeat(64),
                  artifact_uri: "",
                  created_at: "2026-04-05T00:00:00+00:00",
                  approved_at: null,
                },
              ],
            },
          ],
        }),
      () => jsonResponse({ items: [] }),
      () =>
        jsonResponse(
          {
            error: "feature_schema_mismatch",
            message: "version feature schema does not match inference service",
            details: { expected_hash: "a".repeat(64), got_hash: "b".repeat(64), missing_in_got: [], extra_in_got: ["c"] },
          },
          409,
        ),
    ]);
    const w = mount(ModelsView);
    await flushPromises();
    await flushPromises();
    await w.find('[data-testid="promote-v2"]').trigger("click");
    await flushPromises();
    await flushPromises();
    expect(w.find('[data-testid="promote-error"]').exists()).toBe(true);
    expect(w.find('[data-testid="promote-error"]').text()).toContain(
      "does not match inference service",
    );
  });
});
