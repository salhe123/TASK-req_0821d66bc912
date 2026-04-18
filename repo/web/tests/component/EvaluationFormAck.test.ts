import { describe, it, expect } from "vitest";
import { mount } from "@vue/test-utils";
import EvaluationForm from "@/components/EvaluationForm.vue";

const items = [
  { key: "q1", label: "Q1", weight: 1, required: true, missing_strategy: "ZERO_FILL",
    min_value: 0, max_value: 10 },
];

describe("EvaluationForm threshold acknowledgement", () => {
  it("emits submittable=false when a value exceeds threshold without ack", async () => {
    const w = mount(EvaluationForm, { props: { items } });
    await w.find('[data-testid="input-q1"]').setValue("99");
    const emitted = w.emitted("submittable");
    expect(emitted).toBeTruthy();
    const last = emitted![emitted!.length - 1][0] as { submittable: boolean; thresholdKeys: string[] };
    expect(last.submittable).toBe(false);
    expect(last.thresholdKeys).toContain("q1");
  });

  it("emits submittable=true after acknowledgement", async () => {
    const w = mount(EvaluationForm, { props: { items } });
    await w.find('[data-testid="input-q1"]').setValue("99");
    await w.find('[data-testid="threshold-ack-checkbox"]').setValue(true);
    const emitted = w.emitted("submittable");
    const last = emitted![emitted!.length - 1][0] as { submittable: boolean };
    expect(last.submittable).toBe(true);
  });

  it("no acknowledgement required when no thresholds breached", async () => {
    const w = mount(EvaluationForm, { props: { items } });
    await w.find('[data-testid="input-q1"]').setValue("5");
    expect(w.find('[data-testid="threshold-ack"]').exists()).toBe(false);
    const emitted = w.emitted("submittable");
    const last = emitted![emitted!.length - 1][0] as { submittable: boolean };
    expect(last.submittable).toBe(true);
  });
});
