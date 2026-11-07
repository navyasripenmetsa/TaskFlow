let latestCapture = null;
let latestHandoffData = null;

const PROCESSING_API_URL = "http://127.0.0.1:8000/process-contexts";

const activitiesSection = document.getElementById("activitiesSection");
const activityListEl = document.getElementById("activityList");
const activitySelect = document.getElementById("activitySelect");
const selectedActivityInfo = document.getElementById("selectedActivityInfo");
const captureBtn = document.getElementById("captureBtn");
const handoffBtn = document.getElementById("handoffBtn");
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
  summaryEl.textContent =
    `${capture.context_count} supported tab${capture.context_count === 1 ? "" : "s"} captured.`;

  jsonOutputEl.textContent = prettyJson(capture);
  tabListEl.replaceChildren();

  for (const context of capture.contexts) {
    const card = document.createElement("div");
    card.className = "tab-card";

    const title = document.createElement("div");
    title.className = "tab-title";
    title.textContent =
      `${context.state.active ? "●" : "○"} ${context.content.title || "Untitled tab"}`;

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
}
function getActivityContexts(activity) {
  const sourcePackage =
    activity.handoff_package ||
    activity.activity_handoff_package;

  return Array.isArray(sourcePackage?.contexts)
    ? sourcePackage.contexts
    : (activity.handoff_packages || [])
        .flatMap(pkg => pkg.contexts || []);
}

function updateSelectedActivityInfo() {
  const activities = latestHandoffData?.activities || [];
  const selectedIndex = Number(activitySelect.value);

  const activity = activities[selectedIndex];

  if (!activity || !Number.isInteger(selectedIndex)) {
    selectedActivityInfo.textContent = "No activity selected.";
    return;
  }

  const contexts = getActivityContexts(activity);

  selectedActivityInfo.textContent =
    `${activity.label || "Selected activity"} — ${contexts.length} context(s) will be sent.`;
}
function renderActivities(result) {
  activityListEl.replaceChildren();

  const activities = result.activities || [];

activitiesSection.hidden = false;

// Populate the activity dropdown.
activitySelect.replaceChildren();

if (activities.length === 0) {
  const option = document.createElement("option");
  option.value = "";
  option.textContent = "No activities available";
  activitySelect.appendChild(option);

  selectedActivityInfo.textContent = "No activity selected.";
} else {
  activities.forEach((activity, index) => {
    const option = document.createElement("option");

    option.value = String(index);
    option.textContent = activity.label || `Activity ${index + 1}`;

    activitySelect.appendChild(option);
  });

  activitySelect.value = "0";
  updateSelectedActivityInfo();
}

  if (activities.length === 0) {
    activityListEl.textContent = "No activities discovered.";
    return;
  }

  for (const activity of activities) {
    const card = document.createElement("div");
    card.className = "activity-card";

    const title = document.createElement("div");
    title.className = "activity-title";
    title.textContent = activity.label || "Untitled activity";

    const description = document.createElement("div");
    description.className = "activity-description";

    description.textContent =
      activity.description || "No description available.";

    const meta = document.createElement("div");
    meta.className = "activity-meta";

    const tags = [
      `${activity.task_ids?.length || 0} tasks`,
      `${activity.optimization?.context_count || 0} original contexts`,
      `${activity.optimization?.selected_context_count || 0} selected contexts`,
      `Coherence: ${Number(activity.coherence || 0).toFixed(2)}`
    ];

    for (const value of tags) {
      const tag = document.createElement("span");
      tag.className = "activity-tag";
      tag.textContent = value;
      meta.appendChild(tag);
    }

    const ready = document.createElement("div");
    ready.className = "activity-ready";

    ready.textContent = activity.ready_for_handoff
      ? "✓ Ready for handoff"
      : "Not ready for handoff";

    card.append(title, description, meta, ready);
    activityListEl.appendChild(card);
  }
}

// --------------------------------------------------
// Capture and process browser contexts
// --------------------------------------------------

