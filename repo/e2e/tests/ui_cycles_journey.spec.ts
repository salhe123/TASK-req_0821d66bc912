import { test, expect } from "@playwright/test";
import { browserLogin, apiContext } from "./helpers/ui";
import { login, createUser, uid } from "./helpers/auth";

/**
 * CyclesView journey: for an evaluator, drive their assignment through multiple
 * state-machine states via the API, then open the page in the browser and verify
 * the timeline badge shows the correct state + next-action copy each time.
 *
 * The workflow transitions (save/submit/return/approve) are done through the API
 * because the view is read-only; the browser assertion is that the UI reflects
 * the backend truth correctly after each transition.
 */

async function seedCycleForEvaluator(
  request: any,
  adminHeaders: Record<string, string>,
) {
  const tpl = await (
    await request.post("/api/templates", {
      headers: adminHeaders,
      data: {
        name: `ui_tpl_${uid()}`,
        items: [
          {
            key: "q", label: "Q", weight: 1, required: true,
            missing_strategy: "ZERO_FILL",
          },
        ],
      },
    })
  ).json();
  const cycle = await (
    await request.post("/api/cycles", {
      headers: adminHeaders,
      data: {
        name: `ui_cycle_${uid()}`,
        starts_on: new Date().toISOString().slice(0, 10),
        ends_on: new Date(Date.now() + 1000 * 60 * 60 * 24 * 90).toISOString().slice(0, 10),
        deadline_at: new Date(Date.now() + 1000 * 60 * 60 * 24 * 60).toISOString(),
        timezone: "UTC", makeup_enabled: false, makeup_business_days: 5, holidays: [],
        template_version_id: tpl.latest_version_id,
      },
    })
  ).json();
  return { tpl, cycle };
}

test("timeline badge reflects assignment state transitions end-to-end", async ({
  page,
  request,
}) => {
  const admin = await apiContext(request);
  const { cycle } = await seedCycleForEvaluator(request, admin.headers);
  const evaluator = await createUser(request, admin.headers, ["Evaluator"], "uiev");
  const reviewer = await createUser(request, admin.headers, ["Reviewer"], "uirv");

  const assignResp = await request.post(
    `/api/cycles/${cycle.id}/assignments`,
    {
      headers: admin.headers,
      data: { evaluator_user_id: evaluator.id, reviewer_user_id: reviewer.id },
    },
  );
  expect(assignResp.status()).toBe(201);
  const assignment = await assignResp.json();

  // --- Browser: initially NOT_STARTED
  await browserLogin(page, evaluator.username, evaluator.password);
  await page.goto("/cycles");
  const myLoad = page.waitForResponse(
    (r) => r.url().endsWith("/api/assignments/mine/active") && r.request().method() === "GET",
  );
  await myLoad;
  await expect(page.getByTestId("timeline-NOT_STARTED")).toBeVisible();
  await expect(page.getByTestId("timeline-NOT_STARTED")).toHaveAttribute(
    "title",
    /Open and save/,
  );

  // --- Evaluator saves + submits via API; reload page; expect SUBMITTED
  const evalAuth = await login(request, evaluator.username, evaluator.password);
  await request.post(`/api/assignments/${assignment.id}/save`, {
    headers: evalAuth.authHeaders,
    data: { values: { q: 5 } },
  });
  await request.post(`/api/assignments/${assignment.id}/submit`, {
    headers: evalAuth.authHeaders,
    data: { values: { q: 5 } },
  });
  await page.reload();
  await expect(page.getByTestId("timeline-SUBMITTED")).toBeVisible();
  await expect(page.getByTestId("timeline-SUBMITTED")).toHaveAttribute(
    "title",
    /Awaiting reviewer/,
  );

  // --- Reviewer returns via API; reload; expect RETURNED_FOR_REVISION + reason row
  const revAuth = await login(request, reviewer.username, reviewer.password);
  await request.post(`/api/assignments/${assignment.id}/return`, {
    headers: revAuth.authHeaders,
    data: { reason: "reconsider q" },
  });
  await page.reload();
  await expect(page.getByTestId("timeline-RETURNED_FOR_REVISION")).toBeVisible();
  await expect(page.getByText("reconsider q")).toBeVisible();

  // --- Evaluator re-saves + resubmits; reviewer approves → ARCHIVED is terminal,
  //     so assignment leaves the "mine/active" list (which filters ARCHIVED out).
  await request.post(`/api/assignments/${assignment.id}/save`, {
    headers: evalAuth.authHeaders,
    data: { values: { q: 7 } },
  });
  await request.post(`/api/assignments/${assignment.id}/submit`, {
    headers: evalAuth.authHeaders,
    data: { values: { q: 7 } },
  });
  await request.post(`/api/assignments/${assignment.id}/approve`, {
    headers: revAuth.authHeaders,
  });
  await page.reload();
  // The evaluator's active list no longer shows this assignment
  await expect(page.getByText("No active assignments.")).toBeVisible();
});

test("evaluator without active assignments sees the empty state", async ({
  page,
  request,
}) => {
  const admin = await apiContext(request);
  const evaluator = await createUser(request, admin.headers, ["Evaluator"], "nocycle");

  await browserLogin(page, evaluator.username, evaluator.password);
  await page.goto("/cycles");
  await page.waitForResponse(
    (r) => r.url().endsWith("/api/assignments/mine/active") && r.request().method() === "GET",
  );
  await expect(page.getByText("No active assignments.")).toBeVisible();
});
