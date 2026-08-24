import { expect, test } from "@playwright/test";

test("Jellyfin catalog item can be added to the authenticated user Favorites list", async ({
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
    page
      .getByRole("button", {
        name: "Sign in"
      })
      .click()
  ]);

  await expect(page).toHaveURL(/\/portal$/);

  const mediaLink = page.locator('a[href="/portal/media"]').first();

  await expect(mediaLink).toBeVisible();

  const catalogResponsePromise = page.waitForResponse(
    (response) =>
      response.url().includes("/api/v1/media/catalog?page=1&page_size=24") &&
      response.request().method() === "GET" &&
      response.status() === 200
  );

  await mediaLink.click();

  await catalogResponsePromise;

  await expect(page).toHaveURL(/\/portal\/media$/);

  const library = page.getByRole("region", {
    name: "Your Jellyfin library"
  });

  await expect(library).toBeVisible();

  await expect(
    library.getByRole("heading", {
      name: "Interstellar"
    })
  ).toBeVisible();

  await expect(
    library.getByText("Library: Movies", {
      exact: true
    })
  ).toBeVisible();

  const addButton = library.getByRole("button", {
    name: "Add Interstellar to favorites"
  });

  await expect(addButton).toBeVisible();

  const favoriteResponsePromise = page.waitForResponse(
    (response) =>
      response.url().endsWith("/api/v1/favorites") && response.request().method() === "POST"
  );

  await addButton.click();

  const favoriteResponse = await favoriteResponsePromise;

  const favoriteRequest = favoriteResponse.request();

  expect(favoriteRequest.headers()["authorization"]).toBe("Bearer atlas-e2e-access-token");

  expect(favoriteRequest.postDataJSON()).toEqual({
    provider: "jellyfin",
    item_id: "jf-interstellar"
  });

  expect(favoriteResponse.status()).toBe(201);

  await expect(
    library.getByRole("button", {
      name: "Interstellar added to favorites"
    })
  ).toBeDisabled();

  const favoritesLink = page.locator('a[href="/portal/favorites"]').first();

  await expect(favoritesLink).toBeVisible();

  const favoritesResponsePromise = page.waitForResponse(
    (response) =>
      response.url().endsWith("/api/v1/favorites") &&
      response.request().method() === "GET" &&
      response.status() === 200
  );

  await favoritesLink.click();

  await favoritesResponsePromise;

  await expect(page).toHaveURL(/\/portal\/favorites$/);

  const favorites = page.getByRole("region", {
    name: "Your favorites"
  });

  await expect(favorites).toBeVisible();

  await expect(
    favorites.getByText("Interstellar", {
      exact: true
    })
  ).toBeVisible();
});
