import { describe, it, expect, beforeEach, afterEach, vi } from "vitest";
import { mount, flushPromises } from "@vue/test-utils";
import RoutingConsole from "@/components/RoutingConsole.vue";

const expData = {
  id: "e1",
  name: "exp",
  description: "",
  weight_a: 90,
  weight_b: 10,
  ingest_enabled: true,
  apply_enabled: true,
  model_a_id: "a1",
  model_b_id: "b1",
};

describe("RoutingConsole", () => {
  beforeEach(() => vi.stubGlobal("fetch", vi.fn()));
  afterEach(() => vi.unstubAllGlobals());

  it("disables inputs when user cannot edit", () => {
    const w = mount(RoutingConsole, { props: { experiment: expData, canEdit: false } });
    expect((w.find('[data-testid="weight-a-slider"]').element as HTMLInputElement).disabled).toBe(true);
    expect((w.find('[data-testid="toggle-ingest"]').element as HTMLInputElement).disabled).toBe(true);
  });

  it("emits updated with rollback flip when confirmed", async () => {
    const fetchMock = globalThis.fetch as unknown as ReturnType<typeof vi.fn>;
    fetchMock.mockResolvedValueOnce(
      new Response(
        JSON.stringify({ ...expData, weight_a: 100, weight_b: 0 }),
        { status: 200, headers: { "content-type": "application/json" } },
      ),
    );

    const w = mount(RoutingConsole, { props: { experiment: expData, canEdit: true } });
    await w.find('[data-testid="open-rollback"]').trigger("click");
    await w.find('[data-testid="rollback-reason"]').setValue("guardrail breach");
    await w.find('[data-testid="rollback-submit"]').trigger("click");
    await flushPromises();

    const emitted = w.emitted("updated");
    expect(emitted).toBeTruthy();
    const payload = emitted![0][0] as typeof expData;
    expect(payload.weight_a).toBe(100);
    expect(payload.weight_b).toBe(0);

    const call = fetchMock.mock.calls[0];
    expect(call[0]).toBe(`/api/experiments/${expData.id}/rollback`);
    expect(JSON.parse(call[1].body)).toMatchObject({ trigger: "manual", reason: "guardrail breach" });
  });

  it("persists a weight change", async () => {
    const fetchMock = globalThis.fetch as unknown as ReturnType<typeof vi.fn>;
    fetchMock.mockResolvedValueOnce(
      new Response(
        JSON.stringify({ ...expData, weight_a: 80, weight_b: 20 }),
        { status: 200, headers: { "content-type": "application/json" } },
      ),
    );
    const w = mount(RoutingConsole, { props: { experiment: expData, canEdit: true } });
    const slider = w.find('[data-testid="weight-a-slider"]');
    (slider.element as HTMLInputElement).value = "80";
    await slider.trigger("input");
    await slider.trigger("change");
    await flushPromises();
    expect(JSON.parse(fetchMock.mock.calls[0][1].body)).toEqual({ weight_a: 80 });
  });
});
