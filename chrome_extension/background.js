const NATIVE_HOST_NAME = "com.pii_masker.host";
const PROTOCOL_VERSION = 1;
const MIN_HOST_VERSION = "0.2.0";
const DEFAULT_ENGINE = "transformers";
const DEFAULT_TRANSFORMERS_MODEL = "Babelscape/wikineural-multilingual-ner";
const DEFAULT_LOCAL_MODEL_PATH = "local_models/multihead_model.pt";
const DEFAULT_LOCAL_ENCODER_MODEL = "answerdotai/ModernBERT-base";
const SETTINGS_VERSION = 4;

function getDefaults() {
  return {
    language: "en",
    engine: DEFAULT_ENGINE,
    spacyModel: "",
    transformersModel: DEFAULT_TRANSFORMERS_MODEL,
    localModelPath: DEFAULT_LOCAL_MODEL_PATH,
    localEncoderModel: DEFAULT_LOCAL_ENCODER_MODEL,
    settingsVersion: SETTINGS_VERSION,
    keyFile: "",
    includeMapping: false,
  };
}

function resolveModelForEngine(settings) {
  const engine = settings.engine || DEFAULT_ENGINE;
  if (engine === "transformers") {
    const model = typeof settings.transformersModel === "string"
      ? settings.transformersModel.trim()
      : "";
    return model || DEFAULT_TRANSFORMERS_MODEL;
  }
  if (engine === "spacy") {
    const model = typeof settings.spacyModel === "string" ? settings.spacyModel.trim() : "";
    return model || undefined;
  }
  if (engine === "local_multihead") {
    const model = typeof settings.localModelPath === "string" ? settings.localModelPath.trim() : "";
    return model || DEFAULT_LOCAL_MODEL_PATH;
  }
  return undefined;
}

async function getSettings() {
  return new Promise((resolve) => {
    chrome.storage.sync.get(getDefaults(), (result) => {
      const isLegacySettings = (result.settingsVersion || 0) < SETTINGS_VERSION;
      if (!isLegacySettings) {
        resolve(result);
        return;
      }

      const migrated = { ...result, settingsVersion: SETTINGS_VERSION };
      const previousModel = typeof migrated.model === "string" ? migrated.model.trim() : "";
      if (typeof migrated.spacyModel !== "string") {
        migrated.spacyModel = "";
      }
      if (typeof migrated.transformersModel !== "string") {
        migrated.transformersModel = DEFAULT_TRANSFORMERS_MODEL;
      }
      if (typeof migrated.localModelPath !== "string") {
        migrated.localModelPath = DEFAULT_LOCAL_MODEL_PATH;
      }
      if (typeof migrated.localEncoderModel !== "string") {
        migrated.localEncoderModel = DEFAULT_LOCAL_ENCODER_MODEL;
      }
      if (previousModel) {
        if ((migrated.engine || DEFAULT_ENGINE) === "spacy" && !migrated.spacyModel.trim()) {
          migrated.spacyModel = previousModel;
        }
        if ((migrated.engine || DEFAULT_ENGINE) === "transformers" && !migrated.transformersModel.trim()) {
          migrated.transformersModel = previousModel;
        }
      }
      delete migrated.model;

      chrome.storage.sync.set(migrated, () => resolve(migrated));
    });
  });
}

function sendNative(requestPayload) {
  return new Promise((resolve, reject) => {
    chrome.runtime.sendNativeMessage(NATIVE_HOST_NAME, requestPayload, (response) => {
      const runtimeError = chrome.runtime.lastError;
      if (runtimeError) {
        reject(new Error(runtimeError.message));
        return;
      }
      if (!response) {
        reject(new Error("No response from native host"));
        return;
      }
      resolve(response);
    });
  });
}

function parseSemver(value) {
  if (typeof value !== "string") {
    return null;
  }
  const parts = value.trim().split(".");
  if (parts.length !== 3) {
    return null;
  }
  const parsed = parts.map((part) => Number.parseInt(part, 10));
  if (parsed.some((valuePart) => Number.isNaN(valuePart) || valuePart < 0)) {
    return null;
  }
  return parsed;
}

