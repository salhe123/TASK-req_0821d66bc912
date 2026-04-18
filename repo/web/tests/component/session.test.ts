import { describe, it, expect, beforeEach, vi, afterEach } from "vitest";
import { createPinia, setActivePinia } from "pinia";
import { useSessionStore } from "@/stores/session";

describe("session store", () => {
  beforeEach(() => {
    setActivePinia(createPinia());
    vi.stubGlobal("fetch", vi.fn());
  });
  afterEach(() => {
    vi.unstubAllGlobals();
  });

  it("hasPermission honours wildcard", () => {
    const store = useSessionStore();
    store.user = {
      userId: "u",
      username: "u",
      displayName: "",
      roles: ["Administrator"],
      permissions: [{ resource: "*", action: "*" }],
      fieldViewAllowlist: ["*"],
    };
    expect(store.hasPermission("anything", "anything")).toBe(true);
  });

  it("hasPermission respects exact match", () => {
    const store = useSessionStore();
    store.user = {
      userId: "u",
      username: "u",
      displayName: "",
      roles: ["Evaluator"],
      permissions: [{ resource: "cycle", action: "participate" }],
      fieldViewAllowlist: [],
    };
    expect(store.hasPermission("cycle", "participate")).toBe(true);
    expect(store.hasPermission("user", "manage")).toBe(false);
  });

  it("clear nulls user and csrf", () => {
    const store = useSessionStore();
    store.user = {
      userId: "u",
      username: "u",
      displayName: "",
      roles: [],
      permissions: [],
      fieldViewAllowlist: [],
    };
    store.csrfToken = "x";
    store.clear();
    expect(store.user).toBeNull();
    expect(store.csrfToken).toBeNull();
    expect(store.isAuthenticated).toBe(false);
  });
});