captureBtn.addEventListener("click", async () => {
  captureBtn.disabled = true;

  activitiesSection.hidden = true;
  activityListEl.replaceChildren();

  setStatus("Capturing browser contexts...", "loading");

  try {
    // 1. Capture Chrome contexts.
    latestCapture = await captureContextItems();

    renderCapture(latestCapture);

    if (!latestCapture.contexts.length) {
      throw new Error("No supported browser tabs were captured.");
    }

    // 2. Send captured contexts to the task engine.
    setStatus(
      "Processing contexts and discovering activities...",
      "loading"
    );

    const response = await fetch(PROCESSING_API_URL, {
      method: "POST",
      headers: {
        "Content-Type": "application/json"
      },
      body: JSON.stringify(latestCapture)
    });

    const result = await response.json();

    if (!response.ok) {
      throw new Error(
        result.detail || `Backend error (${response.status})`
      );
    }

    if (!result.success) {
      throw new Error("Task processing was unsuccessful.");
    }

    // 3. Save and display discovered activities.
    latestHandoffData = result;

    renderActivities(result);

    setStatus(
      `Processing complete: ${result.task_count} tasks and ${result.activity_count} activities discovered.`,
      "success"
    );

  } catch (error) {
    console.error(
      "[TaskFlow] Capture or processing failed:",
      error
    );

    setStatus(
      `Processing failed: ${error.message}`,
      "error"
    );

  } finally {
    captureBtn.disabled = false;
  }
});

// --------------------------------------------------
// Copy captured contexts
// --------------------------------------------------

copyBtn.addEventListener("click", async () => {
  if (!latestCapture) return;

  try {
    await navigator.clipboard.writeText(
      prettyJson(latestCapture)
    );

    setStatus("JSON copied", "success");

  } catch (error) {
    console.error("[TaskFlow] Copy failed:", error);
    setStatus("Copy failed", "error");
  }
});

// --------------------------------------------------
// Download captured contexts
// --------------------------------------------------

downloadBtn.addEventListener("click", () => {
  if (!latestCapture) return;

  try {
    const blob = new Blob(
      [prettyJson(latestCapture)],
      { type: "application/json" }
    );

    const objectUrl = URL.createObjectURL(blob);

    const anchor = document.createElement("a");

    anchor.href = objectUrl;

    anchor.download =
      `taskflow-context-${makeDownloadTimestamp(latestCapture.captured_at)}.json`;

    document.body.appendChild(anchor);

    anchor.click();
    anchor.remove();

    setTimeout(
      () => URL.revokeObjectURL(objectUrl),
      0
    );

    setStatus("JSON downloaded", "success");

  } catch (error) {
    console.error("[TaskFlow] Download failed:", error);
    setStatus("Download failed", "error");
  }
});

// --------------------------------------------------
// Clear browser activity history
// --------------------------------------------------

clearBtn.addEventListener("click", async () => {
  if (!confirm("Clear all saved tab activity timestamps?")) {
    return;
  }

  try {
    await chrome.storage.local.remove("tabActivity");

    setStatus("Activity history cleared", "success");

  } catch (error) {
    console.error("[TaskFlow] Clear failed:", error);

    setStatus(
      "Could not clear activity history",
      "error"
    );
  }
});

// --------------------------------------------------
// Local handoff using JSON file
// --------------------------------------------------

handoffBtn.addEventListener("click", () => {
  handoffFile.click();
});

