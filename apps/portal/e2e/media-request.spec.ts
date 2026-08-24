import { expect, test } from "@playwright/test";

test("successful login establishes an authenticated session and creates one media request", async ({
  page
}) => {
  await page.goto("/login?next=%2Fportal%2Fmedia");

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

  // The current Atlas login contract lands authenticated users
  // on the canonical Portal root. The protected-route `next`
  // parameter is preserved on entry to /login, but successful
  // login does not currently consume it.
  await expect(page).toHaveURL(/\/portal$/);

  // Navigate through the real Next.js Portal link rather than
  // page.goto(). Atlas authentication is intentionally held in
  // process memory, so a full browser reload would discard the
  // authenticated session we are proving here.
  const mediaLink = page.locator('a[href="/portal/media"]').first();

  await expect(mediaLink).toBeVisible();
  await mediaLink.click();

  await expect(page).toHaveURL(/\/portal\/media$/);

  const search = page.getByLabel("Search movies and TV shows");

  await expect(search).toBeVisible();

  await search.fill("Interstellar");

  await Promise.all([
    page.waitForResponse(
      (response) =>
        response.url().includes("/api/v1/media/search?query=Interstellar&page=1") &&
        response.request().method() === "GET" &&
        response.status() === 200
    ),
    page.getByRole("button", { name: "Search" }).click()
  ]);

  const discovery = page.getByRole("region", {
    name: "Media discovery",
    exact: true
  });

  await expect(discovery).toBeVisible();

  await expect(
    discovery.getByRole("heading", {
      name: "Interstellar"
    })
  ).toBeVisible();

  await expect(discovery.getByText("Not tracked", { exact: true })).toBeVisible();

  const requestButton = discovery.getByRole("button", { name: "Request movie" });

  await expect(requestButton).toBeVisible();

  const requestResponsePromise = page.waitForResponse(
    (response) =>
      response.url().endsWith("/api/v1/requests") && response.request().method() === "POST"
  );

  await requestButton.click();

  const requestResponse = await requestResponsePromise;
  const request = requestResponse.request();

  console.log(`D2_REQUEST_URL=${request.url()}`);
  console.log(`D2_REQUEST_METHOD=${request.method()}`);
  console.log(`D2_REQUEST_AUTHORIZATION=${request.headers()["authorization"] ?? "<absent>"}`);
  console.log(`D2_REQUEST_BODY=${request.postData() ?? "<absent>"}`);
  console.log(`D2_RESPONSE_STATUS=${requestResponse.status()}`);

  let responseBody = "<unreadable>";

  try {
    responseBody = await requestResponse.text();
  } catch {
    // Diagnostic only.
  }

  console.log(`D2_RESPONSE_BODY=${responseBody}`);

  expect(request.headers()["authorization"]).toBe("Bearer atlas-e2e-access-token");

  expect(request.postDataJSON()).toEqual({
    media_type: "movie",
    provider_media_id: "157336",
    title: "Interstellar",
    year: 2014
  });

  expect(requestResponse.status(), `media-request response body: ${responseBody}`).toBe(201);

  await expect(page.getByRole("button", { name: "Requested" })).toBeDisabled();
});
