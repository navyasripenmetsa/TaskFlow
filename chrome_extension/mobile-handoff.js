(() => {
  const statusEl = document.getElementById("status");
  const jsonOutputEl = document.getElementById("jsonOutput");

  function setMobileStatus(message, kind = "") {
    if (!statusEl) return;
    statusEl.textContent = message;
    statusEl.className = `status ${kind}`.trim();
  }

  const styleLink = document.createElement("link");
  styleLink.rel = "stylesheet";
  styleLink.href = "mobile-handoff.css";
  document.head.appendChild(styleLink);

  const section = document.createElement("section");
  section.className = "content-section mobile-handoff-section";
  section.innerHTML = `
    <div class="section-title-row">
      <h2>Send to Android over Wi-Fi</h2>
    </div>
    <p class="mobile-description">Send captured browser tabs to a TaskFlow Android device on the same Wi-Fi network.</p>
    <button id="sendMobileBtn" class="primary" disabled>Send to Mobile</button>
    <details id="mobileConfigSection" class="expandable-section mobile-config">
      <summary>
        <span>Mobile connection</span>
        <span class="expand-hint">Laptop server address and pairing token</span>
      </summary>
      <div class="expandable-content">
        <label for="serverUrlInput">Laptop server address</label>
        <input id="serverUrlInput" type="url" placeholder="http://192.168.x.x:8001" autocomplete="url">
        <label for="pairingTokenInput">Pairing token</label>
        <input id="pairingTokenInput" type="password" placeholder="Token shown by the laptop server" autocomplete="off">
        <button id="saveMobileConfigBtn" class="secondary" type="button">Save mobile connection</button>
      </div>
    </details>`;

  const receiveSection = document.querySelector(".receive-section");
  if (receiveSection) receiveSection.before(section);

  const sendButton = section.querySelector("#sendMobileBtn");
  const serverUrlInput = section.querySelector("#serverUrlInput");
  const pairingTokenInput = section.querySelector("#pairingTokenInput");
  const saveButton = section.querySelector("#saveMobileConfigBtn");

  function getCurrentCapture() {
    if (!jsonOutputEl) return null;
    try {
      const capture = JSON.parse(jsonOutputEl.textContent || "{}");
      return Array.isArray(capture.contexts) && capture.contexts.length
        ? capture
        : null;
    } catch (_error) {
      return null;
    }
  }

  function updateSendButton() {
    sendButton.disabled = !getCurrentCapture();
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
      throw new Error("Enter a valid address, such as http://192.168.1.20:8001.");
    }
    if (!["http:", "https:"].includes(serverUrl.protocol) ||
        serverUrl.pathname !== "/" || serverUrl.search || serverUrl.hash) {
      throw new Error("Use the laptop server's root HTTP or HTTPS address.");
    }

    const config = {
      serverUrl: serverUrl.origin,
      pairingToken,
    };
    await chrome.storage.local.set({
      taskflowMobileServerUrl: config.serverUrl,
      taskflowPairingToken: config.pairingToken,
    });
    serverUrlInput.value = config.serverUrl;
    if (showStatus) setMobileStatus("Mobile connection saved.", "success");
    return config;
  }

  async function mobileApiRequest(serverUrl, pairingToken, path, options = {}) {
    const response = await fetch(`${serverUrl}${path}`, {
      ...options,
      headers: {
        "X-Taskflow-Token": pairingToken,
        ...(options.body ? { "Content-Type": "application/json" } : {}),
        ...(options.headers || {}),
      },
    });
    const data = response.status === 204
      ? null
      : await response.json().catch(() => ({}));
    if (!response.ok) {
      throw new Error(data?.detail || `Laptop server error (${response.status}).`);
    }
    return data;
  }

  chrome.storage.local.get([
    "taskflowMobileServerUrl",
    "taskflowPairingToken",
  ]).then((saved) => {
    serverUrlInput.value = saved.taskflowMobileServerUrl || "";
    pairingTokenInput.value = saved.taskflowPairingToken || "";
  }).catch((error) => {
    console.warn("[TaskFlow] Could not load mobile connection settings:", error);
  });

  saveButton.addEventListener("click", async () => {
    try {
      await saveMobileConfig();
    } catch (error) {
      setMobileStatus(error.message, "error");
    }
  });

  sendButton.addEventListener("click", async () => {
    const capture = getCurrentCapture();
    if (!capture) return;
    sendButton.disabled = true;
    setMobileStatus("Finding TaskFlow on Android…", "loading");

    try {
      const config = await saveMobileConfig(false);
      const deviceResponse = await mobileApiRequest(
        config.serverUrl,
        config.pairingToken,
        "/devices",
      );
      const androidDevices = (deviceResponse?.devices || [])
        .filter((device) => /taskflow android/i.test(device.device_name || ""))
        .sort((left, right) => (right.last_seen || 0) - (left.last_seen || 0));
      if (!androidDevices.length) {
        throw new Error("Open TaskFlow Android and tap Receive Handoff first.");
      }

      setMobileStatus("Generating and sending activity handoff…", "loading");
      const result = await mobileApiRequest(
        config.serverUrl,
        config.pairingToken,
        "/handoff/generate",
        {
          method: "POST",
          body: JSON.stringify({
            capture,
            target_device_id: androidDevices[0].device_id,
          }),
        },
      );
      setMobileStatus(
        `Handoff sent: ${result.activity_count} activity, ${result.context_count} context(s).`,
        "success",
      );
    } catch (error) {
      console.error("[TaskFlow] Send to Mobile failed:", error);
      const message = error instanceof TypeError
        ? "Could not reach the laptop server. Check its address, same Wi-Fi, and Windows Firewall."
        : error.message || "Unknown error.";
      setMobileStatus(`Send to Mobile failed: ${message}`, "error");
    } finally {
      updateSendButton();
    }
  });

  if (jsonOutputEl) {
    new MutationObserver(updateSendButton).observe(jsonOutputEl, {
      childList: true,
      subtree: true,
      characterData: true,
    });
  }
  updateSendButton();
})();
