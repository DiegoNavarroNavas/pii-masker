import fs from "node:fs";
import os from "node:os";
import path from "node:path";
import { execFileSync, execSync } from "node:child_process";
import puppeteer from "puppeteer";

function resolveRepoRoot() {
  const cwd = process.cwd();
  if (
    fs.existsSync(path.join(cwd, "chrome_extension")) &&
    fs.existsSync(path.join(cwd, "scripts", "release", "linux", "install_native_host.sh"))
  ) {
    return cwd;
  }
  const parent = path.resolve(cwd, "..");
  if (
    fs.existsSync(path.join(parent, "chrome_extension")) &&
    fs.existsSync(path.join(parent, "scripts", "release", "linux", "install_native_host.sh"))
  ) {
    return parent;
  }
  return cwd;
}

const repoRoot = resolveRepoRoot();
const extensionPath = path.join(repoRoot, "chrome_extension");
const keyFilePath = path.join(repoRoot, "secret.key");
const userDataDir = fs.mkdtempSync(path.join(os.tmpdir(), "pii-masker-ptr-"));
const browserTarget = process.env.BROWSER_TARGET || "chrome";
const hostPath = process.env.HOST_PATH || "./results/release/linux/bin/host";
const extensionIdOverride = (process.env.EXTENSION_ID || "").trim();
const useInstalledExtension =
  String(process.env.USE_INSTALLED_EXTENSION || "").toLowerCase() === "1" ||
  String(process.env.USE_INSTALLED_EXTENSION || "").toLowerCase() === "true";

function flatpakConfig(target) {
  if (target === "chrome") {
    return { appId: "com.google.Chrome", command: "chrome" };
  }
  if (target === "chromium") {
    return { appId: "org.chromium.Chromium", command: "chromium" };
  }
  if (target === "brave") {
    return { appId: "com.brave.Browser", command: "brave" };
  }
  return null;
}

function flatpakAppInstalled(appId) {
  try {
    execSync(`flatpak info ${appId}`, { stdio: "ignore" });
    return true;
  } catch {
    return false;
  }
}

function makeFlatpakWrapper(target) {
  const config = flatpakConfig(target);
  if (!config || !flatpakAppInstalled(config.appId)) {
    return null;
  }
  const wrapperPath = path.join(
    os.tmpdir(),
    `pii-masker-flatpak-${target}-${Date.now()}.sh`
  );
  const script = [
    "#!/usr/bin/env bash",
    "set -euo pipefail",
    `exec flatpak run --filesystem="${repoRoot}" --filesystem="${os.tmpdir()}" --command=${config.command} ${config.appId} "$@"`,
    "",
  ].join("\n");
  fs.writeFileSync(wrapperPath, script, { encoding: "utf-8", mode: 0o700 });
  return wrapperPath;
}

function flatpakExtensionsDir(target) {
  if (target === "chrome") {
    return path.join(
      os.homedir(),
      ".var",
      "app",
      "com.google.Chrome",
      "config",
      "google-chrome",
      "Default",
      "Extensions"
    );
  }
  if (target === "chromium") {
    return path.join(
      os.homedir(),
      ".var",
      "app",
      "org.chromium.Chromium",
      "config",
      "chromium",
      "Default",
      "Extensions"
    );
  }
  if (target === "brave") {
    return path.join(
      os.homedir(),
      ".var",
      "app",
      "com.brave.Browser",
      "config",
      "BraveSoftware",
      "Brave-Browser",
      "Default",
      "Extensions"
    );
  }
  return null;
}

function flatpakPreferencesPath(target) {
  if (target === "chrome") {
    return path.join(
      os.homedir(),
      ".var",
      "app",
      "com.google.Chrome",
      "config",
      "google-chrome",
      "Default",
      "Preferences"
    );
  }
  if (target === "chromium") {
    return path.join(
      os.homedir(),
      ".var",
      "app",
      "org.chromium.Chromium",
      "config",
      "chromium",
      "Default",
      "Preferences"
    );
  }
  if (target === "brave") {
    return path.join(
      os.homedir(),
      ".var",
      "app",
      "com.brave.Browser",
      "config",
      "BraveSoftware",
      "Brave-Browser",
      "Default",
      "Preferences"
    );
  }
  return null;
}

