import { describe, it, expect, beforeEach, afterEach, vi } from "vitest";
import { mount, flushPromises } from "@vue/test-utils";
import { createPinia, setActivePinia } from "pinia";
import AdminView from "@/views/AdminView.vue";

function jsonResponse(body: unknown, status = 200): Response {
  return new Response(JSON.stringify(body), {
    status,
    headers: { "content-type": "application/json" },
  });
}

function setFetchQueue(queue: Array<() => Response>) {
  const m = vi.fn();
  for (const fn of queue) m.mockResolvedValueOnce(fn());
  vi.stubGlobal("fetch", m);
  return m;
}

describe("AdminView", () => {
  beforeEach(() => setActivePinia(createPinia()));
  afterEach(() => vi.unstubAllGlobals());

  it("renders the users list on initial load", async () => {
    setFetchQueue([
      () =>
        jsonResponse({
          items: [
            {
              id: "u1",
              username: "admin",
              display_name: "",
              is_active: true,
              locked: false,
              roles: ["Administrator"],
              last_login_at: null,
            },
          ],
        }),
    ]);
    const w = mount(AdminView);
    await flushPromises();
    await flushPromises();
    expect(w.text()).toContain("admin");
    expect(w.text()).toContain("Administrator");
  });

  it("switches to audit tab and fetches audit logs with filter", async () => {
    const fetchMock = setFetchQueue([
      () => jsonResponse({ items: [] }), // initial users load
      () => jsonResponse({ items: [] }), // first audit load after tab switch
      () =>
        jsonResponse({
          items: [
            {
              id: "a1",
              action: "MODEL_PROMOTION",
              resource_type: "model",
              resource_id: "m1",
              actor_user_id: "u1",
              created_at: "2026-04-18T10:00:00+00:00",
              payload: {},
            },
          ],
        }),
    ]);
    const w = mount(AdminView);
    await flushPromises();

    await w.find('[data-testid="tab-audit"]').trigger("click");
    await flushPromises();
    await flushPromises();

    await w.find('[data-testid="audit-action"]').setValue("MODEL_PROMOTION");
    await w
      .findAll("button")
      .find((b) => b.text() === "Apply")!
      .trigger("click");
    await flushPromises();
    await flushPromises();

    expect(w.find('[data-testid="audit-row-a1"]').exists()).toBe(true);
    const auditCall = fetchMock.mock.calls[2][0] as string;
    expect(auditCall).toContain("action=MODEL_PROMOTION");
  });

  it("creates a backup and shows the resulting archive", async () => {
    setFetchQueue([
      () => jsonResponse({ items: [] }), // users (initial)
      () => jsonResponse({ items: [] }), // backups (after switch)
      () =>
        jsonResponse(
          {
            id: "b1",
            filename: "mgew-test.bin",
            size_bytes: 123,
            manifest_hash: "a".repeat(64),
            kek_fingerprint: "b".repeat(64),
            created_at: "2026-04-18T12:00:00+00:00",
          },
          201,
        ),
      () =>
        jsonResponse({
          items: [
            {
              id: "b1",
              filename: "mgew-test.bin",
              size_bytes: 123,
              manifest_hash: "a".repeat(64),
              kek_fingerprint: "b".repeat(64),
              created_at: "2026-04-18T12:00:00+00:00",
            },
          ],
        }),
    ]);
    const w = mount(AdminView);
    await flushPromises();

    await w.find('[data-testid="tab-backups"]').trigger("click");
    await flushPromises();
    await flushPromises();

    await w.find('[data-testid="backup-create"]').trigger("click");
    await flushPromises();
    await flushPromises();

    expect(w.find('[data-testid="backup-b1"]').exists()).toBe(true);
    expect(w.find('[data-testid="backup-b1"]').text()).toContain("mgew-test.bin");
  });

  it("stage → commit flow reveals and hides the restore dialog", async () => {
    setFetchQueue([
      () => jsonResponse({ items: [] }), // users
      () =>
        jsonResponse({
          items: [
            {
              id: "b1",
              filename: "mgew-test.bin",
              size_bytes: 10,
              manifest_hash: "a".repeat(64),
              kek_fingerprint: "b".repeat(64),
              created_at: "2026-04-18T12:00:00+00:00",
            },
          ],
        }), // backups
      () =>
        jsonResponse({
          maintenance: { active: true },
          restore: { id: "r1", state: "staged" },
        }), // stage
      () =>
        jsonResponse({
          id: "r1",
          archive_id: "b1",
          state: "committed",
          started_by: "u1",
          kek_fingerprint: "b".repeat(64),
          started_at: "2026-04-18T12:01:00+00:00",
          completed_at: "2026-04-18T12:02:00+00:00",
          notes: {},
        }), // commit
      () => jsonResponse({ items: [] }), // reload backups
    ]);
    const w = mount(AdminView);
    await flushPromises();
    await w.find('[data-testid="tab-backups"]').trigger("click");
    await flushPromises();
    await flushPromises();
    await w.find('[data-testid="stage-b1"]').trigger("click");
    await flushPromises();
    await flushPromises();
    expect(w.find('[data-testid="restore-confirm"]').exists()).toBe(true);

    await w.find('[data-testid="restore-commit"]').trigger("click");
    await flushPromises();
    await flushPromises();
    expect(w.find('[data-testid="restore-confirm"]').exists()).toBe(false);
  });
});
