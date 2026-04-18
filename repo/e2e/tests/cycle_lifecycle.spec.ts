import { test, expect } from "@playwright/test";
import { login, createUser, uid } from "./helpers/auth";

/**
 * Drives the evaluation cycle state machine end-to-end through the real
 * nginx → api → db stack:
 *   NOT_STARTED → IN_PROGRESS → SUBMITTED → RETURNED_FOR_REVISION →
 *   IN_PROGRESS → SUBMITTED → ARCHIVED
 */

test("evaluation cycle full lifecycle", async ({ request }) => {
  const admin = await login(request);

  // Create template
  const tplResp = await request.post("/api/templates", {
    headers: admin.authHeaders,
    data: {
      name: `tpl_${uid()}`,
      items: [
        { key: "q1", label: "Q1", weight: 1.0, required: true, missing_strategy: "ZERO_FILL" },
        { key: "q2", label: "Q2", weight: 2.0, required: true, missing_strategy: "ZERO_FILL" },
      ],
    },
  });
  expect(tplResp.status()).toBe(201);
  const tpl = await tplResp.json();

  // Create cycle
  const deadline = new Date(Date.now() + 1000 * 60 * 60 * 24 * 60).toISOString();
  const cycleResp = await request.post("/api/cycles", {
    headers: admin.authHeaders,
    data: {
      name: `cycle_${uid()}`,
      starts_on: new Date().toISOString().slice(0, 10),
      ends_on: new Date(Date.now() + 1000 * 60 * 60 * 24 * 90).toISOString().slice(0, 10),
      deadline_at: deadline,
      timezone: "UTC",
      makeup_enabled: false,
      makeup_business_days: 5,
      holidays: [],
      template_version_id: tpl.latest_version_id,
    },
  });
  expect(cycleResp.status()).toBe(201);
  const cycle = await cycleResp.json();

  // Seed evaluator and reviewer
  const evaluator = await createUser(request, admin.authHeaders, ["Evaluator"], "eval");
  const reviewer = await createUser(request, admin.authHeaders, ["Reviewer"], "rev");

  // Assign evaluator
  const assignResp = await request.post(
    `/api/cycles/${cycle.id}/assignments`,
    {
      headers: admin.authHeaders,
      data: { evaluator_user_id: evaluator.id, reviewer_user_id: reviewer.id },
    },
  );
  expect(assignResp.status()).toBe(201);
  const assignment = await assignResp.json();
  expect(assignment.state).toBe("NOT_STARTED");
  expect(assignment.late_flag).toBe(false);

  // Evaluator logs in and saves a draft (→ IN_PROGRESS)
  const evalAuth = await login(request, evaluator.username, evaluator.password);
  const saveResp = await request.post(
    `/api/assignments/${assignment.id}/save`,
    {
      headers: evalAuth.authHeaders,
      data: { values: { q1: 7, q2: 9 } },
    },
  );
  expect(saveResp.status()).toBe(200);
  const afterSave = await saveResp.json();
  expect(afterSave.state).toBe("IN_PROGRESS");

  // Evaluator submits (→ SUBMITTED)
  const submitResp = await request.post(
    `/api/assignments/${assignment.id}/submit`,
    {
      headers: evalAuth.authHeaders,
      data: { values: { q1: 7, q2: 9 } },
    },
  );
  expect(submitResp.status()).toBe(200);
  const afterSubmit = await submitResp.json();
  expect(afterSubmit.state).toBe("SUBMITTED");
  expect(afterSubmit.submitted_at).not.toBeNull();
  expect(afterSubmit.late_flag).toBe(false);

  // Reviewer logs in and returns for revision (→ RETURNED_FOR_REVISION)
  const revAuth = await login(request, reviewer.username, reviewer.password);
  const returnResp = await request.post(
    `/api/assignments/${assignment.id}/return`,
    {
      headers: revAuth.authHeaders,
      data: { reason: "please reconsider q2" },
    },
  );
  expect(returnResp.status()).toBe(200);
  const afterReturn = await returnResp.json();
  expect(afterReturn.state).toBe("RETURNED_FOR_REVISION");
  expect(afterReturn.returned_reason).toBe("please reconsider q2");

  // Evaluator re-saves (→ IN_PROGRESS) and resubmits (→ SUBMITTED)
  await request.post(`/api/assignments/${assignment.id}/save`, {
    headers: evalAuth.authHeaders,
    data: { values: { q1: 7, q2: 8 } },
  });
  const reSubmitResp = await request.post(
    `/api/assignments/${assignment.id}/submit`,
    {
      headers: evalAuth.authHeaders,
      data: { values: { q1: 7, q2: 8 } },
    },
  );
  expect(reSubmitResp.status()).toBe(200);
  expect((await reSubmitResp.json()).state).toBe("SUBMITTED");

  // Reviewer approves (→ ARCHIVED)
  const approveResp = await request.post(
    `/api/assignments/${assignment.id}/approve`,
    { headers: revAuth.authHeaders },
  );
  expect(approveResp.status()).toBe(200);
  const approved = await approveResp.json();
  expect(approved.state).toBe("ARCHIVED");
  expect(approved.archived_at).not.toBeNull();

  // ARCHIVED is terminal — further state changes rejected
  const bad = await request.post(
    `/api/assignments/${assignment.id}/return`,
    { headers: revAuth.authHeaders, data: { reason: "too late" } },
  );
  expect(bad.status()).toBe(409);
  expect((await bad.json()).error).toBe("invalid_transition");
});