function flatpakUserDataDir(target) {
  if (target === "chrome") {
    return path.join(
      os.homedir(),
      ".var",
      "app",
      "com.google.Chrome",
      "config",
      "google-chrome"
    );
  }
  if (target === "chromium") {
    return path.join(
      os.homedir(),
      ".var",
      "app",
      "org.chromium.Chromium",
      "config",
      "chromium"
    );
  }
  if (target === "brave") {
    return path.join(
      os.homedir(),
      ".var",
      "app",
      "com.brave.Browser",
      "config",
      "BraveSoftware",
      "Brave-Browser"
    );
  }
  return null;
}

function hasExtensionInPreferences(target, extensionId) {
  const prefsPath = flatpakPreferencesPath(target);
  if (!prefsPath || !fs.existsSync(prefsPath)) {
    return false;
  }
  try {
    const data = JSON.parse(fs.readFileSync(prefsPath, "utf-8"));
    return Boolean(
      data &&
        data.extensions &&
        data.extensions.settings &&
        data.extensions.settings[extensionId]
    );
  } catch {
    return false;
  }
}

function extensionIdFromUrl(url) {
  const parts = String(url).split("/");
  return parts.length >= 3 ? parts[2] : "";
}

async function waitForExtensionId(browser, timeoutMs = 15000) {
  const start = Date.now();
  while (Date.now() - start < timeoutMs) {
    const targets = browser.targets();
    for (const target of targets) {
      const url = target.url();
      if (target.type() === "service_worker" && url.startsWith("chrome-extension://")) {
        const id = extensionIdFromUrl(url);
        if (id) {
          return id;
        }
      }
    }
    await new Promise((resolve) => setTimeout(resolve, 250));
  }
  throw new Error("Could not detect extension service worker ID");
}

function installManifest(extensionId) {
  execFileSync(
    "bash",
    ["./scripts/release/linux/install_native_host.sh", hostPath, extensionId, browserTarget],
    { cwd: repoRoot, stdio: "inherit" }
  );
}

async function runPopupDiagnosis(browser, extensionId) {
  const pages = await browser.pages();
  const page = pages.length ? pages[0] : await browser.newPage();
  await page.goto(`chrome-extension://${extensionId}/popup.html`);
  await page.waitForSelector("#keyFile");
  await page.$eval("#keyFile", (el, value) => {
    el.value = value;
    el.dispatchEvent(new Event("input", { bubbles: true }));
  }, keyFilePath);
  await page.select("#language", "en");
  await page.select("#engine", "transformers");
  await page.click("#saveSettings");
  await new Promise((resolve) => setTimeout(resolve, 400));
  await page.click("#diagnoseHost");
  await page.waitForSelector("#status");
  await new Promise((resolve) => setTimeout(resolve, 4000));
  const status = await page.$eval("#status", (el) => el.textContent?.trim() || "");
  console.log(`Puppeteer popup status: ${status}`);
}

async function waitForExtensionWorker(browser, extensionId, timeoutMs = 15000) {
  const start = Date.now();
  while (Date.now() - start < timeoutMs) {
    for (const target of browser.targets()) {
      if (target.type() !== "service_worker") {
        continue;
      }
      const url = String(target.url() || "");
      if (url.startsWith(`chrome-extension://${extensionId}/`)) {
        return target;
      }
    }
    await new Promise((resolve) => setTimeout(resolve, 250));
  }
  return null;
}

async function runServiceWorkerDiagnosis(browser, extensionId) {
  const target = await waitForExtensionWorker(browser, extensionId);
  if (!target) {
    throw new Error(
      `Could not find extension service worker for ${extensionId}. ` +
        "Ensure the extension is enabled for this profile."
    );
  }
  const worker = await target.worker();
  if (!worker) {
    throw new Error("Found extension service worker target but could not attach.");
  }
  const result = await worker.evaluate(async () => {
    return new Promise((resolve) => {
      try {
        chrome.runtime.sendMessage({ type: "DIAG_NATIVE_HOST" }, (response) => {
          const runtimeError = chrome.runtime.lastError;
          if (runtimeError) {
            resolve({ ok: false, error: runtimeError.message });
            return;
          }
          resolve(response || { ok: false, error: "No response payload" });
        });
      } catch (error) {
        resolve({ ok: false, error: String(error && error.message ? error.message : error) });
      }
    });
  });
  console.log(`Service-worker diagnostic response: ${JSON.stringify(result)}`);
}

