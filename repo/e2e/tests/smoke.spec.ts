import { test, expect } from "@playwright/test";

// Post-Phase-1: unauthenticated visits to `/` are redirected to `/login`,
// so the smoke test validates the SPA served from nginx renders the login
// page and the api is reachable via the nginx proxy.

test("SPA renders at /login after guard redirect", async ({ page }) => {
  await page.goto("/");
  await expect(page).toHaveURL(/\/login/);
  await expect(page.getByRole("heading", { level: 2, name: "Sign in" })).toBeVisible();
  await expect(page.getByTestId("username")).toBeVisible();
  await expect(page.getByTestId("password")).toBeVisible();
  await expect(page.getByTestId("login-submit")).toBeVisible();
});

test("api health endpoint is reachable through the nginx proxy", async ({ request }) => {
  const res = await request.get("/api/health");
  expect(res.status()).toBe(200);
  const body = await res.json();
  expect(body).toEqual({ status: "ok" });
});