handoffFile.addEventListener("change", async () => {
  const file = handoffFile.files[0];

  if (!file) return;

  try {
    const handoffData = JSON.parse(
      await file.text()
    );

    latestHandoffData = handoffData;

    const activities = handoffData.activities || [];

    if (activities.length === 0) {
      throw new Error(
        "No activities found in this JSON file."
      );
    }

    const activity = activities[0];

    // Read the current API package format first.
    // Retain compatibility with older package formats.
    const sourcePackage =
      activity.handoff_package ||
      activity.activity_handoff_package;

    const contexts = Array.isArray(sourcePackage?.contexts)
      ? sourcePackage.contexts
      : (activity.handoff_packages || [])
          .flatMap(pkg => pkg.contexts || []);

    if (contexts.length === 0) {
      throw new Error(
        "No handoff contexts found for this activity."
      );
    }

  const response = await chrome.runtime.sendMessage({
  action: "EXECUTE_HANDOFF",
  activity: {
    activity_id: String(
      sourcePackage?.activity_id ||
      activity.activity_id ||
      activity.task_id ||
      `activity-${Date.now()}`
    ),
    label:
      sourcePackage?.activity_label ||
      activity.activity_label ||
      activity.label ||
      "TaskFlow Activity",
    description:
      sourcePackage?.activity_description ||
      activity.activity_description ||
      activity.description ||
      "",
    contexts
  }
});

    if (!response?.success) {
      throw new Error(
        response?.error || "Handoff failed."
      );
    }

    setStatus(
      `Handoff complete: ${response.opened_tabs} tabs opened.`,
      "success"
    );

  } catch (error) {
    console.error("[TaskFlow] Handoff failed:", error);

    setStatus(
      `Handoff failed: ${error.message}`,
      "error"
    );

  } finally {
    handoffFile.value = "";
  }
});
activitySelect.addEventListener("change", () => {
  updateSelectedActivityInfo();
});
// ==================================================
// TaskFlow Cloud Handoff
// ==================================================

const CLOUD_URL = "http://127.0.0.1:8000";

const serverUrlInput = document.getElementById("serverUrl");
const pairingTokenInput = document.getElementById("pairingToken");

const registerDeviceBtn =
  document.getElementById("registerDeviceBtn");

const refreshDevicesBtn =
  document.getElementById("refreshDevicesBtn");
const generatePairingCodeBtn =
  document.getElementById("generatePairingCodeBtn");

const pairingCodeContainer =
  document.getElementById("pairingCodeContainer");

const pairingCodeDisplay =
  document.getElementById("pairingCodeDisplay");

const pairingCodeInput =
  document.getElementById("pairingCodeInput");

const pairDeviceBtn =
  document.getElementById("pairDeviceBtn");
const deviceSelect =
  document.getElementById("deviceSelect");
const sendToDeviceBtn =
  document.getElementById("sendToDeviceBtn");

const receiveFromCloudBtn =
  document.getElementById("receiveFromCloudBtn");

// --------------------------------------------------
// Cloud configuration
// --------------------------------------------------

if (serverUrlInput) {
  serverUrlInput.value = CLOUD_URL;
}

function getCloudConfig() {
  const serverUrl = (
    serverUrlInput?.value || CLOUD_URL
  ).trim().replace(/\/+$/, "");

  const token = pairingTokenInput?.value?.trim()
    || "change-this-local-dev-token";

  return { serverUrl, token };
}

// --------------------------------------------------
// Cloud API request helper
// --------------------------------------------------


async function cloudRequest(path, options = {}) {
  const { serverUrl, token } = getCloudConfig();

  const useDeviceCredential =
    options.useDeviceCredential === true;

  const requestOptions = { ...options };
  delete requestOptions.useDeviceCredential;

  const headers = {
    "Content-Type": "application/json",
    ...(options.headers || {})
  };

  if (useDeviceCredential) {
    const stored = await chrome.storage.local.get([
      "taskflowDeviceCredential"
    ]);

    const deviceCredential = stored.taskflowDeviceCredential;

    if (!deviceCredential) {
      throw new Error(
        "Device authentication is unavailable. Please register this device first."
      );
    }

    headers["X-Taskflow-Device-Credential"] =
      deviceCredential;
  } else {
    headers["X-Taskflow-Token"] = token;
  }

  const response = await fetch(`${serverUrl}${path}`, {
    ...requestOptions,
    headers
  });

  const data = await response.json().catch(() => ({}));

  if (!response.ok) {
    throw new Error(
      data.detail || `Server error (${response.status})`
    );
  }

  return data;
}


