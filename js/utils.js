export function safeText(value, fallback = "") {
  return value === undefined || value === null || value === "" ? fallback : String(value);
}

export function normalizeAirportCode(code) {
  if (!code) return "";
  const c = String(code).trim().toUpperCase();
  return c.length === 4 && c.startsWith("K") ? c.slice(1) : c;
}

export function formatDateTime(value) {
  if (!value) return "Unavailable";
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return String(value);
  return date.toLocaleString();
}

export function getFreshnessStatus(timestamp, maxAgeMinutes = 10) {
  if (!timestamp) return "unknown";
  const date = new Date(timestamp);
  if (Number.isNaN(date.getTime())) return "unknown";
  const ageMinutes = (Date.now() - date.getTime()) / 60000;
  if (ageMinutes <= maxAgeMinutes) return "fresh";
  if (ageMinutes <= maxAgeMinutes * 2) return "aging";
  return "stale";
}

export function impactClass(value) {
  const v = String(value || "unknown").toLowerCase();
  if (v.includes("red") || v.includes("ground") || v.includes("closure") || v.includes("major")) return "red";
  if (v.includes("amber") || v.includes("monitor") || v.includes("possible")) return "amber";
  if (v.includes("green") || v.includes("good") || v.includes("normal")) return "green";
  if (v.includes("blue") || v.includes("info")) return "blue";
  return "gray";
}

export function downloadTextFile(filename, text, mimeType = "text/plain") {
  const blob = new Blob([text], { type: mimeType });
  const url = URL.createObjectURL(blob);
  const a = document.createElement("a");
  a.href = url;
  a.download = filename;
  a.click();
  URL.revokeObjectURL(url);
}
