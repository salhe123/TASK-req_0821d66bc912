import { describe, it, expect, beforeEach, afterEach, vi } from "vitest";
import { mount, flushPromises } from "@vue/test-utils";
import { createPinia, setActivePinia } from "pinia";
import PlansView from "@/views/PlansView.vue";

function jsonResponse(body: unknown, status = 200): Response {
  return new Response(JSON.stringify(body), {
    status,
    headers: { "content-type": "application/json" },
  });
}

function mockFetch(calls: Array<() => Response>) {
  const m = vi.fn();
  for (const fn of calls) m.mockResolvedValueOnce(fn());
  vi.stubGlobal("fetch", m);
  return m;
}

const samplePlans = {
  items: [
    {
      id: "p1",
      name: "Primary BOM",
      description: "",
      head_version_id: "v2",
      head_version_no: 2,
      versions: [
        {
          id: "v1",
          plan_id: "p1",
          version_no: 1,
          parent_version_id: null,
          note: "initial",
          created_at: "2026-04-01T00:00:00+00:00",
        },
        {
          id: "v2",
          plan_id: "p1",
          version_no: 2,
          parent_version_id: "v1",
          note: "rev",
          created_at: "2026-04-10T00:00:00+00:00",
        },
      ],
    },
  ],
};

const sampleDiff = {
  base_version_id: "v1",
  target_version_id: "v2",
  entries: [
    {
      line_identity_key: "K1",
      changes: ["QUANTITY_CHANGED"],
      base: { line_identity_key: "K1", part_number: "P-A", description: "", quantity: "1", unit: "ea", notes: "", tags: [] },
      target: { line_identity_key: "K1", part_number: "P-A", description: "", quantity: "2", unit: "ea", notes: "", tags: [] },
    },
  ],
};

describe("PlansView", () => {
  beforeEach(() => setActivePinia(createPinia()));
  afterEach(() => vi.unstubAllGlobals());

  it("renders plans list and selects head version on click", async () => {
    mockFetch([
      () => jsonResponse(samplePlans),
      () => jsonResponse(sampleDiff), // diff load triggered by selection
    ]);
    const w = mount(PlansView);
    await flushPromises();
    await flushPromises();
    expect(w.find('[data-testid="plan-p1"]').exists()).toBe(true);

    await w.find('[data-testid="plan-p1"]').trigger("click");
    await flushPromises();
    await flushPromises();
    expect(w.find('[data-testid="version-v1"]').exists()).toBe(true);
    expect(w.find('[data-testid="version-v2"]').exists()).toBe(true);
    expect(w.find('[data-testid="bom-diff"]').exists()).toBe(true);
    expect(w.find('[data-testid="diff-row-K1"]').exists()).toBe(true);
  });

  it("opens the rollback dialog and fires a POST on confirm", async () => {
    const m = mockFetch([
      () => jsonResponse(samplePlans),
      () => jsonResponse(sampleDiff),
      () => jsonResponse({ id: "v3", version_no: 3, parent_version_id: "v2", note: "rollback" }, 201),
      () => jsonResponse(samplePlans),
      () => jsonResponse(sampleDiff),
    ]);
    const w = mount(PlansView);
    await flushPromises();
    await w.find('[data-testid="plan-p1"]').trigger("click");
    await flushPromises();
    await flushPromises();

    await w.find('[data-testid="open-rollback"]').trigger("click");
    expect(w.find('[data-testid="rollback-modal"]').exists()).toBe(true);

    await w.find('[data-testid="rollback-note"]').setValue("revert after drill");
    await w.find('[data-testid="rollback-confirm"]').trigger("click");
    await flushPromises();
    await flushPromises();

    const call = m.mock.calls.find(([url]) => String(url).endsWith("/rollback"));
    expect(call).toBeTruthy();
    const body = JSON.parse(call![1].body);
    expect(body.note).toBe("revert after drill");
  });

  it("renders empty state when there are no plans", async () => {
    mockFetch([() => jsonResponse({ items: [] })]);
    const w = mount(PlansView);
    await flushPromises();
    await flushPromises();
    expect(w.text()).toContain("No plans yet");
  });
});