// --------------------------------------------------
// Device ID management
// --------------------------------------------------

async function getOrCreateDeviceId() {
  const stored = await chrome.storage.local.get(
    "taskflowDeviceId"
  );

  if (stored.taskflowDeviceId) {
    return stored.taskflowDeviceId;
  }

  const deviceId = `desktop-${crypto.randomUUID()}`;

  await chrome.storage.local.set({
    taskflowDeviceId: deviceId
  });

  return deviceId;
}
// --------------------------------------------------
// First-device credential provisioning
// --------------------------------------------------

async function provisionDeviceCredential(deviceId) {
  // Check whether this device already has a credential.
  const stored = await chrome.storage.local.get([
    "taskflowDeviceCredential",
    "taskflowCredentialDeviceId"
  ]);

  if (
    stored.taskflowDeviceCredential &&
    stored.taskflowCredentialDeviceId === deviceId
  ) {
    console.log("[TaskFlow] Device credential already exists.");

    return stored.taskflowDeviceCredential;
  }

  // Request a new device-specific credential.
  const result = await cloudRequest(
    "/devices/credentials/issue",
    {
      method: "POST",
      body: JSON.stringify({
        device_id: deviceId
      })
    }
  );

  if (!result.device_credential) {
    throw new Error("Backend did not return a device credential.");
  }

  // Store the credential against this device ID.
  await chrome.storage.local.set({
    taskflowDeviceCredential: result.device_credential,
    taskflowCredentialDeviceId: deviceId
  });

  console.log("[TaskFlow] Device credential stored.");

  return result.device_credential;
}
async function getNativeDeviceInfo() {
  return new Promise((resolve, reject) => {
    chrome.runtime.sendNativeMessage(
      "com.taskflow.native",
      { profile_label: "Personal" },
      (response) => {
        if (chrome.runtime.lastError) {
          reject(new Error(chrome.runtime.lastError.message));
          return;
        }

        if (!response?.success) {
          reject(new Error(response?.error || "Device detection failed."));
          return;
        }

        resolve(response);
      }
    );
  });
}

// --------------------------------------------------
// Register current device
// --------------------------------------------------

