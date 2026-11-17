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

// Receive handoff instructions and reconstruct the activity.
chrome.runtime.onMessage.addListener(
  (message, sender, sendResponse) => {

    if (message.action !== "EXECUTE_HANDOFF") {
      return;
    }

    (async () => {
      try {
        const activity = message.activity;

        if (
          !activity ||
          !Array.isArray(activity.contexts) ||
          activity.contexts.length === 0
        ) {
          throw new Error("Invalid activity package.");
        }

        const urls = activity.contexts
          .map(context => context.reconstruction_target)
          .filter(url =>
            typeof url === "string" &&
            url.startsWith("https://")
          );

        if (urls.length === 0) {
          throw new Error("No valid HTTPS URLs found.");
        }

        // Open all selected contexts in new tabs.
        const createdTabs = [];

        for (const url of urls) {
          const tab = await chrome.tabs.create({
            url,
            active: false
          });

          createdTabs.push(tab.id);
        }

        // Create a Chrome Tab Group for this activity.
        const groupId = await chrome.tabs.group({
          tabIds: createdTabs
        });

        // Name and color the group.
        await chrome.tabGroups.update(groupId, {
          title: activity.label || "TaskFlow Activity",
          color: "blue",
          collapsed: false
        });

        // Save reconstructed activity metadata locally.
        const stored = await chrome.storage.local.get([
          "taskflowReconstructedActivities"
        ]);

        const activities =
          stored.taskflowReconstructedActivities || [];

        activities.push({
          activity_id: activity.activity_id || null,
          label: activity.label || "TaskFlow Activity",
          description: activity.description || "",
          group_id: groupId,
          tab_ids: createdTabs,
          reconstructed_at: new Date().toISOString()
        });

        await chrome.storage.local.set({
          taskflowReconstructedActivities: activities
        });

        sendResponse({
          success: true,
          opened_tabs: createdTabs.length,
          tab_ids: createdTabs,
          group_id: groupId
        });

      } catch (error) {
        console.error(
          "[TaskFlow] Activity reconstruction failed:",
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
