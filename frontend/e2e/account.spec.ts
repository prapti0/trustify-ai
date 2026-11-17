import { expect, test } from "@playwright/test";

test("register, upload, and open an inconclusive report", async ({ page }) => {
  const email = `analyst-${Date.now()}@example.com`;
  await page.goto("/");
  await expect(page.getByRole("heading", { name: "Verify What's Real. Detect What's Fake." })).toBeVisible();
  await page.getByRole("link", { name: "Get Started" }).click();
  await page.getByLabel("Full Name").fill("Ada Lovelace");
  await page.getByLabel("Email Address").fill(email);
  await page.getByLabel("Password", { exact: true }).fill("correct-horse-battery");
  await page.getByLabel("Confirm Password").fill("correct-horse-battery");
  await page.getByRole("checkbox").check();
  await page.getByRole("button", { name: "Create Account" }).click();
  await expect(page.getByRole("heading", { name: "Security & Authenticity Dashboard" })).toBeVisible();
  await expect(page.getByText("Total Files Analyzed").locator("xpath=..")).toContainText("0");

  await page.getByRole("link", { name: "New Analysis" }).first().click();
  await page.locator("input[type=file]").setInputFiles({
    name: "sample.png",
    mimeType: "image/png",
    buffer: Buffer.from([0x89, 0x50, 0x4e, 0x47, 0x0d, 0x0a, 0x1a, 0x0a, 0x72, 0x65, 0x73, 0x74]),
  });
  await page.getByRole("button", { name: "Start Analysis" }).click();
  await page.getByRole("link", { name: "Open report" }).click();
  await expect(page.getByText("Inconclusive", { exact: true }).first()).toBeVisible();
  await expect(page.getByText("A numeric risk score is omitted")).toBeVisible();
  await expect(page.getByText("Not produced").first()).toBeVisible();
  await page.getByRole("button", { name: "Download PDF Report" }).click();
  await expect(page.getByText("PDF report export is not implemented.")).toBeVisible();

  await expect(page.locator(".report-sheet").first()).toHaveCSS("background-color", "rgb(247, 248, 251)");
  await page.getByRole("button", { name: "Toggle color theme" }).click();
  await expect(page.locator("html")).toHaveAttribute("data-theme", "light");
  await expect(page.locator(".report-sheet").first()).toHaveCSS("background-color", "rgb(247, 248, 251)");

  await page.goto("/app/analyze");
  await page.getByLabel("Public URL").fill("https://testsafebrowsing.appspot.com/s/phishing.html");
  await page.getByRole("button", { name: "Analyze URL" }).click();
  await expect(page.getByText("High Risk", { exact: true }).first()).toBeVisible();
  await expect(page.getByText("phishing", { exact: false }).first()).toBeVisible();

  await page.locator("input[type=file]").setInputFiles({
    name: "sample.png",
    mimeType: "image/png",
    buffer: Buffer.from([0x89, 0x50, 0x4e, 0x47, 0x0d, 0x0a, 0x1a, 0x0a, 0x72, 0x65, 0x73, 0x74]),
  });
  await page.getByRole("button", { name: "Start Analysis" }).click();
  await page.goto("/app/duplicates");
  await expect(page.getByText("does not search the public internet")).toBeVisible();
  await expect(page.getByRole("cell", { name: "Exact", exact: true })).toBeVisible();
  await expect(page.getByRole("cell", { name: "Exact Hash" })).toBeVisible();

  await page.setViewportSize({ width: 390, height: 844 });
  await page.goto("/app");
  await page.getByRole("button", { name: "Menu" }).click();
  await expect(page.getByRole("link", { name: "Video Forensics" })).toBeVisible();
  await expect(page.getByText("Total Files Analyzed").locator("xpath=..")).toContainText("2");
});
