let activeFileInput = null;

function showToast(message, isError = false) {
  const toast = document.createElement("div");
  toast.textContent = message;
  toast.style.position = "fixed";
  toast.style.zIndex = "2147483647";
  toast.style.right = "16px";
  toast.style.bottom = "16px";
  toast.style.padding = "10px 14px";
  toast.style.borderRadius = "6px";
  toast.style.fontSize = "12px";
  toast.style.color = "#fff";
  toast.style.background = isError ? "#b91c1c" : "#15803d";
  toast.style.boxShadow = "0 4px 12px rgba(0,0,0,0.2)";
  document.body.appendChild(toast);
  setTimeout(() => toast.remove(), 2600);
}

function rememberFileInput(target) {
  if (target && target.tagName === "INPUT" && target.type === "file") {
    activeFileInput = target;
  }
}

document.addEventListener("click", (event) => {
  rememberFileInput(event.target);
});

document.addEventListener("focusin", (event) => {
  rememberFileInput(event.target);
});

function fileToBase64(file) {
  return new Promise((resolve, reject) => {
    const reader = new FileReader();
    reader.onload = () => {
      const dataUrl = reader.result;
      if (typeof dataUrl !== "string") {
        reject(new Error("Failed to read selected file"));
        return;
      }
      const idx = dataUrl.indexOf(",");
      resolve(dataUrl.slice(idx + 1));
    };
    reader.onerror = () => reject(new Error("FileReader read error"));
    reader.readAsDataURL(file);
  });
}

function base64ToBytes(base64) {
  const binary = atob(base64);
  const bytes = new Uint8Array(binary.length);
  for (let i = 0; i < binary.length; i += 1) {
    bytes[i] = binary.charCodeAt(i);
  }
  return bytes;
}

function replaceInputFile(inputEl, newFile) {
  const transfer = new DataTransfer();
  transfer.items.add(newFile);
  inputEl.files = transfer.files;
  inputEl.dispatchEvent(new Event("change", { bubbles: true }));
}

function notifyProgress(requestId, stage) {
  if (!requestId) {
    return;
  }
  chrome.runtime.sendMessage({
    type: "MANUAL_REDACTION_PROGRESS",
    requestId,
    stage,
  }).catch(() => {});
}

async function redactActiveUpload(requestId) {
  if (!activeFileInput) {
    throw new Error("No file input selected. Click an upload field first.");
  }
  if (!activeFileInput.files || activeFileInput.files.length === 0) {
    throw new Error("Selected upload input has no file.");
  }

  const file = activeFileInput.files[0];
  const contentBase64 = await fileToBase64(file);
  const jobId = crypto.randomUUID();
  notifyProgress(requestId, "processing_started");
  const response = await chrome.runtime.sendMessage({
    type: "REDACT_UPLOAD_FILE",
    jobId,
    fileName: file.name,
    mimeType: file.type || "application/octet-stream",
    contentBase64,
  });

  if (!response || !response.ok) {
    throw new Error(response?.error?.message || "Background request failed");
  }

  const nativeResponse = response.nativeResponse;
  if (!nativeResponse.ok) {
    const code = nativeResponse.error?.code || "UNKNOWN";
    const message = nativeResponse.error?.message || "Native host redaction failed";
    throw new Error(`${code}: ${message}`);
  }

  const bytes = base64ToBytes(nativeResponse.contentBase64);
  const outName = nativeResponse.fileName || file.name;
  const outType = nativeResponse.mimeType || file.type || "application/octet-stream";
  const redactedFile = new File([bytes], outName, { type: outType });
  replaceInputFile(activeFileInput, redactedFile);
  showToast(`Redacted: ${outName}`);
}

chrome.runtime.onMessage.addListener((message, _sender, sendResponse) => {
  if (!message || message.type !== "RUN_MANUAL_REDACTION") {
    return false;
  }

  redactActiveUpload(message.requestId)
    .then(() => sendResponse({ ok: true }))
    .catch((error) => {
      const msg = String(error && error.message ? error.message : error);
      showToast(msg, true);
      sendResponse({ ok: false, error: msg });
    });

  return true;
});
