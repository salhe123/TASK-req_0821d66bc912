import { test, expect } from "@playwright/test";
import { browserLogin, apiContext } from "./helpers/ui";
import { uid, promoteWithEvalRun } from "./helpers/auth";

/**
 * Browser-driven ModelsView + RoutingConsole journey. Every visible change
 * is produced by a real API call through the nginx proxy.
 */

function feature(name: string) {
  return { name, dtype: "float", transform: "identity", source_query_hash: "q" };
}

async function seedDraftModel(request: any, headers: Record<string, string>) {
  const modelResp = await request.post("/api/models", {
    headers,
    data: { name: `ui_m_${uid()}`, description: "ui journey" },
  });
  expect(modelResp.status()).toBe(201);
  const model = await modelResp.json();
  const v1Resp = await request.post(`/api/models/${model.id}/versions`, {
    headers,
    data: {
      feature_schema: [feature("a")],
      artifact_params: { bias: 0.1, weights: { a: 0.3 } },
    },
  });
  expect(v1Resp.status()).toBe(201);
  return { model, v1: await v1Resp.json() };
}

async function seedEvalRun(
  request: any,
  headers: Record<string, string>,
  modelId: string,
  versionId: string,
) {
  const start = await request.post(
    `/api/models/${modelId}/versions/${versionId}/runs`,
    {
      headers,
      data: { kind: "EVALUATION", dataset_ref: "ui-holdout" },
    },
  );
  const run = await start.json();
  await request.post(
    `/api/models/${modelId}/versions/${versionId}/runs/${run.id}/complete`,
    { headers, data: { status: "SUCCEEDED", metrics: { auc: 0.9 } } },
  );
}

test("registry renders; promote button visible only on DRAFT; promote flips status", async ({
  page,
  request,
}) => {
  const api = await apiContext(request);
  const { model, v1 } = await seedDraftModel(request, api.headers);
  await seedEvalRun(request, api.headers, model.id, v1.id);

  await browserLogin(page);
  await page.goto("/models");
  await expect(page.getByRole("heading", { level: 2, name: "Model registry" })).toBeVisible();

  // Initial render: the DRAFT version has a Promote button.
  await expect(page.getByTestId(`promote-${v1.id}`)).toBeVisible();

  const promoteCall = page.waitForResponse(
    (r) =>
      r.url().includes(`/api/models/${model.id}/versions/${v1.id}/promote`) &&
      r.request().method() === "POST",
  );
  const refreshModels = page.waitForResponse(
    (r) => r.url().endsWith("/api/models") && r.request().method() === "GET",
  );
  await page.getByTestId(`promote-${v1.id}`).click();
  const promoteResp = await promoteCall;
  expect(promoteResp.status()).toBe(200);
  await refreshModels;

  // After promote: the same version row now shows APPROVED and no promote button.
  await expect(page.getByTestId(`promote-${v1.id}`)).toBeHidden();
  await expect(
    page.getByRole("cell", { name: "APPROVED", exact: true }).first(),
  ).toBeVisible();
});

test("promote mismatch surfaces the feature_schema_mismatch error in the UI", async ({
  page,
  request,
}) => {
  const api = await apiContext(request);
  const { model, v1 } = await seedDraftModel(request, api.headers);
  // Promote v1 first so live_schema_hash pins (post-audit: requires a run).
  await promoteWithEvalRun(request, api.headers, model.id, v1.id);
  // Register v2 with a different schema.
  const v2Resp = await request.post(`/api/models/${model.id}/versions`, {
    headers: api.headers,
    data: {
      feature_schema: [feature("a"), feature("b_extra")],
      artifact_params: {},
    },
  });
  const v2 = await v2Resp.json();
  await seedEvalRun(request, api.headers, model.id, v2.id);

  await browserLogin(page);
  await page.goto("/models");
  await expect(page.getByTestId(`promote-${v2.id}`)).toBeVisible();

  const promoteCall = page.waitForResponse(
    (r) =>
      r.url().includes(`/api/models/${model.id}/versions/${v2.id}/promote`) &&
      r.request().method() === "POST",
  );
  await page.getByTestId(`promote-${v2.id}`).click();
  const resp = await promoteCall;
  expect(resp.status()).toBe(409);

  const errLocator = page.getByTestId("promote-error");
  await expect(errLocator).toBeVisible();
  await expect(errLocator).toContainText("does not match inference service");
  // The hash detail is surfaced so the operator can diagnose the drift.
  await expect(errLocator).toContainText("hash expected");
});

test("routing console slider persists a weight change", async ({ page, request }) => {
  const api = await apiContext(request);
  const { model, v1 } = await seedDraftModel(request, api.headers);
  await promoteWithEvalRun(request, api.headers, model.id, v1.id);
  const expResp = await request.post("/api/experiments", {
    headers: api.headers,
    data: {
      name: `ui_e_${uid()}`,
      model_a_version_id: v1.id,
      weight_a: 80,
    },
  });
  expect(expResp.status()).toBe(201);

  await browserLogin(page);
  await page.goto("/models");
  await expect(page.getByTestId("routing-console").first()).toBeVisible();

  const slider = page.locator('[data-testid="weight-a-slider"]').first();
  const routingUpdate = page.waitForResponse(
    (r) => r.url().includes("/routing") && r.request().method() === "POST",
  );
  // Adjust to 60 and fire the change event the component listens on.
  await slider.fill("60");
  await slider.dispatchEvent("change");
  const resp = await routingUpdate;
  expect(resp.status()).toBe(200);
  const body = await resp.json();
  expect(body.weight_a).toBe(60);
  expect(body.weight_b).toBe(40);
});

test("rollback confirmation dialog records a reason and disables the experiment", async ({
  page,
  request,
}) => {
  const api = await apiContext(request);
  const { model, v1 } = await seedDraftModel(request, api.headers);
  await promoteWithEvalRun(request, api.headers, model.id, v1.id);
  await request.post("/api/experiments", {
    headers: api.headers,
    data: {
      name: `ui_rb_${uid()}`,
      model_a_version_id: v1.id,
      weight_a: 70,
    },
  });

  await browserLogin(page);
  await page.goto("/models");

  await page.getByTestId("open-rollback").first().click();
  await expect(page.getByTestId("rollback-confirm")).toBeVisible();

  await page.getByTestId("rollback-reason").fill("browser journey incident drill");
  const rbCall = page.waitForResponse(
    (r) => r.url().endsWith("/rollback") && r.request().method() === "POST",
  );
  await page.getByTestId("rollback-submit").click();
  const resp = await rbCall;
  expect(resp.status()).toBe(200);
  const body = await resp.json();
  expect(body.weight_a).toBe(100);
  expect(body.ingest_enabled).toBe(false);
  expect(body.apply_enabled).toBe(false);
});
