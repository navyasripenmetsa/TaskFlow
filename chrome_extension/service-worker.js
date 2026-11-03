const ACTIVITY_KEY = "tabActivity";

async function getActivity() {
  try {
    const result = await chrome.storage.local.get(ACTIVITY_KEY);
    return result[ACTIVITY_KEY] || {};
  } catch (error) {
    console.error("[TaskFlow] Failed to read tab activity:", error);
    return {};
  }
}

async function setTabActivated(tabId) {
  try {
    const activity = await getActivity();
    activity[String(tabId)] = new Date().toISOString();
    await chrome.storage.local.set({ [ACTIVITY_KEY]: activity });
  } catch (error) {
    console.error("[TaskFlow] Failed to store tab activity:", error);
  }
}

async function removeTabActivity(tabId) {
  try {
    const activity = await getActivity();
    const key = String(tabId);
    if (Object.prototype.hasOwnProperty.call(activity, key)) {
      delete activity[key];
      await chrome.storage.local.set({ [ACTIVITY_KEY]: activity });
    }
  } catch (error) {
    console.error("[TaskFlow] Failed to remove tab activity:", error);
  }
}

chrome.tabs.onActivated.addListener(({ tabId }) => {
  void setTabActivated(tabId);
});

chrome.tabs.onRemoved.addListener((tabId) => {
  void removeTabActivity(tabId);
});

// Receive handoff instructions and open their URLs.
chrome.runtime.onMessage.addListener(
  (message, sender, sendResponse) => {

    if (message.action !== "EXECUTE_HANDOFF") {
      return;
    }

    (async () => {
      try {
        const urls = message.contexts
          .map(context => context.reconstruction_target)
          .filter(url =>
            typeof url === "string" &&
            url.startsWith("https://")
          );

        const createdTabs = [];

        for (const url of urls) {
          const tab = await chrome.tabs.create({
            url: url,
            active: false
          });

          createdTabs.push(tab.id);
        }

        sendResponse({
          success: true,
          opened_tabs: createdTabs.length,
          tab_ids: createdTabs
        });

      } catch (error) {
        console.error(
          "[TaskFlow] Handoff failed:",
          error
        );

        sendResponse({
          success: false,
          error: error.message
        });
      }
    })();

    return true;
  }
);
