import { expect, test } from "@playwright/test";

test("authenticated user can request one Sports event without controlling ownership identity", async ({
  page
}) => {
  await page.goto("/login?next=%2Fportal%2Fsports");

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

  // Atlas currently lands successful login at
  // the canonical Portal root. Navigate through
  // the real Portal link so the in-memory session
  // remains the session under test.
  await expect(page).toHaveURL(/\/portal$/);

  const sportsLink = page.locator('a[href="/portal/sports"]').first();

  await expect(sportsLink).toBeVisible();

  const eventsResponsePromise = page.waitForResponse(
    (response) =>
      response.url().includes("/api/v1/sports/events?provider=thesportsdb") &&
      response.request().method() === "GET"
  );

  await sportsLink.click();

  const eventsResponse = await eventsResponsePromise;

  const eventsRequest = eventsResponse.request();

  expect(eventsRequest.headers()["authorization"]).toBe("Bearer atlas-e2e-access-token");

  expect(eventsResponse.status()).toBe(200);

  await expect(page).toHaveURL(/\/portal\/sports$/);

  const events = page.getByRole("region", {
    name: "Upcoming Sports events"
  });

  await expect(events).toBeVisible();

  await expect(
    events.getByText("Atlas United vs Atlas City", {
      exact: true
    })
  ).toBeVisible();

  await expect(
    events.getByText("Atlas Test League", {
      exact: false
    })
  ).toBeVisible();

  const requestButton = events.getByRole("button", {
    name: "Request event"
  });

  await expect(requestButton).toBeVisible();

  await expect(requestButton).toHaveAttribute("data-provider", "thesportsdb");

  await expect(requestButton).toHaveAttribute("data-provider-event-id", "atlas-sports-event-001");

  const requestResponsePromise = page.waitForResponse(
    (response) =>
      response.url().endsWith("/api/v1/sports/subscriptions") &&
      response.request().method() === "POST"
  );

  await requestButton.click();

  const requestResponse = await requestResponsePromise;

  const request = requestResponse.request();

  console.log(`D4_SPORTS_REQUEST_URL=${request.url()}`);

  console.log(`D4_SPORTS_REQUEST_METHOD=${request.method()}`);

  console.log(
    `D4_SPORTS_REQUEST_AUTHORIZATION=${request.headers()["authorization"] ?? "<absent>"}`
  );

  console.log(`D4_SPORTS_REQUEST_BODY=${request.postData() ?? "<absent>"}`);

  console.log(`D4_SPORTS_RESPONSE_STATUS=${requestResponse.status()}`);

  expect(request.headers()["authorization"]).toBe("Bearer atlas-e2e-access-token");

  expect(request.postDataJSON()).toEqual({
    provider: "thesportsdb",
    provider_event_id: "atlas-sports-event-001"
  });

  // Browser-controlled ownership/process identity
  // must not cross the transport boundary.
  const requestBody = request.postDataJSON();

  expect(requestBody).not.toHaveProperty("user_id");

  expect(requestBody).not.toHaveProperty("subscription_id");

  expect(requestBody).not.toHaveProperty("type");

  expect(requestBody).not.toHaveProperty("name");

  expect(requestResponse.status()).toBe(201);

  const responsePayload = await requestResponse.json();

  expect(responsePayload).toMatchObject({
    subscription_id: `sub_${"e".repeat(32)}`,
    type: "event",
    provider: "thesportsdb",
    provider_event_id: "atlas-sports-event-001",
    name: "Atlas United vs Atlas City",
    user_id: `usr_${"a".repeat(32)}`,
    enabled: true
  });

  expect(responsePayload.subscription_id).not.toBe(responsePayload.provider_event_id);

  await expect(
    events.getByRole("button", {
      name: "Requested"
    })
  ).toBeDisabled();

  // The successful browser state itself prevents
  // an accidental second submission.
  await expect(
    events.getByRole("button", {
      name: "Request event"
    })
  ).toHaveCount(0);
});
