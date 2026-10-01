import { expect, test } from "@playwright/test";

test.describe("Atlas login journey", () => {
  test("unauthenticated protected navigation reaches the real login route and preserves destination", async ({
    page
  }) => {
    await page.goto("/portal/requests");

    await expect(page).toHaveURL(/\/login\?next=%2Fportal%2Frequests$/);

    await expect(page.getByRole("heading", { name: "Welcome back" })).toBeVisible();

    await expect(page.getByLabel("Username")).toBeVisible();

    await expect(page.getByLabel("Password")).toBeVisible();

    await expect(page.getByRole("button", { name: "Sign in" })).toBeVisible();
  });

  test("login form rejects an empty browser submission before any authentication request", async ({
    page
  }) => {
    await page.goto("/login");

    await page.getByRole("button", { name: "Sign in" }).click();

    await expect(page.locator('p.auth-error[role="alert"]')).toHaveText(
      "Enter your username and password."
    );

    await expect(page).toHaveURL(/\/login$/);
  });
});

test("login survives reload and explicit sign-out cannot restore it", async ({ page }) => {
  await page.goto("/login");
  await page.getByLabel("Username").fill("atlas-e2e-user");
  await page.getByLabel("Password").fill("atlas-e2e-password");
  await page.getByRole("button", { name: "Sign in" }).click();
  await expect(page).toHaveURL(/\/portal$/);
  await page.goto("/portal/requests");
  await expect(page.getByRole("heading", { name: "Requests", exact: true })).toBeVisible();
  await page.reload();
  await expect(page.getByRole("heading", { name: "Requests", exact: true })).toBeVisible();
  await expect(page).toHaveURL(/\/portal\/requests$/);
  await page.getByRole("button", { name: /Atlas E2E User/ }).click();
  await page.getByRole("menuitem", { name: "Sign out" }).click();
  await expect(page).toHaveURL(/\/login(?:\?|$)/);
  await page.goto("/portal/requests");
  await expect(page).toHaveURL(/\/login\?next=%2Fportal%2Frequests$/);
});