if (registerDeviceBtn) {
  registerDeviceBtn.addEventListener(
    "click",
    async () => {
      registerDeviceBtn.disabled = true;

      setStatus(
        "Registering this device…",
        "loading"
      );

      try {
        const deviceId = await getOrCreateDeviceId();
        const deviceInfo = await getNativeDeviceInfo();
        await cloudRequest(
          "/devices/register",
          {
            method: "POST",

            body: JSON.stringify({
            device_id: deviceId,
            device_name: deviceInfo.hostname,
            device_type: deviceInfo.device_type,
            manufacturer: deviceInfo.manufacturer,
            model: deviceInfo.model,
            os_name: deviceInfo.os_name,
            os_version: deviceInfo.os_version,
            profile_label: deviceInfo.profile_label,
            user_agent: navigator.userAgent
})
          }
        );
        // Obtain and store this device's unique credential.
await provisionDeviceCredential(deviceId);
        setStatus(
          "This device is registered with TaskFlow Cloud.",
          "success"
        );

      } catch (error) {
        console.error(
          "[TaskFlow] Registration failed:",
          error
        );

        setStatus(
          `Registration failed: ${error.message}`,
          "error"
        );

      } finally {
        registerDeviceBtn.disabled = false;
      }
    }
  );
}
generatePairingCodeBtn.addEventListener(
  "click",
  async () => {
    generatePairingCodeBtn.disabled = true;

    pairingCodeContainer.hidden = true;
    pairingCodeDisplay.textContent = "";

    setStatus(
      "Generating pairing code…",
      "loading"
    );

    try {
      const data = await cloudRequest(
        "/pairing/create",
        {
          method: "POST",
          useDeviceCredential: true
        }
      );

      pairingCodeDisplay.textContent =
        data.pairing_code;

      pairingCodeContainer.hidden = false;

      setStatus(
        "Pairing code generated successfully.",
        "success"
      );

    } catch (error) {
      console.error(
        "[TaskFlow] Pairing code generation failed:",
        error
      );

      setStatus(
        `Could not generate pairing code: ${error.message}`,
        "error"
      );

    } finally {
      generatePairingCodeBtn.disabled = false;
    }
  }
);
pairDeviceBtn.addEventListener(
  "click",
  async () => {
    const pairingCode = pairingCodeInput.value.trim();

    if (!/^\d{8}$/.test(pairingCode)) {
      setStatus(
        "Please enter a valid 8-digit pairing code.",
        "error"
      );
      return;
    }

    pairDeviceBtn.disabled = true;

    setStatus(
      "Pairing this device…",
      "loading"
    );

    try {
      const deviceId = await getOrCreateDeviceId();
      const deviceInfo = await getNativeDeviceInfo();

      // Pairing verification does not require the shared token.
      const { serverUrl } = getCloudConfig();

      const response = await fetch(
        `${serverUrl}/pairing/verify`,
        {
          method: "POST",
          headers: {
            "Content-Type": "application/json"
          },
          body: JSON.stringify({
            pairing_code: pairingCode,
            device_id: deviceId,
            device_name: deviceInfo.hostname,
            device_type: deviceInfo.device_type,
            manufacturer: deviceInfo.manufacturer,
            model: deviceInfo.model,
            os_name: deviceInfo.os_name,
            os_version: deviceInfo.os_version,
            profile_label: deviceInfo.profile_label,
            user_agent: navigator.userAgent
          })
        }
      );

      const data = await response.json().catch(() => ({}));

      if (!response.ok) {
        throw new Error(
          data.detail || `Server error (${response.status})`
        );
      }

      // Store this device's unique credential.
      await chrome.storage.local.set({
        taskflowDeviceCredential: data.device_credential,
        taskflowCredentialDeviceId: data.device_id
      });

      pairingCodeInput.value = "";

      setStatus(
        "Device paired successfully! Authentication credentials stored.",
        "success"
      );

      console.log(
        "[TaskFlow] New device paired and credential stored."
      );

    } catch (error) {
      console.error(
        "[TaskFlow] Device pairing failed:",
        error
      );

      setStatus(
        `Device pairing failed: ${error.message}`,
        "error"
      );

    } finally {
      pairDeviceBtn.disabled = false;
    }
  }
);
// --------------------------------------------------
// Refresh registered devices
// --------------------------------------------------

if (refreshDevicesBtn) {
  refreshDevicesBtn.addEventListener(
    "click",
    async () => {
      refreshDevicesBtn.disabled = true;

      setStatus(
        "Loading registered devices…",
        "loading"
      );

      try {
        const currentDeviceId =
          await getOrCreateDeviceId();

        const data = await cloudRequest(
  "/devices",
  {
    useDeviceCredential: true
  }
);

        deviceSelect.replaceChildren();

        const otherDevices = (
          data.devices || []
        ).filter(
          device =>
            device.device_id !== currentDeviceId
        );

        for (const device of otherDevices) {
          const option = document.createElement("option");

          option.value = device.device_id;
          const profile = device.profile_label
          ? ` (${device.profile_label})`
          : "";

          const os = device.os_name
          ? ` — ${device.os_name}${device.os_version ? " " + device.os_version : ""}`
          : "";

        option.textContent = `${device.device_name}${profile}${os}`;

          deviceSelect.appendChild(option);
        }

        if (otherDevices.length === 0) {
          const option = document.createElement("option");

          option.value = "";
          option.textContent =
            "No other registered devices";

          deviceSelect.appendChild(option);
        }

        setStatus(
          `${otherDevices.length} other device(s) found.`,
          "success"
        );

      } catch (error) {
        console.error(
          "[TaskFlow] Device refresh failed:",
          error
        );

        setStatus(
          `Could not load devices: ${error.message}`,
          "error"
        );

      } finally {
        refreshDevicesBtn.disabled = false;
      }
    }
  );
}

