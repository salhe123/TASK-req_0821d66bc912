import { describe, it, expect } from "vitest";
import { mount } from "@vue/test-utils";
import BomDiffView from "@/components/BomDiffView.vue";

function line(overrides: Record<string, unknown> = {}) {
  return {
    line_identity_key: "K1",
    part_number: "P-1",
    description: "",
    quantity: "1",
    unit: "ea",
    notes: "",
    tags: [],
    ...overrides,
  };
}

describe("BomDiffView", () => {
  it("shows empty state when no entries", () => {
    const w = mount(BomDiffView, { props: { entries: [] } });
    expect(w.text()).toContain("No differences");
  });

  it("colors added lines green", () => {
    const w = mount(BomDiffView, {
      props: {
        entries: [
          { line_identity_key: "K1", changes: ["ADDED"], base: null, target: line() },
        ],
      },
    });
    const row = w.find('[data-testid="diff-row-K1"]');
    expect(row.classes()).toContain("diff__row--added");
  });

  it("shows all change chips", () => {
    const w = mount(BomDiffView, {
      props: {
        entries: [
          {
            line_identity_key: "K1",
            changes: ["QUANTITY_CHANGED", "PART_CHANGED"],
            base: line({ part_number: "A" }),
            target: line({ part_number: "B", quantity: "2" }),
          },
        ],
      },
    });
    const chips = w.findAll(".chip").map((c) => c.text());
    expect(chips).toContain("QUANTITY_CHANGED");
    expect(chips).toContain("PART_CHANGED");
  });

  it("colors removed rows red", () => {
    const w = mount(BomDiffView, {
      props: {
        entries: [
          { line_identity_key: "K1", changes: ["REMOVED"], base: line(), target: null },
        ],
      },
    });
    expect(w.find('[data-testid="diff-row-K1"]').classes()).toContain("diff__row--removed");
  });
});
