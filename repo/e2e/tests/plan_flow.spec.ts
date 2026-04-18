import { test, expect } from "@playwright/test";
import { login, createUser, uid } from "./helpers/auth";

/**
 * Plan flow through the full stack:
 *   create plan v1 → publish v2 with diffs → compare → signed export →
 *   issue share link → open by Plan Owner → revoke → open fails →
 *   rollback to v1 → new v3 with v1 contents
 */

test("plan create, diff, export, share, revoke, rollback", async ({ request }) => {
  const admin = await login(request);

  const planName = `plan_${uid()}`;
  const v1Resp = await request.post("/api/plans", {
    headers: admin.authHeaders,
    data: {
      name: planName,
      description: "governance BOM",
      note: "initial",
      lines: [
        { line_identity_key: "K1", part_number: "P-A", quantity: 10, unit: "ea", notes: "n1" },
        { line_identity_key: "K2", part_number: "P-B", quantity: 2, unit: "ea", tags: ["critical"] },
      ],
    },
  });
  expect(v1Resp.status()).toBe(201);
  const plan = await v1Resp.json();
  const v1Id = plan.head_version_id;

  // Publish v2 with a rename + quantity change + new line
  const v2Resp = await request.post(`/api/plans/${plan.id}/versions`, {
    headers: admin.authHeaders,
    data: {
      parent_version_id: v1Id,
      note: "adjust and add",
      lines: [
        { line_identity_key: "K1", part_number: "P-A-RENAMED", quantity: 10 },
        { line_identity_key: "K2", part_number: "P-B", quantity: 3, tags: ["critical"] },
        { line_identity_key: "K3", part_number: "P-NEW", quantity: 1 },
      ],
    },
  });
  expect(v2Resp.status()).toBe(201);
  const v2 = await v2Resp.json();

  // Compare v2 vs v1
  const diffResp = await request.get(`/api/plans/${plan.id}/versions/${v2.id}/diff`);
  expect(diffResp.status()).toBe(200);
  const diff = await diffResp.json();
  const byKey: Record<string, any> = {};
  for (const e of diff.entries) byKey[e.line_identity_key] = e;
  expect(byKey.K1.changes).toContain("PART_CHANGED");
  expect(byKey.K2.changes).toContain("QUANTITY_CHANGED");
  expect(byKey.K3.changes).toEqual(["ADDED"]);

  // Signed export bundle downloads and looks zip-ish
  const exportResp = await request.get(
    `/api/plans/${plan.id}/versions/${v2.id}/export`,
  );
  expect(exportResp.status()).toBe(200);
  expect(exportResp.headers()["content-type"]).toContain("application/zip");
  const bodyBytes = await exportResp.body();
  expect(bodyBytes.length).toBeGreaterThan(100);
  // Zip file magic: PK\x03\x04
  expect(bodyBytes[0]).toBe(0x50);
  expect(bodyBytes[1]).toBe(0x4b);

  // Create a Plan Owner user and issue a share link for v2
  const owner = await createUser(request, admin.authHeaders, ["Plan Owner"], "po");
  const shareResp = await request.post(
    `/api/plans/${plan.id}/versions/${v2.id}/share`,
    {
      headers: admin.authHeaders,
      data: { role: "Plan Owner", expires_in_days: 3 },
    },
  );
  expect(shareResp.status()).toBe(201);
  const share = await shareResp.json();
  expect(share.token).toBeTruthy();
  expect(share.revoked).toBe(false);

  // Plan owner resolves
  const ownerAuth = await login(request, owner.username, owner.password);
  const open = await request.get(`/api/share/${share.token}`, {
    headers: ownerAuth.authHeaders,
  });
  expect(open.status()).toBe(200);
  const resolved = await open.json();
  expect(resolved.role).toBe("Plan Owner");
  expect(resolved.version.id).toBe(v2.id);
  expect(resolved.version.lines.length).toBe(3);

  // Revoke → further resolution fails with share_link_invalid
  const rev = await request.delete(`/api/plans/share-links/${share.id}`, {
    headers: admin.authHeaders,
  });
  expect(rev.status()).toBe(200);
  expect((await rev.json()).revoked).toBe(true);
  const afterRev = await request.get(`/api/share/${share.token}`, {
    headers: ownerAuth.authHeaders,
  });
  expect(afterRev.status()).toBe(403);
  expect((await afterRev.json()).error).toBe("share_link_invalid");

  // Rollback to v1 creates a new v3 with v1's lines
  const rbResp = await request.post(
    `/api/plans/${plan.id}/versions/${v1Id}/rollback`,
    {
      headers: admin.authHeaders,
      data: { note: "revert to initial" },
    },
  );
  expect(rbResp.status()).toBe(201);
  const newVersion = await rbResp.json();
  expect(newVersion.version_no).toBe(3);
  expect(newVersion.parent_version_id).toBe(v2.id);

  // The rolled-back version contains v1's BOM
  const detail = await request.get(
    `/api/plans/${plan.id}/versions/${newVersion.id}`,
  );
  const body = await detail.json();
  expect(body.lines.length).toBe(2);
  const keys = body.lines.map((l: any) => l.line_identity_key).sort();
  expect(keys).toEqual(["K1", "K2"]);
  const k1 = body.lines.find((l: any) => l.line_identity_key === "K1");
  expect(k1.part_number).toBe("P-A");
  expect(k1.quantity).toBe("10");
});

test("share-link open requires build_plan:view_shared permission", async ({ request }) => {
  const admin = await login(request);
  const planResp = await request.post("/api/plans", {
    headers: admin.authHeaders,
    data: {
      name: `plan_${uid()}`,
      lines: [{ line_identity_key: "K", part_number: "P", quantity: 1 }],
    },
  });
  const plan = await planResp.json();
  const share = await (
    await request.post(
      `/api/plans/${plan.id}/versions/${plan.head_version_id}/share`,
      {
        headers: admin.authHeaders,
        data: { role: "Plan Owner", expires_in_days: 1 },
      },
    )
  ).json();

  // An Evaluator has no view_shared permission → must 403 even with valid token
  const evaluator = await createUser(request, admin.authHeaders, ["Evaluator"], "nosh");
  const evalAuth = await login(request, evaluator.username, evaluator.password);
  const r = await request.get(`/api/share/${share.token}`, {
    headers: evalAuth.authHeaders,
  });
  expect(r.status()).toBe(403);
  expect((await r.json()).error).toBe("permission_denied");
});

test("plan duplicate line identity keys rejected", async ({ request }) => {
  const admin = await login(request);
  const resp = await request.post("/api/plans", {
    headers: admin.authHeaders,
    data: {
      name: `dup_${uid()}`,
      lines: [
        { line_identity_key: "K", part_number: "A", quantity: 1 },
        { line_identity_key: "K", part_number: "B", quantity: 1 },
      ],
    },
  });
  expect(resp.status()).toBe(409);
  expect((await resp.json()).error).toBe("duplicate_line_identity");
});
