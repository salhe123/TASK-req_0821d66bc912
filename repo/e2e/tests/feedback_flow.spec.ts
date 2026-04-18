import { test, expect } from "@playwright/test";
import { login, uid, promoteWithEvalRun } from "./helpers/auth";

/**
 * Feedback flow — end-to-end through the full stack:
 *   LIKE/NOT_INTERESTED bump per-arm signals → visible via /signals
 *   BLOCK persists in subject_blocks regardless of toggle state
 *   ingest_enabled=false records event but leaves signal unchanged
 *   rate limit 60/min → 429 rate_limited
 *   rollback preserves prior events + isolates arms
 */

function feature(name: string) {
  return { name, dtype: "float", transform: "identity", source_query_hash: "q" };
}

async function bootstrapExperiment(request: any, authHeaders: Record<string, string>) {
  const model = await (
    await request.post("/api/models", {
      headers: authHeaders,
      data: { name: `fb_${uid()}` },
    })
  ).json();
  const v1 = await (
    await request.post(`/api/models/${model.id}/versions`, {
      headers: authHeaders,
      data: {
        feature_schema: [feature("a")],
        artifact_params: { bias: 0, weights: { a: 1 } },
      },
    })
  ).json();
  await promoteWithEvalRun(request, authHeaders, model.id, v1.id);
  const v2 = await (
    await request.post(`/api/models/${model.id}/versions`, {
      headers: authHeaders,
      data: {
        feature_schema: [feature("a")],
        artifact_params: { bias: 1, weights: { a: 1 } },
      },
    })
  ).json();
  await promoteWithEvalRun(request, authHeaders, model.id, v2.id);
  const exp = await (
    await request.post("/api/experiments", {
      headers: authHeaders,
      data: {
        name: `fe_${uid()}`,
        model_a_version_id: v1.id,
        model_b_version_id: v2.id,
        weight_a: 50,
      },
    })
  ).json();
  return { exp, v1, v2 };
}

test("LIKE and NOT_INTERESTED bump per-arm signals, visible via /signals", async ({
  request,
}) => {
  const admin = await login(request);
  const { exp, v1 } = await bootstrapExperiment(request, admin.authHeaders);
  const target = `tgt_${uid()}`;

  // Emit 3 LIKEs and 1 NOT_INTERESTED on arm A
  for (let i = 0; i < 3; i++) {
    const r = await request.post("/api/feedback", {
      headers: admin.authHeaders,
      data: {
        experiment_id: exp.id,
        subject_key: `subj-${i}`,
        target_id: target,
        kind: "LIKE",
        arm: "A",
        model_version_id: v1.id,
      },
    });
    expect(r.status()).toBe(201);
    expect((await r.json()).signal_updated).toBe(true);
  }
  await request.post("/api/feedback", {
    headers: admin.authHeaders,
    data: {
      experiment_id: exp.id,
      subject_key: "extra",
      target_id: target,
      kind: "NOT_INTERESTED",
      arm: "A",
      model_version_id: v1.id,
    },
  });

  const signals = await (
    await request.get(`/api/feedback/signals/${exp.id}`, { headers: admin.authHeaders })
  ).json();
  const a = signals.items.find(
    (s: any) => s.arm === "A" && s.target_id === target,
  );
  expect(a).toBeTruthy();
  expect(a.like_count).toBe(3);
  expect(a.not_interested_count).toBe(1);
});

test("BLOCK persists in subject_blocks regardless of ingest toggle", async ({
  request,
}) => {
  const admin = await login(request);
  const { exp, v1 } = await bootstrapExperiment(request, admin.authHeaders);

  // Disable ingest
  await request.post(`/api/experiments/${exp.id}/toggle`, {
    headers: admin.authHeaders,
    data: { ingest_enabled: false },
  });

  const subject = `blk_${uid()}`;
  await request.post("/api/feedback", {
    headers: admin.authHeaders,
    data: {
      experiment_id: exp.id,
      subject_key: subject,
      target_id: "item-x",
      kind: "BLOCK",
      arm: "A",
      model_version_id: v1.id,
    },
  });

  const blocks = await (
    await request.get(`/api/feedback/blocks/${subject}`, {
      headers: admin.authHeaders,
    })
  ).json();
  expect(blocks.subject_key).toBe(subject);
  expect(blocks.items.map((i: any) => i.target_id)).toContain("item-x");
});

