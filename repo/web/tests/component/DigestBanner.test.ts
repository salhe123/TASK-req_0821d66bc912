import { describe, it, expect, beforeEach, afterEach, vi } from "vitest";
import { mount, flushPromises } from "@vue/test-utils";
import { createPinia, setActivePinia } from "pinia";
import DigestBanner from "@/components/DigestBanner.vue";

describe("DigestBanner", () => {
  beforeEach(() => {
    setActivePinia(createPinia());
    vi.stubGlobal("fetch", vi.fn());
  });
  afterEach(() => {
    vi.unstubAllGlobals();
  });

  it("renders nothing when show=false", async () => {
    (globalThis.fetch as unknown as ReturnType<typeof vi.fn>).mockResolvedValueOnce(
      new Response(
        JSON.stringify({ show: false, as_of_local: "2026-04-18T08:00:00+00:00", items: [] }),
        { status: 200, headers: { "content-type": "application/json" } },
      ),
    );
    const w = mount(DigestBanner);
    await flushPromises();
    expect(w.find('[data-testid="digest-banner"]').exists()).toBe(false);
  });

  it("renders items when show=true", async () => {
    (globalThis.fetch as unknown as ReturnType<typeof vi.fn>).mockResolvedValueOnce(
      new Response(
        JSON.stringify({
          show: true,
          as_of_local: "2026-04-18T09:30:00+00:00",
          items: [
            {
              assignment_id: "a1",
              cycle_id: "c1",
              cycle_name: "Q2 2026",
              state: "IN_PROGRESS",
              deadline_at: "2026-06-30T17:00:00+00:00",
              effective_deadline_at: "2026-06-30T17:00:00+00:00",
              late_eligible: true,
            },
          ],
        }),
        { status: 200, headers: { "content-type": "application/json" } },
      ),
    );
    const w = mount(DigestBanner);
    await flushPromises();
    expect(w.find('[data-testid="digest-banner"]').exists()).toBe(true);
    expect(w.text()).toContain("Q2 2026");
    expect(w.text()).toContain("late eligible");
  });

  it("dismiss hides the banner", async () => {
    (globalThis.fetch as unknown as ReturnType<typeof vi.fn>).mockResolvedValueOnce(
      new Response(
        JSON.stringify({
          show: true,
          as_of_local: "2026-04-18T09:30:00+00:00",
          items: [],
        }),
        { status: 200, headers: { "content-type": "application/json" } },
      ),
    );
    const w = mount(DigestBanner);
    await flushPromises();
    expect(w.find('[data-testid="digest-banner"]').exists()).toBe(true);
    await w.find('[data-testid="digest-dismiss"]').trigger("click");
    expect(w.find('[data-testid="digest-banner"]').exists()).toBe(false);
  });
});
