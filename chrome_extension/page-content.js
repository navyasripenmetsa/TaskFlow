
const MAX_TEXT_LENGTH = 12000;
const MAX_FORM_CONTROLS = 50;
const MAX_VALUE_LENGTH = 1000;

// Capture visible page text.

// Capture meaningful page content while reducing UI noise.
function extractVisibleText() {
  try {
    const isVisible = (element) => {
      const style = window.getComputedStyle(element);

      return (
        style.display !== "none" &&
        style.visibility !== "hidden" &&
        element.getClientRects().length > 0
      );
    };

    const cleanElementText = (element) => {
      if (!element) return "";

      const clone = element.cloneNode(true);

      // Remove common interface and non-content elements.
      clone.querySelectorAll(
        "nav, header, footer, aside, button, input, select, textarea, " +
        "script, style, noscript, [role='navigation'], " +
        "[role='banner'], [role='contentinfo'], [aria-hidden='true']"
      ).forEach((el) => el.remove());

      return (clone.innerText || clone.textContent || "")
        .replace(/\s+/g, " ")
        .trim();
    };

    // Gmail: prioritize the actual email rather than its sidebar.
    if (location.hostname === "mail.google.com") {
      const subject = document.querySelector(".hP");
      const sender = document.querySelector(".gD");
      const emailBody = document.querySelector(".a3s");

      const subjectText = subject?.innerText?.trim() || "";
      const senderText =
        sender?.getAttribute("email") ||
        sender?.innerText?.trim() ||
        "";
      const bodyText = cleanElementText(emailBody);

      if (subjectText || bodyText) {
        return [
          subjectText ? `Email subject: ${subjectText}` : "",
          senderText ? `Email sender: ${senderText}` : "",
          bodyText ? `Email body: ${bodyText}` : ""
        ]
          .filter(Boolean)
          .join("\n")
          .slice(0, MAX_TEXT_LENGTH);
      }
    }

    // General websites: prefer their main content region.
    const candidates = Array.from(
      document.querySelectorAll(
        "main, article, [role='main'], [role='article']"
      )
    ).filter(isVisible);

    let bestText = "";
    let bestScore = 0;

    for (const candidate of candidates) {
      const text = cleanElementText(candidate);

      if (!text) continue;

      // Prefer substantial content, without rewarding excessive length.
      const score = Math.min(text.length, 8000);

      if (score > bestScore) {
        bestScore = score;
        bestText = text;
      }
    }

    // Fallback for websites without semantic content regions.
    if (!bestText) {
      bestText = cleanElementText(document.body);
    }

    return bestText.slice(0, MAX_TEXT_LENGTH);

  } catch (error) {
    console.error(
      "[TaskFlow] Failed to extract page text:",
      error
    );
    return "";
  }
}


// Capture basic interaction state.
function extractInteractionState() {
  try {
    const selection = window.getSelection()?.toString().trim() || "";

    const controls = Array.from(
      document.querySelectorAll("input, textarea, select")
    )
      .filter((element) => {
        const style = window.getComputedStyle(element);
        return (
          !element.disabled &&
          element.type !== "password" &&
          style.display !== "none" &&
          style.visibility !== "hidden" &&
          element.getClientRects().length > 0
        );
      })
      .slice(0, MAX_FORM_CONTROLS)
      .map((element) => ({
        tag: element.tagName.toLowerCase(),
        type: element.type || null,
        name: element.name || "",
        value: String(element.value || "").slice(0, MAX_VALUE_LENGTH)
      }));

    return {
      scroll: {
        x: Math.round(window.scrollX),
        y: Math.round(window.scrollY)
      },
      selection: selection.slice(0, MAX_VALUE_LENGTH),
      form_values: controls
    };
  } catch (error) {
    console.error("[TaskFlow] Failed to extract interaction state:", error);
    return {};
  }
}

// Restore basic interaction state.
function restoreInteractionState(interaction) {
  try {
    if (!interaction) return;

    // Restore supported form values.
    (interaction.form_values || []).forEach((saved) => {
      const elements = Array.from(
        document.querySelectorAll(saved.tag)
      );

      const element = elements.find(
        (el) =>
          el.name === saved.name &&
          (el.type || null) === saved.type &&
          !el.disabled &&
          el.type !== "password"
      );

      if (element) {
        element.value = saved.value;

        element.dispatchEvent(
          new Event("input", { bubbles: true })
        );

        element.dispatchEvent(
          new Event("change", { bubbles: true })
        );
      }
    });

    // Restore scroll position.
    if (interaction.scroll) {
      window.scrollTo({
        left: interaction.scroll.x || 0,
        top: interaction.scroll.y || 0,
        behavior: "instant"
      });
    }

    // Restore selected text when the saved text can be found.
    if (interaction.selection) {
      const walker = document.createTreeWalker(
        document.body,
        NodeFilter.SHOW_TEXT
      );

      let node;

      while ((node = walker.nextNode())) {
        const index = node.textContent.indexOf(interaction.selection);

        if (index !== -1) {
          const range = document.createRange();

          range.setStart(node, index);
          range.setEnd(
            node,
            index + interaction.selection.length
          );

          const selection = window.getSelection();
          selection.removeAllRanges();
          selection.addRange(range);
          break;
        }
      }
    }

    console.log("[TaskFlow] Basic interaction state restored.");

  } catch (error) {
    console.error("[TaskFlow] State restoration failed:", error);
  }
}

// Handle page capture requests.
chrome.runtime.onMessage.addListener((message, _sender, sendResponse) => {
  if (message?.type !== "TASKFLOW_GET_PAGE_TEXT") return;

  sendResponse({
    ok: true,
    text: extractVisibleText(),
    interaction: extractInteractionState()
  });
});

// Handle state restoration requests.
chrome.runtime.onMessage.addListener((message, _sender, sendResponse) => {
  if (message?.type !== "TASKFLOW_RESTORE_STATE") return;

  restoreInteractionState(message.interaction);

  sendResponse({ ok: true });
});
