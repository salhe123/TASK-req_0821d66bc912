import { Page, expect, APIRequestContext } from "@playwright/test";
import { ADMIN_USER, ADMIN_PASS, login as apiLogin } from "./auth";

/**
 * Browser login that waits for the SPA's post-login redirect and for
 * `/api/auth/me` to complete so the Pinia session store is populated.
 * Returns nothing — the page is ready for further navigation.
 */
export async function browserLogin(
  page: Page,
  username: string = ADMIN_USER,
  password: string = ADMIN_PASS,
): Promise<void> {
  await page.goto("/login");
  await page.getByTestId("username").fill(username);
  await page.getByTestId("password").fill(password);
  // Wait for both the login POST and the /me GET that the SPA fires on success.
  const loginResp = page.waitForResponse(
    (r) => r.url().endsWith("/api/auth/login") && r.request().method() === "POST",
  );
  const meResp = page.waitForResponse(
    (r) => r.url().endsWith("/api/auth/me") && r.request().method() === "GET",
  );
  await page.getByTestId("login-submit").click();
  const loginResponse = await loginResp;
  expect(loginResponse.status()).toBe(200);
  await meResp;
  await page.waitForURL(/\/$/);
}

/**
 * Convenience: seed data via the real API while running browser-driven tests.
 * Every call here is a real network round-trip through the nginx proxy.
 */
export async function apiContext(request: APIRequestContext): Promise<{
  headers: Record<string, string>;
  userId: string;
  roles: string[];
}> {
  const { authHeaders, userId, roles } = await apiLogin(request);
  return { headers: authHeaders, userId, roles };
}
