import { describe, it, expect, beforeEach, afterEach, vi } from "vitest";
import { mount, flushPromises } from "@vue/test-utils";
import { createPinia, setActivePinia } from "pinia";
import CyclesView from "@/views/CyclesView.vue";

function jsonResponse(body: unknown, status = 200): Response {
  return new Response(JSON.stringify(body), {
    status,
    headers: { "content-type": "application/json" },
  });
}

describe("CyclesView", () => {
  beforeEach(() => {
    setActivePinia(createPinia());
    vi.stubGlobal("fetch", vi.fn());
  });
  afterEach(() => vi.unstubAllGlobals());

  it("renders an empty state when there are no active assignments", async () => {
    const m = globalThis.fetch as unknown as ReturnType<typeof vi.fn>;
    // Default for any unlisted call — an empty payload shaped to satisfy the view.
    m.mockResolvedValue(jsonResponse({ items: [] }));
    m.mockResolvedValueOnce(jsonResponse({ items: [] })) // /api/cycles
      .mockResolvedValueOnce(jsonResponse([])); // /api/assignments/mine/active
    const w = mount(CyclesView);
    await flushPromises();
    await flushPromises();
    expect(w.text()).toContain("No active assignments");
  });

  it("renders the timeline badge for each assignment", async () => {
    const m = globalThis.fetch as unknown as ReturnType<typeof vi.fn>;
    m.mockResolvedValue(jsonResponse({ items: [] }));
    m.mockResolvedValueOnce(jsonResponse({ items: [] }))
      .mockResolvedValueOnce(
        jsonResponse([
          {
            id: "a1",
            cycle_id: "c1",
            evaluator_user_id: "u1",
            reviewer_user_id: null,
            state: "IN_PROGRESS",
            submitted_at: null,
            late_flag: false,
            returned_reason: null,
            archived_at: null,
          },
          {
            id: "a2",
            cycle_id: "c1",
            evaluator_user_id: "u1",
            reviewer_user_id: null,
            state: "RETURNED_FOR_REVISION",
            submitted_at: "2026-04-15T12:00:00+00:00",
            late_flag: false,
            returned_reason: "please reconsider q2",
            archived_at: null,
          },
        ]),
      );
    const w = mount(CyclesView);
    await flushPromises();
    await flushPromises();
    expect(w.find('[data-testid="timeline-IN_PROGRESS"]').exists()).toBe(true);
    expect(w.find('[data-testid="timeline-RETURNED_FOR_REVISION"]').exists()).toBe(true);
    expect(w.text()).toContain("please reconsider q2");
  });

});
