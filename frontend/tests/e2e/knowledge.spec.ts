import { expect, test } from "@playwright/test";
import { randomUUID } from "node:crypto";

// A valid one-page PDF assembled with byte-accurate xref offsets, without a paid provider.
function evidencePdf(): Buffer {
  const text = "BT /F1 12 Tf 72 700 Td (Orion cobalt batteries have 80 kWh capacity.) Tj ET";
  const objects = [
    "<< /Type /Catalog /Pages 2 0 R >>", "<< /Type /Pages /Kids [3 0 R] /Count 1 >>",
    "<< /Type /Page /Parent 2 0 R /MediaBox [0 0 612 792] /Resources << /Font << /F1 4 0 R >> >> /Contents 5 0 R >>",
    "<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>", `<< /Length ${text.length} >>\nstream\n${text}\nendstream`,
  ];
  let pdf = "%PDF-1.4\n";
  const offsets = [0];
  objects.forEach((object, index) => { offsets.push(Buffer.byteLength(pdf)); pdf += `${index + 1} 0 obj\n${object}\nendobj\n`; });
  const xref = Buffer.byteLength(pdf);
  pdf += `xref\n0 6\n0000000000 65535 f \n${offsets.slice(1).map(offset => `${String(offset).padStart(10, "0")} 00000 n \n`).join("")}trailer\n<< /Size 6 /Root 1 0 R >>\nstartxref\n${xref}\n%%EOF\n`;
  return Buffer.from(pdf);
}

test("register, upload PDF, process, ask, and inspect cited source", async ({ page, isMobile }) => {
  const errors: string[] = [];
  page.on("pageerror", error => errors.push(error.message));
  await page.goto("/register");
  await page.getByLabel("Full name").fill("Browser Researcher");
  await page.getByLabel("Email address").fill(`${randomUUID()}@example.com`);
  await page.getByLabel("Password", { exact: true }).fill("browser-test-password-42");
  await page.getByRole("button", { name: "Create account" }).click();
  await expect(page).toHaveURL(/\/app\/dashboard/);
  if (isMobile) await page.getByRole("button", { name: "Open navigation" }).click();
  await page.getByRole("navigation", { name: "Main navigation" }).getByRole("link", { name: "Documents", exact: true }).click();
  await expect(page.getByRole("heading", { name: "Your documents", exact: true })).toBeVisible();
  await page.getByRole("button", { name: "Upload documents", exact: true }).click();
  await page.getByLabel("Select documents").setInputFiles({ name: "orion.pdf", mimeType: "application/pdf", buffer: evidencePdf() });
  await expect(page.getByText("Uploaded. Processing will continue in the background.")).toBeVisible();
  await page.getByRole("button", { name: "Done", exact: true }).click();
  await expect(page.getByText("Ready", { exact: true })).toBeVisible({ timeout: 60_000 });
  if (isMobile) await page.getByRole("button", { name: "Open navigation" }).click();
  await page.getByRole("link", { name: "New conversation", exact: true }).click();
  await page.getByText("Sources: All workspace documents").click();
  await page.getByRole("checkbox", { name: "orion.pdf" }).check();
  await page.getByLabel("Your question").fill("What is the Orion cobalt battery capacity?");
  await page.getByRole("button", { name: "Ask question" }).click();
  await page.getByRole("button", { name: "[1] orion.pdf · p. 1", exact: true }).click();
  const dialog = page.getByRole("dialog", { name: "orion.pdf" });
  await expect(dialog).toContainText("80 kWh");
  await expect(dialog).toContainText("Page 1");
  const download = page.waitForEvent("download");
  await dialog.getByRole("link", { name: "Download original" }).click();
  expect((await download).suggestedFilename()).toBe("orion.pdf");
  await dialog.getByRole("link", { name: "Inspect document" }).click();
  await expect(page).toHaveURL(/\/app\/documents\/.*\?chunk=/);
  await expect(page.getByRole("heading", { name: "Page 1" })).toBeVisible();
  await expect(page.getByText("Orion cobalt batteries have 80 kWh capacity.", { exact: true })).toBeVisible();
  expect(await page.evaluate(() => document.documentElement.scrollWidth <= window.innerWidth)).toBe(true);
  expect(errors).toEqual([]);
});
