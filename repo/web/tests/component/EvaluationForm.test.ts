import { describe, it, expect } from "vitest";
import { mount } from "@vue/test-utils";
import EvaluationForm from "@/components/EvaluationForm.vue";

const items = [
  {
    key: "q1",
    label: "Question 1",
    weight: 1.0,
    required: true,
    missing_strategy: "ZERO_FILL",
  },
  {
    key: "q2",
    label: "Question 2",
    weight: 2.0,
    required: true,
    missing_strategy: "ZERO_FILL",
    min_value: 0,
    max_value: 10,
  },
];

describe("EvaluationForm", () => {
  it("renders each template item and required markers", () => {
    const w = mount(EvaluationForm, { props: { items } });
    expect(w.text()).toContain("Question 1");
    expect(w.text()).toContain("Question 2");
    expect(w.findAll(".req")).toHaveLength(2);
  });

  it("computes weighted subtotal as values change", async () => {
    const w = mount(EvaluationForm, { props: { items } });
    await w.find('[data-testid="input-q1"]').setValue("8");
    await w.find('[data-testid="input-q2"]').setValue("10");
    // Weighted avg = (8*1 + 10*2) / (1+2) = 28/3 ≈ 9.3333
    expect(w.find('[data-testid="subtotal"]').text()).toContain("9.3333");
  });

  it("marks missing flag for blank required item", () => {
    const w = mount(EvaluationForm, { props: { items } });
    const flagChips = w.findAll('.chip[data-flag="missing"]');
    expect(flagChips.length).toBe(2);
  });

  it("marks threshold_exceeded when value outside min/max", async () => {
    const w = mount(EvaluationForm, { props: { items } });
    await w.find('[data-testid="input-q2"]').setValue("999");
    expect(w.find('.chip[data-flag="threshold_exceeded"]').exists()).toBe(true);
  });

  it("emits update:values when values change", async () => {
    const w = mount(EvaluationForm, { props: { items } });
    await w.find('[data-testid="input-q1"]').setValue("5");
    const emitted = w.emitted("update:values");
    expect(emitted).toBeTruthy();
    const last = emitted![emitted!.length - 1][0] as Record<string, unknown>;
    expect(last.q1).toBe(5);
  });

  it("ZERO_FILL keeps weight in denominator for missing items", async () => {
    // Both items are ZERO_FILL. Filling q1 only should drag the subtotal down
    // because q2's weight still counts.
    const w = mount(EvaluationForm, { props: { items } });
    await w.find('[data-testid="input-q1"]').setValue("6");
    // numerator = 6*1 + 0*2 = 6; denominator = 1 + 2 = 3; subtotal = 2.0000
    expect(w.find('[data-testid="subtotal"]').text()).toContain("2.0000");
  });

  it("EXCLUDE_FROM_DENOMINATOR drops weight for missing items", async () => {
    const excludeItems = [
      { ...items[0] },
      { ...items[1], missing_strategy: "EXCLUDE_FROM_DENOMINATOR" },
    ];
    const w = mount(EvaluationForm, { props: { items: excludeItems } });
    await w.find('[data-testid="input-q1"]').setValue("6");
    // q2 excluded entirely → numerator = 6*1 = 6; denominator = 1; subtotal = 6.0000
    expect(w.find('[data-testid="subtotal"]').text()).toContain("6.0000");
  });

  it("mixed missing strategies: excluded item doesn't drag ZERO_FILL item", async () => {
    const mixed = [
      { key: "a", label: "A", weight: 1.0, required: false,
        missing_strategy: "ZERO_FILL" },
      { key: "b", label: "B", weight: 3.0, required: false,
        missing_strategy: "ZERO_FILL" },
      { key: "c", label: "C", weight: 5.0, required: false,
        missing_strategy: "EXCLUDE_FROM_DENOMINATOR" },
    ];
    const w = mount(EvaluationForm, { props: { items: mixed } });
    await w.find('[data-testid="input-a"]').setValue("4");
    // b is ZERO_FILL missing (0, weight 3); c is excluded; a=4, w=1.
    // numerator = 4*1 + 0*3 = 4; denominator = 1 + 3 = 4; subtotal = 1.0000
    expect(w.find('[data-testid="subtotal"]').text()).toContain("1.0000");
  });
});
