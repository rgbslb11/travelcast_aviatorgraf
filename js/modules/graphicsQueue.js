import { appState, loadQueue, removeQueueItem, updateQueueItem } from "../state.js";
import { airportBroadcastPackage } from "../exporters/exportBroadcastPackage.js";
import { selectedAirportToGeoJSON } from "../exporters/exportGeojson.js";
import { airportPlacefile } from "../exporters/exportPlacefile.js";
import { downloadTextFile, safeText } from "../utils.js";

export function renderGraphicsQueue() {
  const container = document.querySelector("#graphics-queue");
  loadQueue();
  container.innerHTML = `<div class="card"><h2>Graphics Queue</h2><p class="muted">LocalStorage-backed queue for graphics prep. Stale/unknown data should not be used without review.</p></div>` +
    (appState.graphicsQueue.length ? appState.graphicsQueue.map(itemHtml).join("") : `<div class="card"><p>No graphics queued yet.</p></div>`);
  container.querySelectorAll("[data-q-action]").forEach(btn => btn.addEventListener("click", handleQueueAction));
}

function itemHtml(q) {
  return `<div class="card"><div class="queue-item"><strong>${safeText(q.packageName)}</strong><span>${safeText(q.productType)}</span><span>${safeText(q.status)}</span><span>${safeText(q.freshnessStatus)}</span><span class="actions">
    <button class="btn small" data-q-action="ready" data-id="${q.id}">Mark Ready</button>
    <button class="btn small" data-q-action="used" data-id="${q.id}">Mark Used</button>
    <button class="btn small" data-q-action="json" data-id="${q.id}">JSON</button>
    <button class="btn small" data-q-action="geojson" data-id="${q.id}">GeoJSON</button>
    <button class="btn small" data-q-action="placefile" data-id="${q.id}">Placefile</button>
    <button class="btn small danger" data-q-action="remove" data-id="${q.id}">Remove</button>
  </span></div><p class="source">${safeText(q.sourceSummary)}</p></div>`;
}

function handleQueueAction(e) {
  const id = e.target.dataset.id;
  const q = appState.graphicsQueue.find(x => x.id === id);
  if (!q) return;
  const action = e.target.dataset.qAction;
  if (action === "ready") updateQueueItem(id, { status: q.freshnessStatus === "stale" || q.freshnessStatus === "unknown" ? "Needs Freshness Review" : "Ready" });
  if (action === "used") updateQueueItem(id, { status: "Used" });
  if (action === "remove") removeQueueItem(id);
  if (action === "json") downloadTextFile(`${q.airportId || "travelcast"}_package.json`, JSON.stringify(airportBroadcastPackage(q.payload), null, 2), "application/json");
  if (action === "geojson") downloadTextFile(`${q.airportId || "travelcast"}.geojson`, JSON.stringify(selectedAirportToGeoJSON(q.payload), null, 2), "application/geo+json");
  if (action === "placefile") downloadTextFile(`${q.airportId || "travelcast"}.placefile.txt`, airportPlacefile([q.payload]), "text/plain");
  renderGraphicsQueue();
}
