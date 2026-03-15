import { chromium } from "playwright";
import { execSync } from "node:child_process";
import os from "node:os";
import path from "node:path";
import fs from "node:fs";

const repoRoot = process.cwd();
const extensionPath = path.join(repoRoot, "chrome_extension");
const userDataDir = fs.mkdtempSync(path.join(os.tmpdir(), "pii-masker-pw-"));

function extensionIdFromServiceWorkerUrl(url) {
  // chrome-extension://<id>/background.js
  const parts = url.split("/");
  return parts[2];
}

async function launchWithExtension() {
  return chromium.launchPersistentContext(userDataDir, {
    channel: "msedge",
    headless: false,
    args: [
      `--disable-extensions-except=${extensionPath}`,
      `--load-extension=${extensionPath}`,
    ],
  });
}

async function getExtensionId() {
  const context = await launchWithExtension();
  try {
    let [serviceWorker] = context.serviceWorkers();
    if (!serviceWorker) {
      serviceWorker = await context.waitForEvent("serviceworker", { timeout: 15000 });
    }
    return extensionIdFromServiceWorkerUrl(serviceWorker.url());
  } finally {
    await context.close();
  }
}

async function runPopupDiagnosis(extensionId) {
  const context = await launchWithExtension();
  try {
    const page = await context.newPage();
    await page.goto(`chrome-extension://${extensionId}/popup.html`);
    await page.locator("#keyFile").fill(path.join(repoRoot, "secret.key"));
    await page.locator("#language").selectOption("en");
    await page.locator("#engine").selectOption("transformers");
    await page.locator("#spacyModel").fill("en_core_web_lg");
    await page.locator("#transformersModel").fill("Babelscape/wikineural-multilingual-ner");
    await page.getByRole("button", { name: "Save Settings" }).click();
    await page.waitForTimeout(400);
    await page.getByRole("button", { name: "Diagnose Native Host" }).click();
    await page.waitForTimeout(6000);
    const status = (await page.locator("#status").innerText()).trim();
    console.log(`Playwright popup status: ${status}`);
  } finally {
    await context.close();
  }
}

async function main() {
  try {
    const extensionId = await getExtensionId();
    console.log(`Detected extension ID in Playwright: ${extensionId}`);

    execSync(
      `powershell -ExecutionPolicy Bypass -File ".\\native_host\\install_chrome_host.ps1" -ExtensionId "${extensionId}"`,
      { cwd: repoRoot, stdio: "inherit" }
    );

    await runPopupDiagnosis(extensionId);
  } finally {
    fs.rmSync(userDataDir, { recursive: true, force: true });
  }
}

main().catch((error) => {
  console.error(error);
  process.exit(1);
});