test("ingest_enabled=false records event but signal_updated=false", async ({
  request,
}) => {
  const admin = await login(request);
  const { exp, v1 } = await bootstrapExperiment(request, admin.authHeaders);
  await request.post(`/api/experiments/${exp.id}/toggle`, {
    headers: admin.authHeaders,
    data: { ingest_enabled: false },
  });

  const r = await request.post("/api/feedback", {
    headers: admin.authHeaders,
    data: {
      experiment_id: exp.id,
      subject_key: "no-signal-subject",
      target_id: "tgt",
      kind: "LIKE",
      arm: "A",
      model_version_id: v1.id,
    },
  });
  expect(r.status()).toBe(201);
  expect((await r.json()).signal_updated).toBe(false);

  const sigs = await (
    await request.get(`/api/feedback/signals/${exp.id}`, {
      headers: admin.authHeaders,
    })
  ).json();
  expect(sigs.items.length).toBe(0);
});

test("rate limit returns 429 rate_limited on 61st event", async ({ request }) => {
  const admin = await login(request);
  const { exp, v1 } = await bootstrapExperiment(request, admin.authHeaders);
  const subject = `rl_${uid()}`;

  for (let i = 0; i < 60; i++) {
    const r = await request.post("/api/feedback", {
      headers: admin.authHeaders,
      data: {
        experiment_id: exp.id,
        subject_key: subject,
        target_id: `t-${i}`,
        kind: "LIKE",
        arm: "A",
        model_version_id: v1.id,
      },
    });
    expect(r.status()).toBe(201);
  }
  const over = await request.post("/api/feedback", {
    headers: admin.authHeaders,
    data: {
      experiment_id: exp.id,
      subject_key: subject,
      target_id: "over",
      kind: "LIKE",
      arm: "A",
      model_version_id: v1.id,
    },
  });
  expect(over.status()).toBe(429);
  expect((await over.json()).error).toBe("rate_limited");
});

test("rollback preserves events and keeps per-arm signals isolated", async ({
  request,
}) => {
  const admin = await login(request);
  const { exp, v1, v2 } = await bootstrapExperiment(request, admin.authHeaders);
  const target = `iso_${uid()}`;

  for (const i of [0, 1]) {
    await request.post("/api/feedback", {
      headers: admin.authHeaders,
      data: {
        experiment_id: exp.id,
        subject_key: `sa-${i}`,
        target_id: target,
        kind: "LIKE",
        arm: "A",
        model_version_id: v1.id,
      },
    });
    await request.post("/api/feedback", {
      headers: admin.authHeaders,
      data: {
        experiment_id: exp.id,
        subject_key: `sb-${i}`,
        target_id: target,
        kind: "LIKE",
        arm: "B",
        model_version_id: v2.id,
      },
    });
  }
  const before = await (
    await request.get(`/api/feedback/signals/${exp.id}`, {
      headers: admin.authHeaders,
    })
  ).json();
  const beforeByArm: Record<string, number> = {};
  for (const s of before.items) {
    if (s.target_id === target) beforeByArm[s.arm] = s.like_count;
  }
  expect(beforeByArm).toEqual({ A: 2, B: 2 });

  // Rollback — weights → (100,0), ingest+apply flipped off; events preserved
  const rb = await request.post(`/api/experiments/${exp.id}/rollback`, {
    headers: admin.authHeaders,
    data: { trigger: "manual", reason: "isolation" },
  });
  expect(rb.status()).toBe(200);

  const after = await (
    await request.get(`/api/feedback/signals/${exp.id}`, {
      headers: admin.authHeaders,
    })
  ).json();
  const afterByArm: Record<string, number> = {};
  for (const s of after.items) {
    if (s.target_id === target) afterByArm[s.arm] = s.like_count;
  }
  expect(afterByArm).toEqual({ A: 2, B: 2 });
});

test("invalid feedback kind is rejected with validation_error", async ({
  request,
}) => {
  const admin = await login(request);
  const { exp, v1 } = await bootstrapExperiment(request, admin.authHeaders);
  const r = await request.post("/api/feedback", {
    headers: admin.authHeaders,
    data: {
      experiment_id: exp.id,
      subject_key: "s",
      target_id: "t",
      kind: "MAYBE",
      arm: "A",
      model_version_id: v1.id,
    },
  });
  expect(r.status()).toBe(422);
  expect((await r.json()).error).toBe("validation_error");
});
