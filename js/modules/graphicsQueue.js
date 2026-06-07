import { appState, loadQueue, removeQueueItem, updateQueueItem } from "../state.js";
import { airportBroadcastPackage } from "../exporters/exportBroadcastPackage.js";
import { selectedAirportToGeoJSON } from "../exporters/exportGeojson.js";
import { airportPlacefile } from "../exporters/exportPlacefile.js";
import { downloadTextFile, safeText, formatDateTime, impactClass } from "../utils.js";

export function renderGraphicsQueue() {
  const container = document.querySelector("#graphics-queue");
  loadQueue();

  const items = appState.graphicsQueue;
  const queueHtml = items.length
    ? items.map(itemHtml).join("")
    : `<div class="card"><p class="muted">No graphics queued yet. Use the <strong>Queue</strong> button on any airport row or the Airport Detail panel.</p></div>`;

  container.innerHTML =
    `<div class="card">
      <h2>Graphics Queue</h2>
      <p class="muted">LocalStorage-backed package queue. Mark items Ready before broadcast use. Stale or unknown freshness items require review before air.</p>
      ${items.length ? `<p class="muted"><strong>${items.length}</strong> item${items.length !== 1 ? "s" : ""} queued</p>` : ""}
    </div>` + queueHtml;

  container.querySelectorAll("[data-q-action]").forEach(btn =>
    btn.addEventListener("click", handleQueueAction)
  );
}

function itemHtml(q) {
  const payload = q.payload || {};
  const iata = safeText(payload.iata || q.airportId, "—");
  const cityState = [payload.city, payload.state].filter(Boolean).join(", ");
  const displayName = safeText(payload.display_name || payload.airport_name, "");
  const freshCls = impactClass(q.freshnessStatus);
  const statusCls = q.status === "Ready" ? "green" : q.status === "Used" ? "gray" : q.status === "Needs Freshness Review" ? "amber" : "blue";
  const opLabel = payload.current_delay_type && payload.current_delay_type !== "None"
    ? payload.current_delay_type
    : "No active FAA/NAS event";
  const fcstLabel = payload.forecast_impact_label || "—";
  const opCls = impactClass(payload.current_impact_color);
  const fcstCls = impactClass(payload.forecast_impact_color);

  return `<div class="card">
    <div style="display:flex;justify-content:space-between;align-items:flex-start;flex-wrap:wrap;gap:10px;margin-bottom:10px">
      <div>
        <strong style="font-size:16px">${iata}</strong>
        ${displayName ? `<span class="muted" style="margin-left:8px">${displayName}</span>` : ""}
        ${cityState ? `<span class="muted" style="margin-left:8px;font-size:12px">${cityState}</span>` : ""}
        <br>
        <span class="muted" style="font-size:12px">${safeText(q.productType, "airport_status_card")} · ${safeText(q.targetPlatform, "broadcast")}</span>
        <br>
        <span class="muted" style="font-size:11px">Queued: ${formatDateTime(q.generatedAt)}</span>
      </div>
      <div style="display:flex;gap:6px;flex-wrap:wrap;align-items:center">
        <span class="badge ${statusCls}">${safeText(q.status, "Draft")}</span>
        <span class="badge ${freshCls}">Freshness: ${safeText(q.freshnessStatus, "unknown")}</span>
      </div>
    </div>
    <div style="display:flex;gap:12px;flex-wrap:wrap;margin-bottom:10px">
      <div>
        <span class="source-doctrine">FAA/NAS:</span>
        <span class="badge ${opCls}" style="font-size:11px">${opLabel}</span>
        ${payload.avg_delay_minutes ? `<span class="muted" style="font-size:12px"> · avg ${payload.avg_delay_minutes} min</span>` : ""}
      </div>
      <div>
        <span class="source-doctrine">NWS Forecast:</span>
        <span class="badge ${fcstCls}" style="font-size:11px">${fcstLabel}</span>
      </div>
      ${payload.flight_category ? `<div><span class="source-doctrine">METAR:</span> <span class="badge gray" style="font-size:11px">${payload.flight_category}</span></div>` : ""}
    </div>
    ${q.sourceSummary ? `<p class="source-doctrine" style="margin:0 0 10px">${safeText(q.sourceSummary)}</p>` : ""}
    <div class="actions">
      <button class="btn small" data-q-action="ready" data-id="${q.id}">Mark Ready</button>
      <button class="btn small" data-q-action="used" data-id="${q.id}">Mark Used</button>
      <button class="btn small" data-q-action="json" data-id="${q.id}">Package JSON</button>
      <button class="btn small" data-q-action="geojson" data-id="${q.id}">GeoJSON</button>
      <button class="btn small" data-q-action="placefile" data-id="${q.id}">Placefile</button>
      <button class="btn small danger" data-q-action="remove" data-id="${q.id}">Remove</button>
    </div>
  </div>`;
}

function handleQueueAction(e) {
  const id = e.target.dataset.id;
  const q = appState.graphicsQueue.find(x => x.id === id);
  if (!q) return;

  const action = e.target.dataset.qAction;
  const fileBase = q.airportId || "travelcast";

  if (action === "ready") {
    const isFresh = q.freshnessStatus === "fresh" || q.freshnessStatus === "aging";
    updateQueueItem(id, { status: isFresh ? "Ready" : "Needs Freshness Review" });
  }
  if (action === "used")      updateQueueItem(id, { status: "Used" });
  if (action === "remove")    removeQueueItem(id);
  if (action === "json")
    downloadTextFile(
      `${fileBase}_broadcast_package.json`,
      JSON.stringify(airportBroadcastPackage(q.payload), null, 2),
      "application/json"
    );
  if (action === "geojson")
    downloadTextFile(
      `${fileBase}_airport_feature.geojson`,
      JSON.stringify(selectedAirportToGeoJSON(q.payload), null, 2),
      "application/geo+json"
    );
  if (action === "placefile")
    downloadTextFile(
      `${fileBase}_airport_impact.placefile.txt`,
      airportPlacefile([q.payload]),
      "text/plain"
    );

  renderGraphicsQueue();
}
