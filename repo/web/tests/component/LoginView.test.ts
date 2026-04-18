import { describe, it, expect, vi, beforeEach, afterEach } from "vitest";
import { mount, flushPromises } from "@vue/test-utils";
import { createPinia, setActivePinia } from "pinia";
import { createRouter, createMemoryHistory } from "vue-router";
import LoginView from "@/views/LoginView.vue";
import DashboardView from "@/views/DashboardView.vue";

function makeRouter() {
  return createRouter({
    history: createMemoryHistory(),
    routes: [
      { path: "/login", name: "login", component: LoginView, meta: { public: true } },
      { path: "/", name: "dashboard", component: DashboardView },
    ],
  });
}

async function drain() {
  // A submit() chain awaits fetch → response.text() → json parse → router.push.
  // flushPromises alone doesn't cover router push + subsequent re-renders on
  // every runtime; alternating with nextTick-style ticks is the safe pattern.
  for (let i = 0; i < 8; i++) {
    await flushPromises();
  }
}

describe("LoginView", () => {
  beforeEach(() => {
    setActivePinia(createPinia());
    vi.stubGlobal("fetch", vi.fn());
  });
  afterEach(() => {
    vi.unstubAllGlobals();
  });

  it("submits credentials and redirects on success", async () => {
    const fetchMock = globalThis.fetch as unknown as ReturnType<typeof vi.fn>;
    fetchMock
      .mockResolvedValueOnce(
        new Response(
          JSON.stringify({
            user_id: "u1",
            username: "admin",
            roles: ["Administrator"],
            csrf_token: "csrf-abc",
            session_token: "s.t",
            expires_at: "2026-04-18T13:00:00+00:00",
          }),
          { status: 200, headers: { "content-type": "application/json" } },
        ),
      )
      .mockResolvedValueOnce(
        new Response(
          JSON.stringify({
            user_id: "u1",
            username: "admin",
            display_name: "",
            roles: ["Administrator"],
            permissions: [{ resource: "*", action: "*" }],
            field_view_allowlist: ["*"],
          }),
          { status: 200, headers: { "content-type": "application/json" } },
        ),
      );

    const router = makeRouter();
    router.push("/login");
    await router.isReady();

    const wrapper = mount(LoginView, { global: { plugins: [router] } });
    await wrapper.find('[data-testid="username"]').setValue("admin");
    await wrapper.find('[data-testid="password"]').setValue("Abcd1234Efgh!");
    await wrapper.find("form").trigger("submit.prevent");
    await drain();

    expect(fetchMock).toHaveBeenCalledTimes(2);
    expect(router.currentRoute.value.name).toBe("dashboard");
  });

  it("shows error on invalid credentials", async () => {
    const fetchMock = globalThis.fetch as unknown as ReturnType<typeof vi.fn>;
    fetchMock.mockResolvedValueOnce(
      new Response(
        JSON.stringify({
          error: "invalid_credentials",
          message: "invalid username or password",
          details: {},
        }),
        { status: 401, headers: { "content-type": "application/json" } },
      ),
    );
    const router = makeRouter();
    router.push("/login");
    await router.isReady();
    const wrapper = mount(LoginView, { global: { plugins: [router] } });
    await wrapper.find('[data-testid="username"]').setValue("bad");
    await wrapper.find('[data-testid="password"]').setValue("bad");
    await wrapper.find("form").trigger("submit.prevent");
    await drain();
    expect(wrapper.find('[data-testid="login-error"]').exists()).toBe(true);
    expect(wrapper.find('[data-testid="login-error"]').text()).toMatch(/invalid/);
  });

  it("shows lockout message on 423", async () => {
    const fetchMock = globalThis.fetch as unknown as ReturnType<typeof vi.fn>;
    fetchMock.mockResolvedValueOnce(
      new Response(
        JSON.stringify({
          error: "account_locked",
          message: "account locked after too many failed attempts",
          details: {},
        }),
        { status: 423, headers: { "content-type": "application/json" } },
      ),
    );
    const router = makeRouter();
    router.push("/login");
    await router.isReady();
    const wrapper = mount(LoginView, { global: { plugins: [router] } });
    await wrapper.find('[data-testid="username"]').setValue("u");
    await wrapper.find('[data-testid="password"]').setValue("p");
    await wrapper.find("form").trigger("submit.prevent");
    await drain();
    expect(wrapper.find('[data-testid="login-error"]').exists()).toBe(true);
    expect(wrapper.find('[data-testid="login-error"]').text()).toMatch(/locked/);
  });
});
