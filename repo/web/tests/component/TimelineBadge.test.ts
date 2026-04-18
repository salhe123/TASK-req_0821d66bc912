import { describe, it, expect } from "vitest";
import { mount } from "@vue/test-utils";
import TimelineBadge from "@/components/TimelineBadge.vue";

const cases: { state: string; label: string; next: RegExp }[] = [
  { state: "NOT_STARTED", label: "Not started", next: /Open and save/ },
  { state: "IN_PROGRESS", label: "In progress", next: /Submit when complete/ },
  { state: "SUBMITTED", label: "Submitted", next: /Awaiting reviewer/ },
  { state: "RETURNED_FOR_REVISION", label: "Returned for revision", next: /Address feedback/ },
  { state: "ARCHIVED", label: "Archived", next: /Complete/ },
];

describe("TimelineBadge", () => {
  for (const c of cases) {
    it(`renders ${c.state} with correct label and next action`, () => {
      const w = mount(TimelineBadge, { props: { state: c.state } });
      expect(w.text()).toContain(c.label);
      expect(w.attributes("title")).toMatch(c.next);
      expect(w.attributes("data-state")).toBe(c.state);
    });
  }

  it("falls back for unknown state", () => {
    const w = mount(TimelineBadge, { props: { state: "WEIRD" } });
    expect(w.text()).toContain("WEIRD");
  });
});
