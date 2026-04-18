import { describe, it, expect } from "vitest";
import { mount } from "@vue/test-utils";
import MaintenanceBanner from "@/components/MaintenanceBanner.vue";

describe("MaintenanceBanner", () => {
  it("renders the reason text when provided", () => {
    const w = mount(MaintenanceBanner, {
      props: { reason: "Restoring from archive mgew-2026-04-18.bin" },
    });
    expect(w.find('[data-testid="maintenance-banner"]').exists()).toBe(true);
    expect(w.text()).toContain("Restoring from archive mgew-2026-04-18.bin");
  });

  it("falls back to a default message when reason is empty", () => {
    const w = mount(MaintenanceBanner, { props: { reason: "" } });
    expect(w.text()).toMatch(/restore in progress/);
  });
});
