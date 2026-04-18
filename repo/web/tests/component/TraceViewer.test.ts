import { describe, it, expect } from "vitest";
import { mount } from "@vue/test-utils";
import TraceViewer from "@/components/TraceViewer.vue";

const trace = {
  engine_version: "1",
  template_version_id: "tv-1",
  rule_set_version_id: "rs-1",
  inputs: { q1: "8", q2: null },
  steps: [
    {
      item_key: "q1",
      raw_present: true,
      raw_value: "8",
      weight: "1",
      effective_value: "8",
      effective_weight: "1",
      missing_strategy: "ZERO_FILL",
      flags: [],
    },
    {
      item_key: "q2",
      raw_present: false,
      raw_value: null,
      weight: "2",
      effective_value: "0",
      effective_weight: "2",
      missing_strategy: "ZERO_FILL",
      flags: ["missing"],
    },
  ],
  totals: { score: "2.6666666666", weighted_sum: "8", weight_sum: "3" },
};

describe("TraceViewer", () => {
  it("renders each step with flags", () => {
    const w = mount(TraceViewer, {
      props: { trace, traceHash: "a".repeat(64) },
    });
    expect(w.find('[data-testid="step-q1"]').exists()).toBe(true);
    expect(w.find('[data-testid="step-q2"]').exists()).toBe(true);
    expect(w.find('[data-testid="step-q2"]').text()).toContain("missing");
  });

  it("displays the trace hash and totals", () => {
    const w = mount(TraceViewer, {
      props: { trace, traceHash: "b".repeat(64) },
    });
    expect(w.find('[data-testid="trace-hash"]').text()).toBe("b".repeat(64));
    expect(w.find('[data-testid="trace-score"]').text()).toContain("2.6666666666");
    expect(w.find('[data-testid="trace-weighted-sum"]').text()).toBe("8");
    expect(w.find('[data-testid="trace-weight-sum"]').text()).toBe("3");
  });
});
