import { expect, test, type Page } from "@playwright/test";

const USERNAME = "atlas-e2e-user";
const PASSWORD = "atlas-e2e-password";

async function login(page: Page): Promise<void> {
  await page.goto("/login");

  await page.getByLabel("Username").fill(USERNAME);

  await page.getByLabel("Password").fill(PASSWORD);

  await Promise.all([
    page.waitForURL(/\/portal(?:\/)?$/),
    page
      .getByRole("button", {
        name: "Sign in",
        exact: true
      })
      .click()
  ]);
}

async function gotoProtected(page: Page, path: string): Promise<void> {
  const link = page.locator(`a[href="${path}"]`).first();

  await expect(link).toBeVisible();

  await link.click();

  await expect(page).toHaveURL(new RegExp(`${path.replace(/[.*+?^${}()|[\]\\]/g, "\\$&")}$`));

  await expect(page.locator("#portal-main-content")).toBeVisible();
}

test.describe("Q.3 accessibility critical surfaces", () => {
  test("semantic baseline — login and Portal shell expose accessible controls and landmarks", async ({
    page
  }) => {
    await page.setViewportSize({
      width: 390,
      height: 844
    });

    await page.goto("/login");

    const username = page.getByLabel("Username", {
      exact: true
    });

    const password = page.getByLabel("Password", {
      exact: true
    });

    const signIn = page.getByRole("button", {
      name: "Sign in",
      exact: true
    });

    await expect(username).toBeVisible();

    await expect(password).toBeVisible();

    await expect(signIn).toBeVisible();

    await username.focus();

    await expect(username).toBeFocused();

    await page.keyboard.press("Tab");

    await expect(password).toBeFocused();

    await page.keyboard.press("Tab");

    await expect(signIn).toBeFocused();

    await username.fill(USERNAME);

    await password.fill(PASSWORD);

    await Promise.all([page.waitForURL(/\/portal(?:\/)?$/), page.keyboard.press("Enter")]);

    await expect(page.locator("#portal-main-content")).toBeVisible();

    await expect(page.locator('aside[aria-label="Portal navigation"]')).toHaveAttribute(
      "data-open",
      "false"
    );

    await expect(
      page.getByRole("button", {
        name: "Open navigation",
        exact: true
      })
    ).toBeVisible();
  });

  test("semantic baseline — Media Favorites Sports and Services expose named critical surfaces", async ({
    page
  }) => {
    await page.setViewportSize({
      width: 1280,
      height: 800
    });

    await login(page);

    await gotoProtected(page, "/portal/media");

    const currentMedia = page
      .locator('aside[aria-label="Portal navigation"]')
      .getByRole("navigation")
      .locator('a[href="/portal/media"]');

    await expect(currentMedia).toHaveCount(1);

    await expect(currentMedia).toHaveAttribute("aria-current", "page");

    await expect(
      page.getByRole("region", {
        name: "Media discovery",
        exact: true
      })
    ).toBeVisible();

    await expect(
      page.getByLabel("Search movies and TV shows", {
        exact: true
      })
    ).toBeVisible();

    await expect(
      page.getByRole("navigation", {
        name: "Media discovery pages",
        exact: true
      })
    ).toBeVisible();

    await gotoProtected(page, "/portal/favorites");

    await expect(
      page
        .getByRole("heading", {
          name: "Your favorites",
          exact: true
        })
        .first()
    ).toBeVisible();

    await gotoProtected(page, "/portal/sports");

    await expect(
      page.getByRole("region", {
        name: "Upcoming Sports events",
        exact: true
      })
    ).toBeVisible();

    await expect(
      page
        .getByRole("region", {
          name: "Upcoming Sports events",
          exact: true
        })
        .getByRole("button")
        .first()
    ).toBeVisible();

    await gotoProtected(page, "/portal/services");

    await expect(
      page.getByRole("region", {
        name: "Service Lifecycle summary",
        exact: true
      })
    ).toBeVisible();

    await expect(
      page
        .getByRole("heading", {
          name: "Managed services",
          exact: true
        })
        .first()
    ).toBeVisible();
  });

  test("semantic baseline — compact navigation opens and closes from the keyboard", async ({
    page
  }) => {
    await page.setViewportSize({
      width: 390,
      height: 844
    });

    await login(page);

    const openNavigation = page.getByRole("button", {
      name: "Open navigation",
      exact: true
    });

    const navigation = page.getByRole("complementary", {
      name: "Portal navigation",
      exact: true
    });

    await openNavigation.focus();

    await expect(openNavigation).toBeFocused();

    await page.keyboard.press("Enter");

    await expect(navigation).toHaveAttribute("data-open", "true");

    await page.keyboard.press("Escape");

    await expect(page.locator('aside[aria-label="Portal navigation"]')).toHaveAttribute(
      "data-open",
      "false"
    );

    await expect(openNavigation).toBeFocused();
  });

  test("closed compact navigation stays out of reverse keyboard flow", async ({ page }) => {
    await page.setViewportSize({
      width: 390,
      height: 844
    });

    await login(page);

    const openNavigation = page.getByRole("button", {
      name: "Open navigation",
      exact: true
    });

    const navigation = page.locator('aside[aria-label="Portal navigation"]');

    await expect(navigation).toHaveAttribute("data-open", "false");

    await openNavigation.focus();

    await expect(openNavigation).toBeFocused();

    await page.keyboard.press("Shift+Tab");

    const focusEnteredClosedNavigation = await page.evaluate(() => {
      const active = document.activeElement;

      const sidebar = document.querySelector('[aria-label="Portal navigation"]');

      const backdrop = document.querySelector(".portal-sidebar-backdrop");

      return (
        active !== null && (active === backdrop || (sidebar !== null && sidebar.contains(active)))
      );
    });

    expect(
      focusEnteredClosedNavigation,
      "closed compact navigation must not receive sequential keyboard focus"
    ).toBe(false);
  });
});
