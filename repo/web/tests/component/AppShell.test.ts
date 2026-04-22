import { describe, it, expect, beforeEach, afterEach, vi } from "vitest";
import { mount, flushPromises } from "@vue/test-utils";
import { createRouter, createMemoryHistory } from "vue-router";
import { createPinia, setActivePinia } from "pinia";
import AppShell from "@/components/AppShell.vue";
import DashboardView from "@/views/DashboardView.vue";
import { useSessionStore } from "@/stores/session";

function seedSessionUser() {
  const s = useSessionStore();
  s.user = {
    userId: "u1",
    username: "tester",
    displayName: "Tester",
    roles: ["Administrator"],
    permissions: [{ resource: "*", action: "*" }],
    fieldViewAllowlist: [],
  };
}

function jsonResponse(body: unknown, status = 200): Response {
  return new Response(JSON.stringify(body), {
    status,
    headers: { "content-type": "application/json" },
  });
}

function makeRouter() {
  return createRouter({
    history: createMemoryHistory(),
    routes: [{ path: "/", component: DashboardView }],
  });
}

describe("AppShell", () => {
  beforeEach(() => {
    // Every fetch caller (DashboardView, DigestBanner, …) must get its own
    // Response instance — a Response body is single-read, so reusing one via
    // mockResolvedValue leaks "Body has already been read" rejections across
    // consumers.
    vi.stubGlobal(
      "fetch",
      vi.fn(() =>
        Promise.resolve(
          jsonResponse({ show: false, as_of_local: "", items: [] }),
        ),
      ),
    );
  });
  afterEach(() => vi.unstubAllGlobals());

  it("renders every nav item with expected labels", async () => {
    setActivePinia(createPinia());
    const router = makeRouter();
    router.push("/");
    await router.isReady();

    const wrapper = mount(AppShell, {
      global: { plugins: [router] },
    });

    const labels = wrapper.findAll("li").map((li) => li.text());
    expect(labels).toEqual([
      "Dashboard",
      "Evaluation Cycles",
      "Build Plans",
      "Model Registry",
      "Feedback",
      "Administration",
    ]);
  });

  it("disables non-implemented nav items", async () => {
    setActivePinia(createPinia());
    const router = makeRouter();
    router.push("/");
    await router.isReady();

    const wrapper = mount(AppShell, {
      global: { plugins: [router] },
    });

    const disabled = wrapper.findAll("a[aria-disabled='true']");
    expect(disabled.length).toBe(5);
  });

  it("surfaces the digest banner globally when the API returns show=true", async () => {
    const m = globalThis.fetch as unknown as ReturnType<typeof vi.fn>;
    m.mockReset();
    // Build a fresh Response on every invocation so both the DigestBanner and
    // any sibling fetch (e.g. DashboardView) can read their own body.
    m.mockImplementation(() =>
      Promise.resolve(
        jsonResponse({
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
      ),
    );

    setActivePinia(createPinia());
    seedSessionUser();
    const router = makeRouter();
    router.push("/");
    await router.isReady();

    const w = mount(AppShell, { global: { plugins: [router] } });
    await flushPromises();

    expect(w.find('[data-testid="digest-banner"]').exists()).toBe(true);
    expect(w.text()).toContain("Q2 2026");
  });
});
