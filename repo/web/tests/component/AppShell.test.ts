import { describe, it, expect } from "vitest";
import { mount } from "@vue/test-utils";
import { createRouter, createMemoryHistory } from "vue-router";
import { createPinia, setActivePinia } from "pinia";
import AppShell from "@/components/AppShell.vue";
import DashboardView from "@/views/DashboardView.vue";

function makeRouter() {
  return createRouter({
    history: createMemoryHistory(),
    routes: [{ path: "/", component: DashboardView }],
  });
}

describe("AppShell", () => {
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
});
