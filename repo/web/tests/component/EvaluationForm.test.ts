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
});
