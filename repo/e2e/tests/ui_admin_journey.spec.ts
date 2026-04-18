import { test, expect } from "@playwright/test";
import { browserLogin, apiContext } from "./helpers/ui";
import { createUser, uid } from "./helpers/auth";

/**
 * Browser-driven AdminView journeys against the real API.
 * No transport mocking — every action results in a real HTTP call through
 * nginx and a DB write (or read) in the api/db containers.
 */

test("admin can switch tabs and the audit filter bumps the backing query", async ({
  page,
  request,
}) => {
  // Seed a distinctive audit row via API — a template creation is the simplest
  // pre-existing audited action.
  const api = await apiContext(request);
  const templateResp = await request.post("/api/templates", {
    headers: api.headers,
    data: {
      name: `audit_tpl_${uid()}`,
      items: [
        {
          key: "q", label: "Q", weight: 1, required: true, missing_strategy: "ZERO_FILL",
        },
      ],
    },
  });
  expect(templateResp.status()).toBe(201);

  await browserLogin(page);
  await page.goto("/admin");

  // Users tab is active by default — the admin user is visible.
  await expect(page.getByRole("heading", { level: 2, name: "Administration" })).toBeVisible();
  await expect(page.getByText("Administrator", { exact: false }).first()).toBeVisible();

  // Switch to Audit tab → waits for the /api/admin/audit/logs request.
  const auditInit = page.waitForResponse((r) =>
    r.url().includes("/api/admin/audit/logs") && r.request().method() === "GET",
  );
  await page.getByTestId("tab-audit").click();
  await auditInit;

  // Apply a filter on action=TEMPLATE_CREATE — the next request must carry that param.
  const filtered = page.waitForResponse(
    (r) =>
      r.url().includes("/api/admin/audit/logs") &&
      r.url().includes("action=TEMPLATE_CREATE"),
  );
  await page.getByTestId("audit-action").fill("TEMPLATE_CREATE");
  await page.getByRole("button", { name: "Apply" }).click();
  const filteredResp = await filtered;
  expect(filteredResp.status()).toBe(200);

  // After the filter, audit rows visible contain the TEMPLATE_CREATE action.
  await expect(page.locator('code', { hasText: "TEMPLATE_CREATE" }).first()).toBeVisible();
});

test("admin creates a backup and sees it appear in the list", async ({ page, request }) => {
  await browserLogin(page);
  await page.goto("/admin");

  const backupsLoad = page.waitForResponse((r) =>
    r.url().endsWith("/api/admin/backups") && r.request().method() === "GET",
  );
  await page.getByTestId("tab-backups").click();
  await backupsLoad;

  // Click "Create archive now" — wait for the POST + reload.
  const createResp = page.waitForResponse((r) =>
    r.url().endsWith("/api/admin/backups") && r.request().method() === "POST",
  );
  const reload = page.waitForResponse((r) =>
    r.url().endsWith("/api/admin/backups") && r.request().method() === "GET",
  );
  await page.getByTestId("backup-create").click();
  const create = await createResp;
  expect(create.status()).toBe(201);
  await reload;

  // A backup row renders with the filename from the POST response.
  const created = await create.json();
  await expect(page.locator(`code`, { hasText: created.filename })).toBeVisible();
  await expect(page.getByTestId(`backup-${created.id}`)).toBeVisible();
});

test("admin stage-commit flow opens and closes the restore dialog", async ({
  page,
  request,
}) => {
  // Pre-create a backup via API so the list always has exactly one row we know.
  const api = await apiContext(request);
  const createResp = await request.post("/api/admin/backups", { headers: api.headers });
  expect(createResp.status()).toBe(201);
  const archive = await createResp.json();

  await browserLogin(page);
  await page.goto("/admin");

  const backupsLoad = page.waitForResponse((r) =>
    r.url().endsWith("/api/admin/backups") && r.request().method() === "GET",
  );
  await page.getByTestId("tab-backups").click();
  await backupsLoad;

  // Stage → dialog becomes visible, maintenance snapshot returned.
  const stageResp = page.waitForResponse((r) =>
    r.url().includes(`/api/admin/backups/${archive.id}/stage`),
  );
  await page.getByTestId(`stage-${archive.id}`).click();
  const staged = await stageResp;
  expect(staged.status()).toBe(200);
  await expect(page.getByTestId("restore-confirm")).toBeVisible();

  // Commit → dialog disappears, BACKUP_RESTORE audited.
  const commitResp = page.waitForResponse((r) =>
    r.url().includes(`/api/admin/backups/${archive.id}/commit`),
  );
  await page.getByTestId("restore-commit").click();
  const committed = await commitResp;
  expect(committed.status()).toBe(200);
  await expect(page.getByTestId("restore-confirm")).toBeHidden();

  // Verify via API that the audit row exists with the expected final_state.
  const auditResp = await request.get(
    `/api/admin/audit/logs?action=BACKUP_RESTORE&resource_id=${archive.id}`,
    { headers: api.headers },
  );
  const audits = await auditResp.json();
  const row = audits.items.find((r: any) => r.resource_id === archive.id);
  expect(row).toBeTruthy();
  expect(row.payload.final_state).toBe("committed");
  expect(row.payload.kek_fingerprint).toHaveLength(64);
});

test("non-admin user lands on dashboard but cannot load admin API data", async ({
  page,
  request,
}) => {
  const api = await apiContext(request);
  const eval_ = await createUser(request, api.headers, ["Evaluator"], "evview");

  await browserLogin(page, eval_.username, eval_.password);

  // Navigate to /admin — the SPA doesn't hide the route, so the API is where
  // authorisation shows up: the users listing returns 403 for a non-admin.
  const listing = page.waitForResponse(
    (r) => r.url().endsWith("/api/admin/users") && r.request().method() === "GET",
  );
  await page.goto("/admin");
  const resp = await listing;
  expect(resp.status()).toBe(403);
  const body = await resp.json();
  expect(body.error).toBe("permission_denied");
});