test("cross-evaluator submit is rejected with not_your_assignment", async ({ request }) => {
  const admin = await login(request);
  const tpl = await (
    await request.post("/api/templates", {
      headers: admin.authHeaders,
      data: {
        name: `tpl_${uid()}`,
        items: [{ key: "q", label: "Q", weight: 1, required: true, missing_strategy: "ZERO_FILL" }],
      },
    })
  ).json();
  const cycle = await (
    await request.post("/api/cycles", {
      headers: admin.authHeaders,
      data: {
        name: `cycle_${uid()}`,
        starts_on: new Date().toISOString().slice(0, 10),
        ends_on: new Date(Date.now() + 1000 * 60 * 60 * 24 * 90).toISOString().slice(0, 10),
        deadline_at: new Date(Date.now() + 1000 * 60 * 60 * 24 * 60).toISOString(),
        timezone: "UTC", makeup_enabled: false, makeup_business_days: 5, holidays: [],
        template_version_id: tpl.latest_version_id,
      },
    })
  ).json();
  const owner = await createUser(request, admin.authHeaders, ["Evaluator"], "owner");
  const stranger = await createUser(request, admin.authHeaders, ["Evaluator"], "stranger");
  const assignment = await (
    await request.post(`/api/cycles/${cycle.id}/assignments`, {
      headers: admin.authHeaders,
      data: { evaluator_user_id: owner.id },
    })
  ).json();

  const strangerAuth = await login(request, stranger.username, stranger.password);
  const resp = await request.post(`/api/assignments/${assignment.id}/save`, {
    headers: strangerAuth.authHeaders,
    data: { values: { q: 1 } },
  });
  expect(resp.status()).toBe(403);
  expect((await resp.json()).error).toBe("not_your_assignment");
});

test("late submit without makeup is rejected with deadline_passed_no_makeup", async ({
  request,
}) => {
  const admin = await login(request);
  const tpl = await (
    await request.post("/api/templates", {
      headers: admin.authHeaders,
      data: {
        name: `tpl_${uid()}`,
        items: [{ key: "q", label: "Q", weight: 1, required: true, missing_strategy: "ZERO_FILL" }],
      },
    })
  ).json();
  // Deadline in the past, no makeup.
  const past = new Date(Date.now() - 1000 * 60 * 60 * 24).toISOString();
  const cycle = await (
    await request.post("/api/cycles", {
      headers: admin.authHeaders,
      data: {
        name: `late_${uid()}`,
        starts_on: new Date(Date.now() - 1000 * 60 * 60 * 24 * 30).toISOString().slice(0, 10),
        ends_on: new Date().toISOString().slice(0, 10),
        deadline_at: past,
        timezone: "UTC", makeup_enabled: false, makeup_business_days: 5, holidays: [],
        template_version_id: tpl.latest_version_id,
      },
    })
  ).json();
  const evaluator = await createUser(request, admin.authHeaders, ["Evaluator"], "lateval");
  await request.post(`/api/cycles/${cycle.id}/assignments`, {
    headers: admin.authHeaders,
    data: { evaluator_user_id: evaluator.id },
  });
  const evalAuth = await login(request, evaluator.username, evaluator.password);
  const mine = await (
    await request.get("/api/assignments/mine/active", { headers: evalAuth.authHeaders })
  ).json();
  const aid = mine[0].id;
  await request.post(`/api/assignments/${aid}/save`, {
    headers: evalAuth.authHeaders,
    data: { values: { q: 1 } },
  });
  const submit = await request.post(`/api/assignments/${aid}/submit`, {
    headers: evalAuth.authHeaders,
    data: { values: { q: 1 } },
  });
  expect(submit.status()).toBe(409);
  expect((await submit.json()).error).toBe("deadline_passed_no_makeup");
});
