let latestCapture = null;
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
}

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
