/**
 * Visual regression tests — Settings Panel
 *
 * Covers all visible sections of SettingsPanel.svelte:
 *   - Appearance (theme toggle)
 *   - Security (root access, dry run, snapshot toggles)
 *   - Usage (token/cost display)
 *   - Screen Vision
 *   - Model (provider, mode, ollama model)
 *   - Cloud API (provider buttons, API key input)
 *   - Restrictions
 *   - Debug
 *
 * Also tests the light-mode variant to catch theme-switching regressions.
 */

import { test, expect } from "@playwright/test";
import { gotoApp, clickTab, freezeAnimations } from "./helpers";

test.describe("Settings Panel", () => {
  test.beforeEach(async ({ page }) => {
    await gotoApp(page);
    await clickTab(page, "Settings");
    await freezeAnimations(page);
    // Wait for the settings panel to be fully rendered
    await page.waitForSelector(".settings-panel", { timeout: 5_000 });
  });

  test("full settings panel matches baseline (dark mode)", async ({ page }) => {
    const panel = page.locator(".settings-panel");
    await expect(panel).toBeVisible();
    await expect(panel).toHaveScreenshot("settings-full-dark.png", {
      fullPage: false,
    });
  });

  test("appearance section matches baseline", async ({ page }) => {
    const section = page
      .locator(".settings-group")
      .filter({ hasText: "Appearance" });
    await expect(section).toBeVisible();
    await expect(section).toHaveScreenshot("settings-appearance-section.png");
  });

  test("security section matches baseline", async ({ page }) => {
    const section = page
      .locator(".settings-group")
      .filter({ hasText: "Security" });
    await expect(section).toBeVisible();
    await expect(section).toHaveScreenshot("settings-security-section.png");
  });

  test("model section matches baseline", async ({ page }) => {
    const section = page
      .locator(".settings-group")
      .filter({ hasText: "Model" })
      .first();
    await expect(section).toBeVisible();
    await expect(section).toHaveScreenshot("settings-model-section.png");
  });

  test("cloud API section matches baseline", async ({ page }) => {
    const section = page
      .locator(".settings-group")
      .filter({ hasText: "Cloud API" });
    await expect(section).toBeVisible();
    await expect(section).toHaveScreenshot("settings-cloud-section.png");
  });

  test("toggle active state renders correctly", async ({ page }) => {
    // Click the Root Access toggle and verify the active CSS class is applied
    const rootToggle = page
      .locator(".setting-row")
      .filter({ hasText: "Root Access" })
      .locator(".toggle");

    await expect(rootToggle).toBeVisible();
    // Capture inactive state
    await expect(rootToggle).toHaveScreenshot("settings-toggle-inactive.png");

    // Click to activate
    await rootToggle.click();
    await page.waitForTimeout(100);
    await expect(rootToggle).toHaveScreenshot("settings-toggle-active.png");
  });

  test("light mode settings panel matches baseline", async ({ page }) => {
    // Click the Light Mode toggle to switch themes
    const themeToggle = page
      .locator(".setting-row")
      .filter({ hasText: "Light Mode" })
      .locator(".toggle");

    await themeToggle.click();
    await page.waitForTimeout(200); // allow theme transition

    const panel = page.locator(".settings-panel");
    await expect(panel).toHaveScreenshot("settings-full-light.png");
  });

  test("restrictions section matches baseline", async ({ page }) => {
    const section = page
      .locator(".settings-group")
      .filter({ hasText: "Restrictions" });
    await expect(section).toBeVisible();
    await expect(section).toHaveScreenshot("settings-restrictions-section.png");
  });

  test("learned risk world model exposes runtime status and saves its toggle", async ({
    page,
  }) => {
    const section = page
      .locator(".settings-group")
      .filter({ hasText: "Learned Risk World Model" });
    await section.scrollIntoViewIfNeeded();

    await expect(section).toContainText("Loaded");
    await expect(section).toContainText("36,000 real samples");
    await expect(section).toContainText("risk-mlp-v2-action-types");
    await expect(section).toContainText("80% risk");
    await expect(section).toContainText("learned + rule");

    await section.getByRole("button", { name: "Toggle Learned Risk World Model" }).click();
    await section.getByRole("button", { name: "Save" }).click();

    await expect
      .poll(() =>
        page.evaluate(() => (window as any).__risk_gate_update__)
      )
      .toMatchObject({
        method: "risk_gate_config_update",
        params: { enabled: false },
      });
  });

  test("voice workflow panel submits a durable workflow goal", async ({
    page,
  }) => {
    const section = page
      .locator(".settings-group")
      .filter({ hasText: "Active Voice/Gesture Workflows" });
    await section.scrollIntoViewIfNeeded();

    await expect(section).toContainText("No active workflows right now.");
    await section
      .getByPlaceholder("Describe the multi-step goal")
      .fill("open github and review notifications");
    await section.getByRole("button", { name: "Start Workflow" }).click();

    await expect
      .poll(() => page.evaluate(() => (window as any).__workflow_submit__))
      .toMatchObject({
        method: "voice_gesture_workflow_submit",
        params: {
          goal: "open github and review notifications",
          invocation_source: "voice",
        },
      });
  });

  test("autonomous healing shows live monitors and saves selected metrics", async ({
    page,
  }) => {
    const section = page
      .locator(".settings-group")
      .filter({ hasText: "Autonomous Healing" });
    await section.scrollIntoViewIfNeeded();

    await expect(section).toContainText("CPU > 80% · 24% · 12 checks");
    await expect(section).toContainText("RAM > 85% · 58% · 8 checks");
    await expect(section).toContainText("Disk > 90% · 71% · 2 checks");
    await section.getByRole("button", { name: "Toggle disk monitoring" }).click();
    await section.getByRole("button", { name: "Save" }).click();

    await expect
      .poll(() => page.evaluate(() => (window as any).__self_healing_update__))
      .toMatchObject({
        method: "self_healing_config_update",
        params: {
          enabled: true,
          auto_execute_max_tier: 1,
          watched_metrics: ["cpu", "memory"],
        },
      });
  });

  test("full window with settings tab active matches baseline", async ({
    page,
  }) => {
    await expect(page.locator(".window")).toHaveScreenshot(
      "settings-full-window.png"
    );
  });
});
