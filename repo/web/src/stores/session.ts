import { defineStore } from "pinia";
import { computed, ref } from "vue";
import { apiGet, apiPost, setCsrfTokenProvider } from "@/lib/api";

export interface SessionPermission {
  resource: string;
  action: string;
}

export interface SessionUser {
  userId: string;
  username: string;
  displayName: string;
  roles: string[];
  permissions: SessionPermission[];
  fieldViewAllowlist: string[];
}

interface LoginResponse {
  user_id: string;
  username: string;
  roles: string[];
  csrf_token: string;
  session_token: string;
  expires_at: string;
}

interface MeResponse {
  user_id: string;
  username: string;
  display_name: string;
  roles: string[];
  permissions: SessionPermission[];
  field_view_allowlist: string[];
  timezone?: string;
  csrf_token?: string;
}

export const useSessionStore = defineStore("session", () => {
  const user = ref<SessionUser | null>(null);
  const csrfToken = ref<string | null>(null);
  const lockoutMessage = ref<string | null>(null);

  setCsrfTokenProvider(() => csrfToken.value);

  const isAuthenticated = computed(() => user.value !== null);

  function hasRole(role: string): boolean {
    return user.value?.roles.includes(role) ?? false;
  }

  function hasPermission(resource: string, action: string): boolean {
    if (!user.value) return false;
    return (
      user.value.permissions.some((p) => p.resource === "*" && p.action === "*") ||
      user.value.permissions.some((p) => p.resource === resource && p.action === action)
    );
  }

  async function login(username: string, password: string): Promise<{ ok: boolean; error?: string }> {
    lockoutMessage.value = null;
    const result = await apiPost<LoginResponse>("/api/auth/login", { username, password });
    if (!result.ok) {
      if (result.status === 423) {
        lockoutMessage.value = result.message;
      }
      return { ok: false, error: result.error };
    }
    csrfToken.value = result.data.csrf_token;
    const me = await apiGet<MeResponse>("/api/auth/me");
    if (!me.ok) return { ok: false, error: me.error };
    user.value = {
      userId: me.data.user_id,
      username: me.data.username,
      displayName: me.data.display_name,
      roles: me.data.roles,
      permissions: me.data.permissions,
      fieldViewAllowlist: me.data.field_view_allowlist,
    };
    return { ok: true };
  }

  async function refresh(): Promise<void> {
    const me = await apiGet<MeResponse>("/api/auth/me");
    if (!me.ok) {
      user.value = null;
      csrfToken.value = null;
      return;
    }
    user.value = {
      userId: me.data.user_id,
      username: me.data.username,
      displayName: me.data.display_name,
      roles: me.data.roles,
      permissions: me.data.permissions,
      fieldViewAllowlist: me.data.field_view_allowlist,
    };
    // Page-reload restore: the session cookie survived but Pinia's csrfToken
    // didn't, so mutating requests would fail CSRF. /me returns the current
    // session's csrf_token exactly so the SPA can rehydrate it here.
    if (me.data.csrf_token) {
      csrfToken.value = me.data.csrf_token;
    }
  }

  async function logout(): Promise<void> {
    await apiPost("/api/auth/logout");
    user.value = null;
    csrfToken.value = null;
  }

  function clear(): void {
    user.value = null;
    csrfToken.value = null;
  }

  return {
    user,
    csrfToken,
    lockoutMessage,
    isAuthenticated,
    hasRole,
    hasPermission,
    login,
    logout,
    refresh,
    clear,
  };
});
