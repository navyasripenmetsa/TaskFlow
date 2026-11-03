async function loadTabActivity() {
  try {
    const result = await chrome.storage.local.get("tabActivity");
    return result.tabActivity || {};
  } catch (error) {
    console.error("[TaskFlow] Could not load activity:", error);
    return {};
  }
}


async function getPageContext(tabId) {
  try {
    const response = await chrome.tabs.sendMessage(tabId, {
      type: "TASKFLOW_GET_PAGE_TEXT"
    });

    if (response?.ok) {
      return {
        text: typeof response.text === "string" ? response.text : "",
        interaction: response.interaction || {}
      };
    }
  } catch (error) {
    console.warn(
      `[TaskFlow] Could not read page context for tab ${tabId}. Refresh the page after installing/reloading the extension.`,
      error
    );
  }

  return {
    text: "",
    interaction: {}
  };
}


async function captureContextItems() {
  const capturedAt = new Date().toISOString();
  const activity = await loadTabActivity();
  const tabs = await chrome.tabs.query({ currentWindow: true });
  const supportedTabs = tabs.filter((tab) => isSupportedHttpUrl(tab.url));

  const contexts = [];

  for (let i = 0; i < supportedTabs.length; i += 1) {
    const tab = supportedTabs[i];
    const pageContext = await getPageContext(tab.id);
    const text = pageContext.text;
    const url = tab.url || "";

    contexts.push({
      context_id: `ctx_${String(i + 1).padStart(3, "0")}`,
      source: {
        tab_id: tab.id,
        window_id: tab.windowId
      },
      content: {
        title: tab.title || "",
        url,
        domain: getDomain(url),
        text
      },
      state: {
        active: Boolean(tab.active),
        last_interaction: activity[String(tab.id)] || null,
        interaction: pageContext.interaction
      },
      reconstruction: {
        method: "url",
        target: url
      }
    });
  }

  return {
    schema_version: "1.0",
    captured_at: capturedAt,
    context_count: contexts.length,
    contexts
  };
}
