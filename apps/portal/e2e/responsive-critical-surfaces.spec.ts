import { expect, test, type Locator, type Page } from "@playwright/test";

type ResponsiveViewport = Readonly<{
  name: string;
  width: number;
  height: number;
  compactNavigation: boolean;
}>;

const VIEWPORTS: readonly ResponsiveViewport[] = [
  {
    name: "phone-390x844",
    width: 390,
    height: 844,
    compactNavigation: true
  },
  {
    name: "tablet-768x1024",
    width: 768,
    height: 1024,
    compactNavigation: true
  },
  {
    name: "desktop-1280x800",
    width: 1280,
    height: 800,
    compactNavigation: false
  }
];

async function expectNoHorizontalDocumentOverflow(page: Page, label: string): Promise<void> {
  const dimensions = await page.evaluate(() => ({
    innerWidth: window.innerWidth,
    documentClientWidth: document.documentElement.clientWidth,
    documentScrollWidth: document.documentElement.scrollWidth,
    bodyScrollWidth: document.body.scrollWidth
  }));

  expect(
    dimensions.documentScrollWidth,
    `${label}: documentElement exceeds the viewport`
  ).toBeLessThanOrEqual(dimensions.innerWidth + 1);

  expect(dimensions.bodyScrollWidth, `${label}: body exceeds the viewport`).toBeLessThanOrEqual(
    dimensions.innerWidth + 1
  );

  expect(
    dimensions.documentClientWidth,
    `${label}: client width differs materially from viewport`
  ).toBeLessThanOrEqual(dimensions.innerWidth + 1);
}

async function expectHorizontallyInsideViewport(
  page: Page,
  locator: Locator,
  label: string
): Promise<void> {
  await expect(locator, `${label}: element must be visible`).toBeVisible();

  const box = await locator.boundingBox();

  expect(box, `${label}: visible element must have a bounding box`).not.toBeNull();

  if (!box) {
    return;
  }

  expect(box.x, `${label}: element begins left of viewport`).toBeGreaterThanOrEqual(-1);

  expect(
    box.x + box.width,
    `${label}: element extends past right viewport edge`
  ).toBeLessThanOrEqual((await page.evaluate(() => window.innerWidth)) + 1);
}

async function login(page: Page): Promise<void> {
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
}

async function openCompactNavigation(page: Page): Promise<void> {
  const menuButton = page.getByRole("button", {
    name: "Open navigation",
    exact: true
  });

  await expect(menuButton).toBeVisible();

  await menuButton.click();

  const navigation = page
    .getByRole("complementary", {
      name: "Portal navigation",
      exact: true
    })
    .getByRole("navigation");

  await expect(navigation).toBeVisible();

  await expect(
    page
      .getByRole("button", {
        name: "Close navigation"
      })
      .last()
  ).toBeVisible();
}

async function navigateThroughPortal(
  page: Page,
  viewport: ResponsiveViewport,
  href: string
): Promise<void> {
  if (viewport.compactNavigation) {
    await openCompactNavigation(page);
  }

  const link = page.locator(`a[href="${href}"]`).first();

  await expect(link).toBeVisible();

  await link.click();

  await expect(page).toHaveURL(new RegExp(`${href.replace(/[.*+?^${}()|[\]\\]/g, "\\$&")}$`));
}

