let latestCapture = null;
const captureBtn = document.getElementById("captureBtn");
const sendMobileBtn = document.getElementById("sendMobileBtn");
const handoffBtn = document.getElementById("handoffBtn");
const serverUrlInput = document.getElementById("serverUrlInput");
const pairingTokenInput = document.getElementById("pairingTokenInput");
const saveMobileConfigBtn = document.getElementById("saveMobileConfigBtn");
const handoffFile = document.getElementById("handoffFile");
const copyBtn = document.getElementById("copyBtn");
const downloadBtn = document.getElementById("downloadBtn");
const clearBtn = document.getElementById("clearBtn");
const statusEl = document.getElementById("status");
const summaryEl = document.getElementById("summary");
const tabListEl = document.getElementById("tabList");
const jsonOutputEl = document.getElementById("jsonOutput");

function setStatus(message, kind = "") {
  statusEl.textContent = message;
  statusEl.className = `status ${kind}`.trim();
}

function renderCapture(capture) {
  summaryEl.textContent = `${capture.context_count} supported tab${capture.context_count === 1 ? "" : "s"} captured.`;
  jsonOutputEl.textContent = prettyJson(capture);
  tabListEl.replaceChildren();

  for (const context of capture.contexts) {
    const card = document.createElement("div");
    card.className = "tab-card";

    const title = document.createElement("div");
    title.className = "tab-title";
    title.textContent = `${context.state.active ? "●" : "○"} ${context.content.title || "Untitled tab"}`;

    const domain = document.createElement("div");
    domain.className = "tab-domain";
    domain.textContent = context.content.domain || "Unknown domain";

    const textInfo = document.createElement("div");
    textInfo.className = "tab-meta";
    textInfo.textContent = context.content.text
      ? `${context.content.text.length} characters of visible text captured`
      : "No page text captured — refresh this tab and capture again";

    card.append(title, domain, textInfo);
    tabListEl.appendChild(card);
  }

  copyBtn.disabled = false;
  downloadBtn.disabled = false;
  sendMobileBtn.disabled = !capture.contexts.length;
}

async function saveMobileConfig(showStatus = true) {
  const rawServerUrl = serverUrlInput.value.trim();
  const pairingToken = pairingTokenInput.value.trim();
  if (!rawServerUrl || !pairingToken) {
    throw new Error("Enter the laptop server address and pairing token.");
  }

  let serverUrl;
  try {
    serverUrl = new URL(rawServerUrl);
  } catch (_error) {
    throw new Error("Enter a valid server address, such as http://192.168.1.20:8000.");
  }
  if (!(["http:", "https:"].includes(serverUrl.protocol)) || serverUrl.pathname !== "/" || serverUrl.search || serverUrl.hash) {
    throw new Error("Use the laptop server's root HTTP or HTTPS address.");
  }

  const config = {
    serverUrl: serverUrl.origin,
    pairingToken
  };
  await chrome.storage.local.set({
    taskflowMobileServerUrl: config.serverUrl,
    taskflowPairingToken: config.pairingToken
  });
  serverUrlInput.value = config.serverUrl;
  if (showStatus) setStatus("Mobile connection saved", "success");
  return config;
}

async function mobileApiRequest(serverUrl, pairingToken, path, options = {}) {
  const response = await fetch(`${serverUrl}${path}`, {
    ...options,
    headers: {
      "X-Taskflow-Token": pairingToken,
      ...(options.body ? { "Content-Type": "application/json" } : {}),
      ...(options.headers || {})
    }
  });
  if (!response.ok) {
    let message = `Laptop server returned ${response.status}.`;
    try {
      const errorBody = await response.json();
      if (typeof errorBody.detail === "string") message = errorBody.detail;
    } catch (_error) {
      // Keep the useful HTTP status when the server has no JSON error body.
    }
    throw new Error(message);
  }
  return response.status === 204 ? null : response.json();
}

async function loadMobileConfig() {
  try {
    const saved = await chrome.storage.local.get([
      "taskflowMobileServerUrl",
      "taskflowPairingToken"
    ]);
    serverUrlInput.value = saved.taskflowMobileServerUrl || "";
    pairingTokenInput.value = saved.taskflowPairingToken || "";
  } catch (error) {
    console.warn("[TaskFlow] Could not load mobile connection settings:", error);
  }
}

saveMobileConfigBtn.addEventListener("click", async () => {
  try {
    await saveMobileConfig();
  } catch (error) {
    setStatus(error.message, "error");
  }
});

