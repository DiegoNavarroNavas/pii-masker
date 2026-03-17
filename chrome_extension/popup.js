const DEFAULT_ENGINE = "transformers";
const DEFAULT_TRANSFORMERS_MODEL = "Babelscape/wikineural-multilingual-ner";
const DEFAULT_LOCAL_MODEL_PATH = "local_models/multihead_model.pt";
const DEFAULT_LOCAL_ENCODER_MODEL = "answerdotai/ModernBERT-base";
const SETTINGS_VERSION = 4;
let pendingRequestId = null;

function status(message, state = "ok") {
  const el = document.getElementById("status");
  el.textContent = message;
  el.className = `status ${state}`;
}

function toFriendlyHostError(message) {
  const text = String(message || "");
  if (text.includes("Specified native messaging host not found")) {
    return "Companion app is not installed. Install/repair the native host package, then retry.";
  }
  if (text.includes("missing version metadata")) {
    return "Companion app is outdated. Reinstall or upgrade it, then retry.";
  }
  if (text.includes("too old")) {
    return text;
  }
  return text;
}

function setRunButtonBusy(isBusy, label = "Processing requested") {
  const btn = document.getElementById("runRedaction");
  if (!btn) {
    return;
  }
  btn.disabled = isBusy;
  btn.textContent = isBusy ? label : "Redact Selected Upload";
}

function defaults() {
  return {
    keyFile: "",
    language: "en",
    engine: DEFAULT_ENGINE,
    spacyModel: "",
    transformersModel: DEFAULT_TRANSFORMERS_MODEL,
    localModelPath: DEFAULT_LOCAL_MODEL_PATH,
    localEncoderModel: DEFAULT_LOCAL_ENCODER_MODEL,
    settingsVersion: SETTINGS_VERSION,
    includeMapping: false,
  };
}

const ENGINE_GROUPS = ["spacy", "transformers", "local_multihead"];

function updateEngineVisibility(engine) {
  for (const key of ENGINE_GROUPS) {
    const el = document.getElementById(`group-${key}`);
    if (el) {
      el.style.display = engine === key ? "" : "none";
    }
  }
}

function loadSettings() {
  chrome.storage.sync.get(defaults(), (data) => {
    document.getElementById("keyFile").value = data.keyFile || "";
    const engine = data.engine || DEFAULT_ENGINE;
    document.getElementById("language").value = data.language || "en";
    document.getElementById("engine").value = engine;
    document.getElementById("spacyModel").value = data.spacyModel || "";
    document.getElementById("transformersModel").value =
      data.transformersModel || DEFAULT_TRANSFORMERS_MODEL;
    document.getElementById("localModelPath").value =
      data.localModelPath || DEFAULT_LOCAL_MODEL_PATH;
    document.getElementById("localEncoderModel").value =
      data.localEncoderModel || DEFAULT_LOCAL_ENCODER_MODEL;
    document.getElementById("includeMapping").checked = Boolean(data.includeMapping);
    updateEngineVisibility(engine);
  });
}

function saveSettings() {
  const payload = {
    keyFile: document.getElementById("keyFile").value.trim(),
    language: document.getElementById("language").value,
    engine: document.getElementById("engine").value,
    spacyModel: document.getElementById("spacyModel").value.trim(),
    transformersModel: document.getElementById("transformersModel").value.trim(),
    localModelPath: document.getElementById("localModelPath").value.trim(),
    localEncoderModel: document.getElementById("localEncoderModel").value.trim(),
    settingsVersion: SETTINGS_VERSION,
    includeMapping: document.getElementById("includeMapping").checked,
  };
  chrome.storage.sync.set(payload, () => {
    if (chrome.runtime.lastError) {
      status(chrome.runtime.lastError.message, "error");
      return;
    }
    status("Settings saved", "ok");
  });
}