for (const viewport of VIEWPORTS) {
  test(`responsive critical surfaces remain usable at ${viewport.name}`, async ({ page }) => {
    await page.setViewportSize({
      width: viewport.width,
      height: viewport.height
    });

    // ------------------------------------------------------
    // Login
    // ------------------------------------------------------

    await page.goto("/login");

    await expect(
      page.getByRole("heading", {
        name: "Welcome back"
      })
    ).toBeVisible();

    const username = page.getByLabel("Username");

    const password = page.getByLabel("Password");

    const signIn = page.getByRole("button", {
      name: "Sign in"
    });

    await expectHorizontallyInsideViewport(page, username, `${viewport.name} login username`);

    await expectHorizontallyInsideViewport(page, password, `${viewport.name} login password`);

    await expectHorizontallyInsideViewport(page, signIn, `${viewport.name} login submit`);

    await expectNoHorizontalDocumentOverflow(page, `${viewport.name} login`);

    await login(page);

    // ------------------------------------------------------
    // Portal shell
    // ------------------------------------------------------

    await expectNoHorizontalDocumentOverflow(page, `${viewport.name} portal shell`);

    if (viewport.compactNavigation) {
      await openCompactNavigation(page);

      await page
        .getByRole("button", {
          name: "Close navigation"
        })
        .last()
        .click();

      await expect(
        page.getByRole("button", {
          name: "Open navigation",
          exact: true
        })
      ).toBeVisible();
    }

    // ------------------------------------------------------
    // Media
    // ------------------------------------------------------

    const catalogResponsePromise = page.waitForResponse(
      (response) =>
        response.url().includes("/api/v1/media/catalog?page=1&page_size=24") &&
        response.request().method() === "GET" &&
        response.status() === 200
    );

    await navigateThroughPortal(page, viewport, "/portal/media");

    await catalogResponsePromise;

    const mediaRegion = page.getByRole("region", {
      name: "Your Jellyfin library"
    });

    await expect(mediaRegion).toBeVisible();

    await expect(
      mediaRegion.getByRole("heading", {
        name: "Interstellar"
      })
    ).toBeVisible();

    await expectHorizontallyInsideViewport(
      page,
      mediaRegion.getByRole("button", {
        name: "Add Interstellar to favorites"
      }),
      `${viewport.name} media favorite action`
    );

    await expectNoHorizontalDocumentOverflow(page, `${viewport.name} media`);

    // ------------------------------------------------------
    // Favorites
    // ------------------------------------------------------

    const favoritesResponsePromise = page.waitForResponse(
      (response) =>
        response.url().endsWith("/api/v1/favorites") &&
        response.request().method() === "GET" &&
        response.status() === 200
    );

    await navigateThroughPortal(page, viewport, "/portal/favorites");

    await favoritesResponsePromise;

    await expect(
      page.getByRole("heading", {
        name: "Your favorites",
        exact: true
      })
    ).toBeVisible();

    await expectNoHorizontalDocumentOverflow(page, `${viewport.name} favorites`);

    // ------------------------------------------------------
    // Sports
    // ------------------------------------------------------

    const eventsResponsePromise = page.waitForResponse(
      (response) =>
        response.url().includes("/api/v1/sports/events?provider=thesportsdb") &&
        response.request().method() === "GET" &&
        response.status() === 200
    );

    await navigateThroughPortal(page, viewport, "/portal/sports");

    await eventsResponsePromise;

    const sportsRegion = page.getByRole("region", {
      name: "Upcoming Sports events"
    });

    await expect(sportsRegion).toBeVisible();

    await expect(
      sportsRegion.getByText("Atlas United vs Atlas City", {
        exact: true
      })
    ).toBeVisible();

    await expectHorizontallyInsideViewport(
      page,
      sportsRegion.getByRole("button", {
        name: "Request event"
      }),
      `${viewport.name} Sports request action`
    );

    await expectNoHorizontalDocumentOverflow(page, `${viewport.name} Sports`);

    // ------------------------------------------------------
    // Administrator / Services
    // ------------------------------------------------------

    const serviceResponsesPromise = Promise.all([
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

    await navigateThroughPortal(page, viewport, "/portal/services");

    await serviceResponsesPromise;

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

    const viewDetails = page
      .getByRole("button", {
        name: "View details"
      })
      .first();

    await expectHorizontallyInsideViewport(
      page,
      viewDetails,
      `${viewport.name} service detail action`
    );

    const detailResponsePromise = page.waitForResponse(
      (response) =>
        response.url().endsWith("/api/v1/services/jellyfin") &&
        response.request().method() === "GET" &&
        response.status() === 200
    );

    await viewDetails.click();

    const detailResponse = await detailResponsePromise;

    expect(detailResponse.request().method()).toBe("GET");

    await expect(
      page.getByText("Read-only service detail", {
        exact: true
      })
    ).toBeVisible();

    const closeDetails = page.getByRole("button", {
      name: "Close details"
    });

    await expectHorizontallyInsideViewport(
      page,
      closeDetails,
      `${viewport.name} service close-detail action`
    );

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

    await expectNoHorizontalDocumentOverflow(page, `${viewport.name} Services detail`);

    await closeDetails.click();

    await expect(
      page.getByText("Read-only service detail", {
        exact: true
      })
    ).toHaveCount(0);
  });
}