// --------------------------------------------------
// Send activity to another device through cloud
// --------------------------------------------------

if (sendToDeviceBtn) {
  sendToDeviceBtn.addEventListener(
    "click",
    async () => {
      sendToDeviceBtn.disabled = true;

      try {
        if (!latestHandoffData) {
          throw new Error(
            "Capture and process contexts first, or load your activity handoff JSON file."
          );
        }

        const selectedIndex = Number(activitySelect.value);

const activity =
  latestHandoffData.activities?.[selectedIndex];

if (!Number.isInteger(selectedIndex) || !activity) {
  throw new Error("Please select a valid activity.");
}

        if (!activity) {
          throw new Error(
            "No activity found in the handoff data."
          );
        }

        // Current API format: activity.handoff_package
        // Older formats are retained as fallbacks.
        const sourcePackage =
  activity.handoff_package ||
  activity.activity_handoff_package;

const contexts = getActivityContexts(activity);

        if (contexts.length === 0) {
          throw new Error(
            "No selected contexts are available for this activity."
          );
        }

        // Build the package expected by the cloud server.
        const activityPackage = {
          activity_id: String(
            sourcePackage?.activity_id ||
            activity.activity_id ||
            activity.task_id ||
            `activity-${Date.now()}`
          ),

          label:
            sourcePackage?.activity_label ||
            activity.activity_label ||
            activity.label ||
            "TaskFlow Activity",

          description:
            sourcePackage?.activity_description ||
            activity.activity_description ||
            activity.description ||
            "",

          contexts
        };

        const targetDeviceId = deviceSelect?.value;

        if (!targetDeviceId) {
          throw new Error(
            "Select a target device first."
          );
        }

        setStatus(
          "Sending activity to target device…",
          "loading"
        );

        const result = await cloudRequest(
  "/handoff",
  {
    method: "POST",
    useDeviceCredential: true,

    body: JSON.stringify({
      activity_package: activityPackage,
      target_device_id: targetDeviceId
    })
  }
);

        setStatus(
          `Activity sent: ${result.context_count} context(s).`,
          "success"
        );

      } catch (error) {
        console.error(
          "[TaskFlow] Cloud send failed:",
          error
        );

        setStatus(
          `Cloud send failed: ${error.message}`,
          "error"
        );

      } finally {
        sendToDeviceBtn.disabled = false;
      }
    }
  );
}

// --------------------------------------------------
// Receive activity from cloud on this device
// --------------------------------------------------

if (receiveFromCloudBtn) {
  receiveFromCloudBtn.addEventListener(
    "click",
    async () => {
      receiveFromCloudBtn.disabled = true;

      try {
        const deviceId = await getOrCreateDeviceId();

        setStatus(
          "Checking for incoming activity…",
          "loading"
        );

        const activityPackage = await cloudRequest(
  `/devices/${encodeURIComponent(deviceId)}/handoff`,
  {
    useDeviceCredential: true
  }
);

        if (
          !Array.isArray(activityPackage.contexts) ||
          activityPackage.contexts.length === 0
        ) {
          throw new Error(
            "The received activity contains no contexts."
          );
        }

        const result = await chrome.runtime.sendMessage({
  action: "EXECUTE_HANDOFF",
  activity: {
    activity_id: activityPackage.activity_id,
    label: activityPackage.label || "TaskFlow Activity",
    description: activityPackage.description || "",
    contexts: activityPackage.contexts
  }
});

        if (!result?.success) {
          throw new Error(
            result?.error ||
            "Could not open received activity."
          );
        }

        setStatus(
          `Received "${activityPackage.label || "activity"}": ${result.opened_tabs} tab(s) opened.`,
          "success"
        );

      } catch (error) {
        console.error(
          "[TaskFlow] Cloud receive failed:",
          error
        );

        setStatus(
          `Cloud receive failed: ${error.message}`,
          "error"
        );

      } finally {
        receiveFromCloudBtn.disabled = false;
      }
    }
  );
}