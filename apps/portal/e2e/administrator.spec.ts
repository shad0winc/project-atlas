import { expect, test, type Request } from "@playwright/test";

test("authenticated administrator can inspect the complete read-only Service Lifecycle surface", async ({
  page
}) => {
  const serviceRequests: Request[] = [];

  page.on("request", (request) => {
    if (request.url().includes("/api/v1/services")) {
      serviceRequests.push(request);
    }
  });

  await page.goto("/login?next=%2Fportal%2Fservices");

  await page.getByLabel("Username").fill("atlas-e2e-user");

  await page.getByLabel("Password").fill("atlas-e2e-password");

  await Promise.all([
    page.waitForResponse(
      (response) =>
        response.url().endsWith("/api/v1/auth/login") &&
        response.request().method() === "POST" &&
        response.status() === 200
    ),
    page
      .getByRole("button", {
        name: "Sign in"
      })
      .click()
  ]);

  await expect(page).toHaveURL(/\/portal$/);

  /*
   * Navigate through the real Portal link.
   *
   * The current authenticated Portal session is held in
   * process memory, so this deliberately follows the same
   * contract used by the existing critical E2E journeys.
   *
   * This is also the expected D.5.3A RED point: the current
   * deterministic fixture has not yet granted
   * system.health.read.
   */
  const servicesLink = page.locator('a[href="/portal/services"]').first();

  await expect(servicesLink).toBeVisible();

  const overviewResponsesPromise = Promise.all([
    page.waitForResponse(
      (response) =>
        response.url().endsWith("/api/v1/services") &&
        response.request().method() === "GET" &&
        response.status() === 200
    ),
    page.waitForResponse(
      (response) =>
        response.url().endsWith("/api/v1/services/health") &&
        response.request().method() === "GET" &&
        response.status() === 200
    ),
    page.waitForResponse(
      (response) =>
        response.url().endsWith("/api/v1/services/summary") &&
        response.request().method() === "GET" &&
        response.status() === 200
    ),
    page.waitForResponse(
      (response) =>
        response.url().endsWith("/api/v1/services/updates") &&
        response.request().method() === "GET" &&
        response.status() === 200
    ),
    page.waitForResponse(
      (response) =>
        response.url().endsWith("/api/v1/services/history") &&
        response.request().method() === "GET" &&
        response.status() === 200
    )
  ]);

  await servicesLink.click();

  const overviewResponses = await overviewResponsesPromise;

  await expect(page).toHaveURL(/\/portal\/services$/);

  for (const response of overviewResponses) {
    const request = response.request();

    expect(request.headers()["authorization"]).toBe("Bearer atlas-e2e-access-token");

    expect(request.method()).toBe("GET");
  }

  await expect(
    page.getByText("Service health", {
      exact: true
    })
  ).toBeVisible();

  await expect(
    page
      .getByText("Managed services", {
        exact: true
      })
      .first()
  ).toBeVisible();

  await expect(
    page.getByText("1 update available", {
      exact: true
    })
  ).toBeVisible();

  await expect(
    page.getByText("2 maintenance records", {
      exact: true
    })
  ).toBeVisible();

  await expect(
    page
      .getByRole("heading", {
        name: "Jellyfin"
      })
      .first()
  ).toBeVisible();

  await expect(
    page
      .getByText("Runtime: running", {
        exact: true
      })
      .first()
  ).toBeVisible();

  await expect(
    page
      .getByText("Health: healthy", {
        exact: true
      })
      .first()
  ).toBeVisible();

  const detailResponsePromise = page.waitForResponse(
    (response) =>
      response.url().endsWith("/api/v1/services/jellyfin") &&
      response.request().method() === "GET" &&
      response.status() === 200
  );

  await page
    .getByRole("button", {
      name: "View details"
    })
    .first()
    .click();

  const detailResponse = await detailResponsePromise;

  expect(detailResponse.request().headers()["authorization"]).toBe("Bearer atlas-e2e-access-token");

  await expect(
    page.getByText("Read-only service detail", {
      exact: true
    })
  ).toBeVisible();

  await expect(
    page.getByText("container name", {
      exact: true
    })
  ).toBeVisible();

  await expect(
    page.getByRole("button", {
      name: "Close details"
    })
  ).toBeVisible();

  /*
   * The v1.0 Service Lifecycle administration surface is
   * explicitly read-only.
   */
  await expect(
    page.getByRole("button", {
      name: "Restart",
      exact: true
    })
  ).toHaveCount(0);

  await expect(
    page.getByRole("button", {
      name: "Update service",
      exact: true
    })
  ).toHaveCount(0);

  await expect(
    page.getByRole("button", {
      name: "Rollback",
      exact: true
    })
  ).toHaveCount(0);

  await page
    .getByRole("button", {
      name: "Close details"
    })
    .click();

  await expect(
    page.getByText("Read-only service detail", {
      exact: true
    })
  ).toHaveCount(0);

  /*
   * Every browser request crossing the Service Lifecycle API
   * boundary must remain GET-only.
   *
   * Do not assert an exact request count here: React or browser
   * lifecycle behavior may safely repeat an idempotent GET.
   * Instead certify that every observed Service Lifecycle
   * request is authenticated and read-only.
   */
  expect(serviceRequests.length).toBeGreaterThanOrEqual(6);

  for (const request of serviceRequests) {
    expect(request.method()).toBe("GET");

    expect(request.headers()["authorization"]).toBe("Bearer atlas-e2e-access-token");
  }
});