async function runDiagnosis() {
  const cleanupPaths = [];
  if (useInstalledExtension && extensionIdOverride) {
    const dir = flatpakExtensionsDir(browserTarget);
    const inExtensionsDir =
      Boolean(dir && fs.existsSync(dir) && fs.readdirSync(dir).includes(extensionIdOverride));
    const inPreferences = hasExtensionInPreferences(browserTarget, extensionIdOverride);
    if (!inExtensionsDir && !inPreferences) {
      throw new Error(
        `Extension ID ${extensionIdOverride} was not found in Flatpak browser profile metadata. ` +
          "Install/enable the extension in that browser profile first, or remove USE_INSTALLED_EXTENSION."
      );
    }
  }
  const launchArgs = [
    "--no-sandbox",
    "--disable-setuid-sandbox",
    "--disable-dev-shm-usage",
    "--disable-crash-reporter",
    "--disable-crashpad",
    "--no-first-run",
  ];
  if (!useInstalledExtension) {
    launchArgs.push(`--disable-extensions-except=${extensionPath}`);
    launchArgs.push(`--load-extension=${extensionPath}`);
  } else {
    launchArgs.push("--profile-directory=Default");
  }
  const launchOptions = {
    headless: false,
    args: launchArgs,
  };
  if (!useInstalledExtension) {
    launchOptions.userDataDir = userDataDir;
  } else {
    const installedProfileDir = flatpakUserDataDir(browserTarget);
    if (installedProfileDir) {
      const lockPath = path.join(installedProfileDir, "SingletonLock");
      if (fs.existsSync(lockPath)) {
        throw new Error(
          `Browser profile appears in use at ${installedProfileDir} (SingletonLock exists). ` +
            "Close all browser windows for that Flatpak app and retry."
        );
      }
      launchOptions.userDataDir = installedProfileDir;
    }
  }
  if (process.env.PUPPETEER_EXECUTABLE_PATH) {
    launchOptions.executablePath = process.env.PUPPETEER_EXECUTABLE_PATH;
    console.log(`Using browser binary: ${process.env.PUPPETEER_EXECUTABLE_PATH}`);
  } else {
    const flatpakWrapper = makeFlatpakWrapper(browserTarget);
    if (flatpakWrapper) {
      launchOptions.executablePath = flatpakWrapper;
      launchOptions.pipe = true;
      cleanupPaths.push(flatpakWrapper);
      console.log(`Using Flatpak browser wrapper: ${flatpakWrapper}`);
    } else {
      console.log("Using Puppeteer-managed Chrome binary.");
    }
  }
  let browser;
  try {
    browser = await puppeteer.launch(launchOptions);
  } catch (error) {
    if (!process.env.PUPPETEER_EXECUTABLE_PATH) {
      throw new Error(
        `Failed to launch Puppeteer-managed Chrome. ` +
          `Try setting PUPPETEER_EXECUTABLE_PATH to your browser binary ` +
          `(or set BROWSER_TARGET to a Flatpak browser you have installed).\n` +
          String(error && error.message ? error.message : error)
      );
    }
    throw error;
  }
  try {
    const extensionId = extensionIdOverride || (await waitForExtensionId(browser));
    if (useInstalledExtension) {
      console.log("Using installed browser profile extension.");
    } else {
      console.log("Using unpacked extension from repository.");
    }
    if (extensionIdOverride) {
      console.log(`Using EXTENSION_ID override: ${extensionId}`);
    } else {
      console.log(`Detected extension ID: ${extensionId}`);
    }
    installManifest(extensionId);
    try {
      await runPopupDiagnosis(browser, extensionId);
    } catch (error) {
      const message = String(error && error.message ? error.message : error);
      if (!message.includes("ERR_BLOCKED_BY_CLIENT")) {
        throw error;
      }
      console.log(
        "Popup navigation blocked by client policy; falling back to service-worker diagnosis."
      );
      await runServiceWorkerDiagnosis(browser, extensionId);
    }
  } finally {
    await browser.close();
    for (const cleanupPath of cleanupPaths) {
      fs.rmSync(cleanupPath, { force: true });
    }
  }
}

async function main() {
  await runDiagnosis();
}

main()
  .catch((error) => {
    console.error(error);
    process.exitCode = 1;
  })
  .finally(() => {
    fs.rmSync(userDataDir, { recursive: true, force: true });
  });
