import AxeBuilder from "@axe-core/playwright";
import { expect, test, type Page } from "@playwright/test";

const USERNAME = "atlas-e2e-user";
const PASSWORD = "atlas-e2e-password";

type AxeResults = Awaited<ReturnType<AxeBuilder["analyze"]>>;

type AxeViolation = AxeResults["violations"][number];

async function login(page: Page): Promise<void> {
  await page.goto("/login");

  await page
    .getByLabel("Username", {
      exact: true
    })
    .fill(USERNAME);

  await page
    .getByLabel("Password", {
      exact: true
    })
    .fill(PASSWORD);

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

async function navigateProtected(page: Page, path: string): Promise<void> {
  const link = page.locator(`a[href="${path}"]`).first();

  await expect(link).toBeVisible();

  await link.click();

  await expect(page).toHaveURL(new RegExp(`${path.replace(/[.*+?^${}()|[\]\\]/g, "\\$&")}$`));
}

function seriousOrCritical(violations: AxeViolation[]): AxeViolation[] {
  return violations.filter(
    (violation) => violation.impact === "serious" || violation.impact === "critical"
  );
}

function describeViolations(violations: AxeViolation[]): string {
  return violations
    .map((violation) => {
      const targets = violation.nodes.map((node) => JSON.stringify(node.target)).join(", ");

      return [
        `id=${violation.id}`,
        `impact=${violation.impact}`,
        `help=${violation.help}`,
        `targets=${targets}`
      ].join(" | ");
    })
    .join("\n");
}

async function scan(page: Page, surface: string): Promise<void> {
  const results = await new AxeBuilder({
    page
  }).analyze();

  const blocking = seriousOrCritical(results.violations);

  console.log(`Q3D_AXE_SURFACE=${surface}`);

  console.log(`Q3D_AXE_TOTAL_VIOLATIONS=${results.violations.length}`);

  console.log(`Q3D_AXE_BLOCKING_VIOLATIONS=${blocking.length}`);

  for (const violation of blocking) {
    console.log(`Q3D_AXE_VIOLATION=${describeViolations([violation])}`);
  }

  expect(
    blocking,
    [`${surface} has serious/critical Axe violations.`, describeViolations(blocking)].join("\n")
  ).toEqual([]);
}

test.describe("Q.3 automated Axe accessibility scan", () => {
  test("Login has no serious or critical Axe violations", async ({ page }) => {
    await page.setViewportSize({
      width: 1280,
      height: 800
    });

    await page.goto("/login");

    await expect(
      page.getByRole("button", {
        name: "Sign in",
        exact: true
      })
    ).toBeVisible();

    await scan(page, "login");
  });

  test("Portal dashboard shell has no serious or critical Axe violations", async ({ page }) => {
    await page.setViewportSize({
      width: 1280,
      height: 800
    });

    await login(page);

    await expect(page.locator("#portal-main-content")).toBeVisible();

    await scan(page, "portal-dashboard");
  });

  test("Media has no serious or critical Axe violations", async ({ page }) => {
    await page.setViewportSize({
      width: 1280,
      height: 800
    });

    await login(page);

    await navigateProtected(page, "/portal/media");

    await expect(
      page.getByRole("region", {
        name: "Media discovery",
        exact: true
      })
    ).toBeVisible();

    await scan(page, "media");
  });

  test("Favorites has no serious or critical Axe violations", async ({ page }) => {
    await page.setViewportSize({
      width: 1280,
      height: 800
    });

    await login(page);

    await navigateProtected(page, "/portal/favorites");

    await expect(
      page
        .getByRole("heading", {
          name: "Your favorites",
          exact: true
        })
        .first()
    ).toBeVisible();

    await scan(page, "favorites");
  });

  test("Sports has no serious or critical Axe violations", async ({ page }) => {
    await page.setViewportSize({
      width: 1280,
      height: 800
    });

    await login(page);

    await navigateProtected(page, "/portal/sports");

    await expect(
      page.getByRole("region", {
        name: "Upcoming Sports events",
        exact: true
      })
    ).toBeVisible();

    await scan(page, "sports");
  });

  test("Services has no serious or critical Axe violations", async ({ page }) => {
    await page.setViewportSize({
      width: 1280,
      height: 800
    });

    await login(page);

    await navigateProtected(page, "/portal/services");

    await expect(
      page.getByRole("region", {
        name: "Service Lifecycle summary",
        exact: true
      })
    ).toBeVisible();

    await scan(page, "services");
  });
});
