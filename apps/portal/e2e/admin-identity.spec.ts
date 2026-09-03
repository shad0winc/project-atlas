import { expect, test, type Page, type Request } from "@playwright/test";

async function signInAsAdministrator(page: Page): Promise<void> {
  await page.goto("/login?next=%2Fportal");

  await page.getByLabel("Username").fill("atlas-e2e-user");
  await page.getByLabel("Password").fill("atlas-e2e-password");

  await Promise.all([
    page.waitForResponse(
      (response) =>
        response.url().endsWith("/api/v1/auth/login") &&
        response.request().method() === "POST" &&
        response.status() === 200
    ),
    page.getByRole("button", { name: "Sign in" }).click()
  ]);

  await expect(page).toHaveURL(/\/portal$/);
}

test("global administrator can discover the Users identity-management surface", async ({ page }) => {
  await signInAsAdministrator(page);

  const usersLink = page.locator('a[href="/portal/users"]').first();

  await expect(usersLink).toBeVisible();
  await expect(usersLink).toContainText("Users");
});

test("global administrator can inspect users and invitations through the Portal", async ({ page }) => {
  const adminRequests: Request[] = [];

  page.on("request", (request) => {
    if (request.url().includes("/api/v1/admin/")) {
      adminRequests.push(request);
    }
  });

  await signInAsAdministrator(page);

  const usersLink = page.locator('a[href="/portal/users"]').first();
  await expect(usersLink).toBeVisible();

  const initialResponses = Promise.all([
    page.waitForResponse(
      (response) =>
        response.url().endsWith("/api/v1/admin/users") &&
        response.request().method() === "GET" &&
        response.status() === 200
    ),
    page.waitForResponse(
      (response) =>
        response.url().endsWith("/api/v1/admin/invitations") &&
        response.request().method() === "GET" &&
        response.status() === 200
    )
  ]);

  await usersLink.click();
  await initialResponses;

  await expect(page).toHaveURL(/\/portal\/users$/);
  await expect(page.getByRole("heading", { name: "Users", level: 2 })).toBeVisible();
  await expect(page.getByText("Atlas Test", { exact: true })).toBeVisible();
  await expect(page.getByRole("heading", { name: "Invitations" })).toBeVisible();

  expect(adminRequests.length).toBeGreaterThanOrEqual(2);

  for (const request of adminRequests) {
    expect(request.headers()["authorization"]).toBe("Bearer atlas-e2e-access-token");
  }
});

test("global administrator can provision a linked Atlas user", async ({ page }) => {
  await signInAsAdministrator(page);

  const usersLink = page.locator('a[href="/portal/users"]').first();
  await expect(usersLink).toBeVisible();
  await usersLink.click();

  await expect(page).toHaveURL(/\/portal\/users$/);

  await page.getByRole("button", { name: "Create user" }).click();

  await page.getByLabel("Username").fill("atlas-created-user");
  await page.getByLabel("Email").fill("CREATED@example.invalid");
  await page.getByLabel("Initial password").fill("atlas-e2e-created-password");
  await page.getByLabel("Display name").fill("Atlas Created User");
  await page.getByLabel("First name").fill("Atlas");
  await page.getByLabel("Last name").fill("Created");
  await page.getByLabel("Initial role").selectOption("member");

  const createResponsePromise = page.waitForResponse(
    (response) =>
      response.url().endsWith("/api/v1/admin/users") &&
      response.request().method() === "POST" &&
      response.status() === 201
  );

  await page.getByRole(
    "button",
    { name: "Create Atlas user" }
  ).click();

  const createResponse = await createResponsePromise;

  expect(
    createResponse.request().headers()["authorization"]
  ).toBe("Bearer atlas-e2e-access-token");

  const requestBody = createResponse.request().postDataJSON();

  expect(requestBody).toMatchObject({
    username: "atlas-created-user",
    email: "CREATED@example.invalid",
    roles: ["member"],
    display_name: "Atlas Created User",
    first_name: "Atlas",
    last_name: "Created"
  });

  expect(requestBody.password).toBe(
    "atlas-e2e-created-password"
  );

  await expect(
    page.getByRole("heading", {
      name: "Atlas Created User",
      level: 4
    })
  ).toBeVisible();

  await expect(
    page.getByText("atlas-created-user", { exact: true })
  ).toBeVisible();

  await expect(
    page.getByText(
      "atlas-e2e-created-password",
      { exact: true }
    )
  ).toHaveCount(0);

  await expect(
    page.getByRole("button", { name: "Create user" })
  ).toBeVisible();
});

test("global administrator can create and revoke a representative invitation", async ({ page }) => {
  await signInAsAdministrator(page);

  const usersLink = page.locator('a[href="/portal/users"]').first();
  await expect(usersLink).toBeVisible();
  await usersLink.click();

  await expect(page).toHaveURL(/\/portal\/users$/);

  await page.getByRole("button", { name: "Create invitation" }).click();

  await page.getByLabel("Email").fill("atlas-acceptance@example.invalid");
  await page.getByLabel("Role").selectOption("user");
  await page.getByLabel("Expires in days").fill("7");

  const createResponsePromise = page.waitForResponse(
    (response) =>
      response.url().endsWith("/api/v1/admin/invitations") &&
      response.request().method() === "POST" &&
      response.status() === 201
  );

  await page.getByRole("button", { name: "Create invitation", exact: true }).last().click();

  const createResponse = await createResponsePromise;
  expect(createResponse.request().headers()["authorization"]).toBe("Bearer atlas-e2e-access-token");

  await expect(page.getByText("Invitation created", { exact: true })).toBeVisible();
  await expect(page.getByText("Copy this invitation token now", { exact: false })).toBeVisible();

  const revokeButton = page.getByRole("button", { name: "Revoke invitation" }).first();
  await expect(revokeButton).toBeVisible();

  const revokeResponsePromise = page.waitForResponse(
    (response) =>
      response.url().includes("/api/v1/admin/invitations/") &&
      response.url().endsWith("/revoke") &&
      response.request().method() === "POST" &&
      response.status() === 200
  );

  await revokeButton.click();
  await revokeResponsePromise;

  await expect(page.getByText("revoked", { exact: false }).first()).toBeVisible();
});

test("global administrator can inspect and update supported member fields", async ({ page }) => {
  await signInAsAdministrator(page);

  const usersLink = page.locator('a[href="/portal/users"]').first();
  await expect(usersLink).toBeVisible();
  await usersLink.click();

  await expect(page.getByText("Atlas Test", { exact: true })).toBeVisible();
  await page.getByRole("button", { name: /Manage Atlas Test/i }).click();

  await expect(
    page
      .getByLabel("User detail for Atlas Test")
      .getByRole("heading", { name: "Atlas Test", level: 3 })
  ).toBeVisible();

  const disableResponsePromise = page.waitForResponse(
    (response) =>
      response.url().includes("/api/v1/admin/users/") &&
      response.request().method() === "PATCH" &&
      response.status() === 200
  );

  await page.getByRole("button", { name: "Disable user" }).click();
  await disableResponsePromise;

  await expect(page.getByText("disabled", { exact: false }).first()).toBeVisible();

  const enableResponsePromise = page.waitForResponse(
    (response) =>
      response.url().includes("/api/v1/admin/users/") &&
      response.request().method() === "PATCH" &&
      response.status() === 200
  );

  await page.getByRole("button", { name: "Enable user" }).click();
  await enableResponsePromise;

  await expect(page.getByText("active", { exact: false }).first()).toBeVisible();
});
