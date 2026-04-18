import { test, expect } from "@playwright/test";
import { ADMIN_USER, ADMIN_PASS } from "./helpers/auth";

/**
 * Browser-driven auth flow through the full stack:
 *   - login page → submit credentials → dashboard renders with readiness
 *   - logged-in nav exposes modules the admin's role grants
 *   - sign out clears the session and re-routes to /login
 *   - deep-link to /plans while unauthenticated redirects with ?next=
 */

test("admin can sign in via the UI and land on dashboard", async ({ page }) => {
  await page.goto("/login");
  await page.getByTestId("username").fill(ADMIN_USER);
  await page.getByTestId("password").fill(ADMIN_PASS);
  await page.getByTestId("login-submit").click();

  // After login the SPA routes to /
  await page.waitForURL(/\/$/);
  await expect(page.getByRole("heading", { level: 2, name: "Dashboard" })).toBeVisible();

  // Dashboard reads /api/health/ready via nginx proxy
  await expect(page.getByTestId("ready-status")).toHaveText(/ok|degraded/);
});

test("nav exposes modules after admin login and sign-out returns to /login", async ({
  page,
}) => {
  await page.goto("/login");
  await page.getByTestId("username").fill(ADMIN_USER);
  await page.getByTestId("password").fill(ADMIN_PASS);
  await page.getByTestId("login-submit").click();
  await page.waitForURL(/\/$/);

  for (const label of [
    "Dashboard",
    "Evaluation Cycles",
    "Build Plans",
    "Model Registry",
    "Feedback",
    "Administration",
  ]) {
    await expect(page.getByText(label, { exact: true }).first()).toBeVisible();
  }

  // Sign out → /login
  await page.getByTestId("sign-out").click();
  await page.waitForURL(/\/login/);
  await expect(page.getByRole("heading", { level: 2, name: "Sign in" })).toBeVisible();
});

test("deep-link redirect preserves intended path via next query", async ({ page }) => {
  await page.goto("/plans");
  await page.waitForURL(/\/login\?next=/);
  expect(page.url()).toContain("next=");
  expect(decodeURIComponent(page.url())).toContain("/plans");
});

test("invalid credentials surface the error envelope message", async ({ page }) => {
  await page.goto("/login");
  await page.getByTestId("username").fill("nobody");
  await page.getByTestId("password").fill("not-the-right-password");
  await page.getByTestId("login-submit").click();
  await expect(page.getByTestId("login-error")).toBeVisible();
  await expect(page.getByTestId("login-error")).toContainText(/invalid/i);
});