async function refreshVaultOutputPath() {
  const outputEl = document.getElementById("vaultOutputPath");
  if (!outputEl) {
    return;
  }
  outputEl.value = "Checking...";
  try {
    const response = await chrome.runtime.sendMessage({
      type: "GET_VAULT_OUTPUT_PATH",
      jobId: `vault-path-${Date.now()}`,
    });
    if (!response) {
      throw new Error("Popup and background are out of sync. Reload the extension, then retry.");
    }
    if (!response?.ok) {
      throw new Error(response?.error?.message || "Could not load vault output path");
    }
    const nativeResponse = response.nativeResponse;
    if (!nativeResponse?.ok) {
      const code = nativeResponse?.error?.code || "UNKNOWN";
      const message = nativeResponse?.error?.message || "Host returned an error";
      throw new Error(`${code}: ${message}`);
    }
    const path = nativeResponse.vaultDirectory || "";
    outputEl.value = path;
    if (nativeResponse.exists) {
      status("Vault output path loaded", "ok");
    } else {
      status("Vault output path loaded (directory will be created on first save)", "pending");
    }
  } catch (error) {
    outputEl.value = "";
    status(toFriendlyHostError(String(error && error.message ? error.message : error)), "error");
  }
}

async function runManualRedaction() {
  try {
    const requestId = crypto.randomUUID();
    pendingRequestId = requestId;
    setRunButtonBusy(true);
    status("Processing requested", "pending");

    const [tab] = await chrome.tabs.query({ active: true, currentWindow: true });
    if (!tab || !tab.id) {
      throw new Error("No active tab");
    }

    const isRestricted = tab.url && /^(chrome|edge|about|chrome-extension):/i.test(tab.url);
    if (isRestricted) {
      throw new Error("Open a normal website tab (not chrome:// or extension pages).");
    }

    let response;
    try {
      response = await chrome.tabs.sendMessage(tab.id, {
        type: "RUN_MANUAL_REDACTION",
        requestId,
      });
    } catch (firstError) {
      const message = String(firstError && firstError.message ? firstError.message : firstError);
      const missingReceiver = message.includes("Receiving end does not exist");
      if (!missingReceiver) {
        throw firstError;
      }

      await chrome.scripting.executeScript({
        target: { tabId: tab.id },
        files: ["content.js"],
      });
      response = await chrome.tabs.sendMessage(tab.id, {
        type: "RUN_MANUAL_REDACTION",
        requestId,
      });
    }

    if (!response?.ok) {
      throw new Error(response?.error || "Redaction failed");
    }
    pendingRequestId = null;
    setRunButtonBusy(false);
    status("Redaction completed", "ok");
  } catch (error) {
    pendingRequestId = null;
    setRunButtonBusy(false);
    status(toFriendlyHostError(String(error && error.message ? error.message : error)), "error");
  }
}

async function diagnoseNativeHost() {
  try {
    const response = await chrome.runtime.sendMessage({ type: "DIAG_NATIVE_HOST" });
    if (!response?.ok) {
      throw new Error(response?.error?.message || "Native host diagnostic failed");
    }
    const nativeResponse = response.nativeResponse;
    if (!nativeResponse?.ok) {
      const code = nativeResponse.error?.code || "UNKNOWN";
      const message = nativeResponse.error?.message || "Host returned error";
      status(`Host reachable: ${code} - ${message}`, "error");
      return;
    }
    status("Host reachable: diagnostic call succeeded", "ok");
  } catch (error) {
    status(
      `Host unreachable: ${toFriendlyHostError(String(error && error.message ? error.message : error))}`,
      "error"
    );
  }
}

chrome.runtime.onMessage.addListener((message) => {
  if (!message || message.type !== "MANUAL_REDACTION_PROGRESS") {
    return false;
  }

  if (!pendingRequestId || message.requestId !== pendingRequestId) {
    return false;
  }

  if (message.stage === "processing_started") {
    setRunButtonBusy(true, "Processing started");
    status("Processing started", "pending");
  }

  return false;
});

document.addEventListener("DOMContentLoaded", () => {
  loadSettings();
  document.getElementById("engine").addEventListener("change", (e) => updateEngineVisibility(e.target.value));
  document.getElementById("saveSettings").addEventListener("click", saveSettings);
  document.getElementById("runRedaction").addEventListener("click", runManualRedaction);
  document.getElementById("refreshVaultPath").addEventListener("click", refreshVaultOutputPath);
  document.getElementById("diagnoseHost").addEventListener("click", diagnoseNativeHost);
  refreshVaultOutputPath();
});