function isHostCompatible(hostVersion, minVersion) {
  const host = parseSemver(hostVersion);
  const min = parseSemver(minVersion);
  if (!host || !min) {
    return false;
  }
  for (let idx = 0; idx < 3; idx += 1) {
    if (host[idx] > min[idx]) {
      return true;
    }
    if (host[idx] < min[idx]) {
      return false;
    }
  }
  return true;
}

function assertCompatibleHost(response) {
  const hostVersion = response && typeof response.hostVersion === "string"
    ? response.hostVersion
    : "";
  if (!hostVersion) {
    throw new Error(
      `Native host is missing version metadata. Please reinstall/upgrade the companion app (need >= ${MIN_HOST_VERSION}).`
    );
  }
  if (!isHostCompatible(hostVersion, MIN_HOST_VERSION)) {
    throw new Error(
      `Native host ${hostVersion} is too old. Please upgrade to ${MIN_HOST_VERSION} or later.`
    );
  }
}

chrome.runtime.onMessage.addListener((message, _sender, sendResponse) => {
  if (message && message.type === "DIAG_NATIVE_HOST") {
    (async () => {
      try {
        const settings = await getSettings();
        const nativeRequest = {
          version: PROTOCOL_VERSION,
          action: "redact_upload",
          jobId: `diag-${Date.now()}`,
          fileName: "diag.txt",
          mimeType: "text/plain",
          contentBase64: "dGVzdA==",
          language: settings.language || "en",
          engine: settings.engine || DEFAULT_ENGINE,
          spacyModel: settings.spacyModel || "",
          transformersModel: settings.transformersModel || DEFAULT_TRANSFORMERS_MODEL,
          localEncoderModel: settings.localEncoderModel || DEFAULT_LOCAL_ENCODER_MODEL,
          keyFile: settings.keyFile || "C:\\invalid\\missing.key",
          minHostVersion: MIN_HOST_VERSION,
          includeMapping: false,
        };
        const resolvedModel = resolveModelForEngine(settings);
        if (resolvedModel) {
          nativeRequest.model = resolvedModel;
        }
        const response = await sendNative(nativeRequest);
        assertCompatibleHost(response);
        sendResponse({ ok: true, nativeResponse: response });
      } catch (error) {
        sendResponse({
          ok: false,
          error: {
            code: "NATIVE_DIAG_FAILURE",
            message: String(error && error.message ? error.message : error),
          },
        });
      }
    })();
    return true;
  }

  if (!message || message.type !== "REDACT_UPLOAD_FILE") {
    return false;
  }

  (async () => {
    try {
      const settings = await getSettings();
      if (!settings.keyFile || !settings.keyFile.trim()) {
        throw new Error("Set key file path in extension popup before redacting.");
      }

      const nativeRequest = {
        version: PROTOCOL_VERSION,
        action: "redact_upload",
        jobId: message.jobId,
        fileName: message.fileName,
        mimeType: message.mimeType,
        contentBase64: message.contentBase64,
        language: settings.language || "en",
        engine: settings.engine || DEFAULT_ENGINE,
        spacyModel: settings.spacyModel || "",
        transformersModel: settings.transformersModel || DEFAULT_TRANSFORMERS_MODEL,
        localEncoderModel: settings.localEncoderModel || DEFAULT_LOCAL_ENCODER_MODEL,
        keyFile: settings.keyFile,
        minHostVersion: MIN_HOST_VERSION,
        includeMapping: Boolean(settings.includeMapping),
      };
      const resolvedModel = resolveModelForEngine(settings);
      if (resolvedModel) {
        nativeRequest.model = resolvedModel;
      }

      const response = await sendNative(nativeRequest);
      assertCompatibleHost(response);
      sendResponse({ ok: true, nativeResponse: response });
    } catch (error) {
      sendResponse({
        ok: false,
        error: {
          code: "BACKGROUND_FAILURE",
          message: String(error && error.message ? error.message : error),
        },
      });
    }
  })();

  return true;
});
