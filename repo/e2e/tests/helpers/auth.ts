import { APIRequestContext } from "@playwright/test";

export const ADMIN_USER = "e2e_admin";
export const ADMIN_PASS = "E2E-Admin-Pass-1";

/**
 * Log a user in via the real /api/auth/login endpoint (through the nginx proxy),
 * and return the Authorization + CSRF headers needed for subsequent requests.
 * This drives the full stack (web → api → db) without mocking.
 */
export async function login(
  request: APIRequestContext,
  username: string = ADMIN_USER,
  password: string = ADMIN_PASS,
): Promise<{
  authHeaders: Record<string, string>;
  sessionToken: string;
  csrfToken: string;
  userId: string;
  roles: string[];
}> {
  const resp = await request.post("/api/auth/login", {
    data: { username, password },
  });
  if (!resp.ok()) {
    throw new Error(`login failed: ${resp.status()} ${await resp.text()}`);
  }
  const body = await resp.json();
  return {
    authHeaders: {
      Authorization: `Bearer ${body.session_token}`,
      "X-CSRF-Token": body.csrf_token,
    },
    sessionToken: body.session_token,
    csrfToken: body.csrf_token,
    userId: body.user_id,
    roles: body.roles,
  };
}

export function uid(): string {
  return Math.random().toString(36).slice(2, 10);
}

/**
 * Run a successful evaluation run on a version, then promote it. Required by
 * the post-audit promotion gate.
 */
export async function promoteWithEvalRun(
  request: APIRequestContext,
  authHeaders: Record<string, string>,
  modelId: string,
  versionId: string,
) {
  const startResp = await request.post(
    `/api/models/${modelId}/versions/${versionId}/runs`,
    {
      headers: authHeaders,
      data: { kind: "EVALUATION", dataset_ref: "holdout-e2e" },
    },
  );
  if (!startResp.ok()) {
    throw new Error(`start run failed: ${startResp.status()} ${await startResp.text()}`);
  }
  const run = await startResp.json();
  const completeResp = await request.post(
    `/api/models/${modelId}/versions/${versionId}/runs/${run.id}/complete`,
    {
      headers: authHeaders,
      data: { status: "SUCCEEDED", metrics: { auc: 0.9 } },
    },
  );
  if (!completeResp.ok()) {
    throw new Error(`complete run failed: ${completeResp.status()} ${await completeResp.text()}`);
  }
  return await request.post(`/api/models/${modelId}/versions/${versionId}/promote`, {
    headers: authHeaders,
  });
}

/**
 * Create a new user via the admin API and return { id, username, password }.
 */
export async function createUser(
  request: APIRequestContext,
  authHeaders: Record<string, string>,
  roles: string[] = ["Evaluator"],
  usernamePrefix = "u",
): Promise<{ id: string; username: string; password: string }> {
  const username = `${usernamePrefix}_${uid()}`;
  const password = "Seeded-e2e-password-1";
  const resp = await request.post("/api/admin/users", {
    headers: authHeaders,
    data: { username, password, roles, display_name: username },
  });
  if (!resp.ok()) {
    throw new Error(`createUser failed: ${resp.status()} ${await resp.text()}`);
  }
  const body = await resp.json();
  return { id: body.id, username, password };
}
