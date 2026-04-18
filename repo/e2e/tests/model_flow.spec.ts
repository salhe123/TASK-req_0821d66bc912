import { test, expect } from "@playwright/test";
import { login, uid, promoteWithEvalRun } from "./helpers/auth";

/**
 * Model registry + routing flow through the full stack:
 *   register model → register v1 (DRAFT) → promote (pins live schema) →
 *   register v2 with mismatched schema → promote blocked (409) →
 *   register v3 matching → promote succeeds →
 *   create experiment v1 vs v3 @ 50/50 → predict assigns sticky arm →
 *   change routing to 70/30 (audited) → manual rollback flips to (100,0),
 *   disables ingest+apply, records a rollback_event.
 */

function feature(name: string) {
  return { name, dtype: "float", transform: "identity", source_query_hash: "q" };
}

test("model register, promote (pin + mismatch), experiment routing, rollback", async ({
  request,
}) => {
  const admin = await login(request);

  const modelResp = await request.post("/api/models", {
    headers: admin.authHeaders,
    data: { name: `m_${uid()}`, description: "recommender" },
  });
  expect(modelResp.status()).toBe(201);
  const model = await modelResp.json();
  expect(model.live_schema_hash).toBeNull();

  // Register v1
  const v1 = await (
    await request.post(`/api/models/${model.id}/versions`, {
      headers: admin.authHeaders,
      data: {
        feature_schema: [feature("a"), feature("b")],
        artifact_params: { bias: 0.0, weights: { a: 0.5, b: 0.5 } },
      },
    })
  ).json();
  expect(v1.status).toBe("DRAFT");
  expect(v1.feature_schema_hash).toHaveLength(64);

  // Promote v1 — pins live_schema_hash (post-audit: requires a successful eval run)
  const promoteV1 = await promoteWithEvalRun(request, admin.authHeaders, model.id, v1.id);
  expect(promoteV1.status()).toBe(200);
  expect((await promoteV1.json()).status).toBe("APPROVED");
  const listed = await (await request.get("/api/models", { headers: admin.authHeaders })).json();
  const self = listed.items.find((m: any) => m.id === model.id);
  expect(self.live_schema_hash).toBe(v1.feature_schema_hash);

  // Register v2 with a different schema (add feature "c"), promote blocked
  const v2 = await (
    await request.post(`/api/models/${model.id}/versions`, {
      headers: admin.authHeaders,
      data: {
        feature_schema: [feature("a"), feature("b"), feature("c")],
        artifact_params: { bias: 0.0, weights: { a: 0.5, b: 0.5 } },
      },
    })
  ).json();
  const mismatchResp = await promoteWithEvalRun(request, admin.authHeaders, model.id, v2.id);
  expect(mismatchResp.status()).toBe(409);
  const mismatch = await mismatchResp.json();
  expect(mismatch.error).toBe("feature_schema_mismatch");
  expect(mismatch.details.extra_in_got).toContain("c");

  // Register v3 with matching schema → promote succeeds
  const v3 = await (
    await request.post(`/api/models/${model.id}/versions`, {
      headers: admin.authHeaders,
      data: {
        feature_schema: [feature("a"), feature("b")],
        artifact_params: { bias: 1.5, weights: { a: 0.2, b: 0.1 } },
      },
    })
  ).json();
  const promoteV3 = await promoteWithEvalRun(request, admin.authHeaders, model.id, v3.id);
  expect(promoteV3.status()).toBe(200);

  // Create experiment v1 (A) vs v3 (B) @ 50/50
  const expResp = await request.post("/api/experiments", {
    headers: admin.authHeaders,
    data: {
      name: `e_${uid()}`,
      model_a_version_id: v1.id,
      model_b_version_id: v3.id,
      weight_a: 50,
    },
  });
  expect(expResp.status()).toBe(201);
  const exp = await expResp.json();
  expect(exp.weight_a).toBe(50);
  expect(exp.weight_b).toBe(50);

  // Predict — deterministic across two calls for same subject
  const r1 = await (
    await request.post("/api/inference/predict", {
      headers: admin.authHeaders,
      data: { experiment_id: exp.id, subject_key: "subject-42", features: { a: 0.3, b: 0.1 } },
    })
  ).json();
  const r2 = await (
    await request.post("/api/inference/predict", {
      headers: admin.authHeaders,
      data: { experiment_id: exp.id, subject_key: "subject-42", features: { a: 0.3, b: 0.1 } },
    })
  ).json();
  expect(r1.arm).toBe(r2.arm);
  expect(r1.model_version_id).toBe(r2.model_version_id);
  expect(r1.score).toBe(r2.score);

  // Routing update — audited and weights persist
  const routingResp = await request.post(
    `/api/experiments/${exp.id}/routing`,
    { headers: admin.authHeaders, data: { weight_a: 70 } },
  );
  expect(routingResp.status()).toBe(200);
  const routing = await routingResp.json();
  expect(routing.weight_a).toBe(70);
  expect(routing.weight_b).toBe(30);

  // Rollback flips to (100,0) and disables toggles
  const rollbackResp = await request.post(
    `/api/experiments/${exp.id}/rollback`,
    { headers: admin.authHeaders, data: { trigger: "manual", reason: "incident drill" } },
  );
  expect(rollbackResp.status()).toBe(200);
  const afterRollback = await rollbackResp.json();
  expect(afterRollback.weight_a).toBe(100);
  expect(afterRollback.weight_b).toBe(0);
  expect(afterRollback.ingest_enabled).toBe(false);
  expect(afterRollback.apply_enabled).toBe(false);

  // Predict after rollback is blocked because apply is off
  const blocked = await request.post("/api/inference/predict", {
    headers: admin.authHeaders,
    data: { experiment_id: exp.id, subject_key: "x", features: { a: 0.1, b: 0.1 } },
  });
  expect(blocked.status()).toBe(409);
  expect((await blocked.json()).error).toBe("experiment_apply_disabled");

  // Re-enable apply and predict routes all subjects to arm A
  await request.post(`/api/experiments/${exp.id}/toggle`, {
    headers: admin.authHeaders,
    data: { apply_enabled: true },
  });
  for (const s of ["s1", "s2", "s3", "s4"]) {
    const r = await (
      await request.post("/api/inference/predict", {
        headers: admin.authHeaders,
        data: { experiment_id: exp.id, subject_key: s, features: { a: 0.2, b: 0.2 } },
      })
    ).json();
    expect(r.arm).toBe("A");
  }
});

test("rollback with invalid trigger is rejected", async ({ request }) => {
  const admin = await login(request);
  const model = await (
    await request.post("/api/models", {
      headers: admin.authHeaders,
      data: { name: `m_${uid()}` },
    })
  ).json();
  const v1 = await (
    await request.post(`/api/models/${model.id}/versions`, {
      headers: admin.authHeaders,
      data: { feature_schema: [feature("a")], artifact_params: {} },
    })
  ).json();
  await promoteWithEvalRun(request, admin.authHeaders, model.id, v1.id);
  const exp = await (
    await request.post("/api/experiments", {
      headers: admin.authHeaders,
      data: {
        name: `e_${uid()}`,
        model_a_version_id: v1.id,
        weight_a: 100,
      },
    })
  ).json();
  const bad = await request.post(`/api/experiments/${exp.id}/rollback`, {
    headers: admin.authHeaders,
    data: { trigger: "teleport" },
  });
  expect(bad.status()).toBe(409);
  expect((await bad.json()).error).toBe("invalid_trigger");
});
