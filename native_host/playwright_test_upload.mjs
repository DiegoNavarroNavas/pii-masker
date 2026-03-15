import { chromium } from "playwright";
import { execSync } from "node:child_process";
import os from "node:os";
import path from "node:path";
import fs from "node:fs";

const repoRoot = process.cwd();
const extensionPath = path.join(repoRoot, "chrome_extension");
const userDataDir = fs.mkdtempSync(path.join(os.tmpdir(), "pii-masker-upload-"));
const uploadFilePath = path.join(repoRoot, "document.txt");
const keyFilePath = path.join(repoRoot, "secret.key");

function extensionIdFromServiceWorkerUrl(url) {
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

async function runUploadFlow() {
  const extensionId = await getExtensionId();
  console.log(`Detected extension ID: ${extensionId}`);

  execSync(
    `powershell -ExecutionPolicy Bypass -File ".\\native_host\\install_chrome_host.ps1" -ExtensionId "${extensionId}"`,
    { cwd: repoRoot, stdio: "inherit" }
  );

  const context = await launchWithExtension();
  try {
    let [serviceWorker] = context.serviceWorkers();
    if (!serviceWorker) {
      serviceWorker = await context.waitForEvent("serviceworker", { timeout: 15000 });
    }

    await serviceWorker.evaluate(
      async ({ keyFilePath }) => {
        await chrome.storage.sync.set({
          keyFile: keyFilePath,
          language: "en",
          engine: "transformers",
          includeMapping: false,
          spacyModel: "en_core_web_lg",
          transformersModel: "Babelscape/wikineural-multilingual-ner",
        });
      },
      { keyFilePath }
    );

    const page = await context.newPage();
    const targetUrl = `file:///${path.join(repoRoot, "tests", "upload_test.html").replace(/\\/g, "/")}`;
    await page.goto(targetUrl);
    await page.locator("#upload").click();
    await page.locator("#upload").setInputFiles(uploadFilePath);
    await page.bringToFront();

    const response = await serviceWorker.evaluate(async () => {
      const [tab] = await chrome.tabs.query({ active: true, currentWindow: true });
      return chrome.tabs.sendMessage(tab.id, { type: "RUN_MANUAL_REDACTION" });
    });

    console.log("Content-script response:", response);
    if (!response?.ok) {
      throw new Error(`Redaction failed: ${response?.error || "unknown error"}`);
    }

    const selectedName = await page.locator("#upload").evaluate((el) => {
      const input = el;
      return input.files && input.files.length ? input.files[0].name : "";
    });
    console.log(`Selected file after redaction: ${selectedName}`);
    if (!selectedName.includes(".redacted")) {
      throw new Error(`Expected redacted filename, got: ${selectedName}`);
    }
    console.log("Playwright upload test: PASS");
  } finally {
    await context.close();
  }
}

runUploadFlow()
  .catch((error) => {
    console.error(error);
    process.exitCode = 1;
  })
  .finally(() => {
    fs.rmSync(userDataDir, { recursive: true, force: true });
  });