sendMobileBtn.addEventListener("click", async () => {
  if (!latestCapture || !latestCapture.contexts.length) return;
  sendMobileBtn.disabled = true;
  setStatus("Finding TaskFlow on Android…", "loading");

  try {
    const config = await saveMobileConfig(false);
    const deviceResponse = await mobileApiRequest(
      config.serverUrl,
      config.pairingToken,
      "/devices"
    );
    const androidDevices = (deviceResponse.devices || [])
      .filter((device) => /taskflow android/i.test(device.device_name || ""))
      .sort((left, right) => right.last_seen - left.last_seen);
    if (!androidDevices.length) {
      throw new Error("Open TaskFlow Android and tap Receive Handoff first.");
    }

    setStatus("Generating and sending activity handoff…", "loading");
    const result = await mobileApiRequest(
      config.serverUrl,
      config.pairingToken,
      "/handoff/generate",
      {
        method: "POST",
        body: JSON.stringify({
          capture: latestCapture,
          target_device_id: androidDevices[0].device_id
        })
      }
    );
    setStatus(
      `Handoff sent: ${result.activity_count} activity, ${result.context_count} context(s).`,
      "success"
    );
  } catch (error) {
    console.error("[TaskFlow] Send to Mobile failed:", error);
    const message = error instanceof TypeError
      ? "Could not reach the laptop server. Check the address, same Wi-Fi, and Windows Firewall."
      : error.message || "Unknown error";
    setStatus(`Send to Mobile failed: ${message}`, "error");
  } finally {
    sendMobileBtn.disabled = !latestCapture?.contexts?.length;
  }
});

loadMobileConfig();

captureBtn.addEventListener("click", async () => {
  captureBtn.disabled = true;
  setStatus("Capturing…", "loading");

  try {
    latestCapture = await captureContextItems();
    renderCapture(latestCapture);
    setStatus("Capture complete", "success");
  } catch (error) {
    console.error("[TaskFlow] Capture failed:", error);
    setStatus(`Capture failed: ${error.message || "Unknown error"}`, "error");
  } finally {
    captureBtn.disabled = false;
  }
});

copyBtn.addEventListener("click", async () => {
  if (!latestCapture) return;
  try {
    await navigator.clipboard.writeText(prettyJson(latestCapture));
    setStatus("JSON copied", "success");
  } catch (error) {
    console.error("[TaskFlow] Copy failed:", error);
    setStatus("Copy failed", "error");
  }
});

downloadBtn.addEventListener("click", () => {
  if (!latestCapture) return;
  try {
    const blob = new Blob([prettyJson(latestCapture)], { type: "application/json" });
    const objectUrl = URL.createObjectURL(blob);
    const anchor = document.createElement("a");
    anchor.href = objectUrl;
    anchor.download = `taskflow-context-${makeDownloadTimestamp(latestCapture.captured_at)}.json`;
    document.body.appendChild(anchor);
    anchor.click();
    anchor.remove();
    setTimeout(() => URL.revokeObjectURL(objectUrl), 0);
    setStatus("JSON downloaded", "success");
  } catch (error) {
    console.error("[TaskFlow] Download failed:", error);
    setStatus("Download failed", "error");
  }
});

clearBtn.addEventListener("click", async () => {
  if (!confirm("Clear all saved tab activity timestamps?")) return;
  try {
    await chrome.storage.local.remove("tabActivity");
    setStatus("Activity history cleared", "success");
  } catch (error) {
    console.error("[TaskFlow] Clear failed:", error);
    setStatus("Could not clear activity history", "error");
  }
});
handoffBtn.addEventListener("click", () => {
  handoffFile.click();
});

handoffFile.addEventListener("change", async () => {
  const file = handoffFile.files[0];
  if (!file) return;

  try {
    const handoffData = JSON.parse(await file.text());

    const activities = handoffData.activities || [];

    if (activities.length === 0) {
      throw new Error("No activities found in this JSON file.");
    }

    const activity = activities[0];

    const contexts = (activity.handoff_packages || [])
      .flatMap(pkg => pkg.contexts || []);

    if (contexts.length === 0) {
      throw new Error("No handoff contexts found for this activity.");
    }

    const response = await chrome.runtime.sendMessage({
      action: "EXECUTE_HANDOFF",
      contexts
    });

    if (!response?.success) {
      throw new Error(response?.error || "Handoff failed.");
    }

    setStatus(`Handoff complete: ${response.opened_tabs} tabs opened.`, "success");
  } catch (error) {
    console.error("[TaskFlow] Handoff failed:", error);
    setStatus(`Handoff failed: ${error.message}`, "error");
  } finally {
    handoffFile.value = "";
  }
});
