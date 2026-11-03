function isSupportedHttpUrl(value) {
  try {
    const url = new URL(value);
    return url.protocol === "http:" || url.protocol === "https:";
  } catch {
    return false;
  }
}

function getDomain(value) {
  try {
    const hostname = new URL(value).hostname.toLowerCase();
    return hostname.startsWith("www.") ? hostname.slice(4) : hostname;
  } catch {
    return "";
  }
}

function makeDownloadTimestamp(isoString) {
  return isoString.replace(/[:.]/g, "-");
}

function prettyJson(value) {
  return JSON.stringify(value, null, 2);
}
