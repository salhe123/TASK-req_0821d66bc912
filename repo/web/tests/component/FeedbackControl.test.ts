import { describe, it, expect, beforeEach, afterEach, vi } from "vitest";
import { mount, flushPromises } from "@vue/test-utils";
import FeedbackControl from "@/components/FeedbackControl.vue";

function makeResponse(body: unknown, status = 201): Response {
  return new Response(JSON.stringify(body), {
    status,
    headers: { "content-type": "application/json" },
  });
}

describe("FeedbackControl", () => {
  beforeEach(() => vi.stubGlobal("fetch", vi.fn()));
  afterEach(() => vi.unstubAllGlobals());

  const commonProps = {
    subjectKey: "subject-1",
    targetId: "item-1",
    experimentId: "exp-1",
    modelVersionId: "mv-1",
    arm: "A" as const,
  };

  it("sends LIKE payload with full context", async () => {
    const fetchMock = globalThis.fetch as unknown as ReturnType<typeof vi.fn>;
    fetchMock.mockResolvedValueOnce(makeResponse({ kind: "LIKE" }));

    const w = mount(FeedbackControl, { props: commonProps });
    await w.find('[data-testid="fb-like"]').trigger("click");
    await flushPromises();

    const body = JSON.parse(fetchMock.mock.calls[0][1].body);
    expect(body).toMatchObject({
      experiment_id: "exp-1",
      subject_key: "subject-1",
      target_id: "item-1",
      kind: "LIKE",
      arm: "A",
      model_version_id: "mv-1",
    });
  });

  it("marks active state after successful submit", async () => {
    const fetchMock = globalThis.fetch as unknown as ReturnType<typeof vi.fn>;
    fetchMock.mockResolvedValueOnce(makeResponse({ kind: "LIKE" }));
    const w = mount(FeedbackControl, { props: commonProps });
    await w.find('[data-testid="fb-like"]').trigger("click");
    await flushPromises();
    expect(w.find('[data-testid="fb-like"]').classes()).toContain("active");
  });

  it("emits error when the API returns 429", async () => {
    const fetchMock = globalThis.fetch as unknown as ReturnType<typeof vi.fn>;
    fetchMock.mockResolvedValueOnce(
      makeResponse(
        { error: "rate_limited", message: "slow down", details: {} },
        429,
      ),
    );
    const w = mount(FeedbackControl, { props: commonProps });
    await w.find('[data-testid="fb-block"]').trigger("click");
    await flushPromises();
    const errors = w.emitted("error");
    expect(errors).toBeTruthy();
    expect((errors![0][0] as { error: string }).error).toBe("rate_limited");
    expect(w.find('[data-testid="fb-block"]').classes()).not.toContain("active");
  });

  it("emits change with payload on success", async () => {
    const fetchMock = globalThis.fetch as unknown as ReturnType<typeof vi.fn>;
    fetchMock.mockResolvedValueOnce(makeResponse({ kind: "NOT_INTERESTED" }));
    const w = mount(FeedbackControl, { props: commonProps });
    await w.find('[data-testid="fb-not-interested"]').trigger("click");
    await flushPromises();
    const emitted = w.emitted("change");
    expect(emitted).toBeTruthy();
    const p = emitted![0][0] as Record<string, unknown>;
    expect(p.kind).toBe("NOT_INTERESTED");
    expect(p.targetId).toBe("item-1");
    expect(p.experimentId).toBe("exp-1");
  });
});
