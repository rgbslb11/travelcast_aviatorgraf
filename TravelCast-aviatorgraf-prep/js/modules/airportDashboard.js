import { sampleAirportStatus } from "../sampleData/sampleAirportStatus.js";
import { getSupabaseClient, isSupabaseConfigured } from "../supabaseClient.js";
import { appState, addQueueItem } from "../state.js";
import { impactClass, safeText, formatDateTime } from "../utils.js";
import { airportRowsToGeoJSON, selectedAirportToGeoJSON } from "../exporters/exportGeojson.js";
import { dashboardJson } from "../exporters/exportDashboardJson.js";
import { airportBroadcastPackage } from "../exporters/exportBroadcastPackage.js";
import { airportPlacefile } from "../exporters/exportPlacefile.js";
import { downloadTextFile } from "../utils.js";
import { renderAirportDetail } from "./airportDetail.js";
import { renderGraphicsQueue } from "./graphicsQueue.js";

export async function loadAirportStatus() {
  if (isSupabaseConfigured()) {
    try {
      const client = await getSupabaseClient();
      const { data, error } = await client.from("v_airport_status_dashboard").select("*").order("region").order("iata");
      if (!error && data) {
        appState.demoModeActive = false;
        appState.airportStatusRecords = data;
        return data;
      }
      appState.warnings.push(`Supabase view unavailable; using demo data. ${error?.message || ""}`);
    } catch (err) {
      appState.warnings.push(`Supabase failed; using demo data. ${err.message}`);
    }
  }
  appState.demoModeActive = true;
  appState.airportStatusRecords = sampleAirportStatus;
  return sampleAirportStatus;
}

export async function renderAirportDashboard() {
  const container = document.querySelector("#airport-board");
  const records = await loadAirportStatus();
  const warning = appState.demoModeActive ? `<div class="warning">Demo Mode Active: data is sample-only and not live.</div>` : "";
  container.innerHTML = `
    ${warning}
    <div class="card">
      <h2>Airport Status Board</h2>
      <p class="muted">High-level airport operations and weather-impact board. FAA/NAS operational status is separated from NWS forecast proxy.</p>
      <div class="export-row">
        <button class="btn primary" id="export-dashboard-json">Export Dashboard JSON</button>
        <button class="btn" id="export-all-geojson">Export All Airports GeoJSON</button>
      </div>
    </div>
    <div class="table-shell"><table>
      <thead><tr><th>Airport</th><th>Region</th><th>Forecast Weather Impact</th><th>Current Operational Impact</th><th>Delay</th><th>Reason</th><th>Runways / AAR</th><th>METAR</th><th>Freshness</th><th>Actions</th></tr></thead>
      <tbody>${records.map(rowHtml).join("")}</tbody>
    </table></div>`;

  container.querySelector("#export-dashboard-json").addEventListener("click", () => downloadTextFile("travelcast_airport_status_dashboard.json", JSON.stringify(dashboardJson(records), null, 2), "application/json"));
  container.querySelector("#export-all-geojson").addEventListener("click", () => downloadTextFile("travelcast_airport_overlay.geojson", JSON.stringify(airportRowsToGeoJSON(records), null, 2), "application/geo+json"));
  container.querySelectorAll("[data-action]").forEach(btn => btn.addEventListener("click", handleAction));
}

function rowHtml(r) {
  const impact = impactClass(r.overall_impact_color || r.forecast_impact_color || r.current_status_code);
  return `<tr>
    <td><strong>${safeText(r.iata || r.airport_id)}</strong><br><span class="muted">${safeText(r.display_name)} — ${safeText(r.icao)}</span></td>
    <td>${safeText(r.region)}</td>
    <td><span class="badge ${impactClass(r.forecast_impact_color)}">${safeText(r.forecast_impact_label,"Unknown")}</span><br><span class="muted">${safeText(r.forecast_impact_reasons)}</span></td>
    <td><span class="badge ${impact}">${safeText(r.current_delay_type || r.overall_impact_label,"None")}</span></td>
    <td>${r.avg_delay_minutes ?? ""}${r.avg_delay_minutes ? " min" : ""}<br><span class="muted">Max ${r.max_delay_minutes ?? "—"}</span></td>
    <td>${safeText(r.current_reason,"—")}</td>
    <td>${safeText(r.arrival_runway,"—")}<br><span class="muted">Dep ${safeText(r.departure_runway,"—")} / AAR ${safeText(r.aar,"—")}</span></td>
    <td>${safeText(r.metar_condition,"—")}<br><span class="muted">${safeText(r.flight_category,"—")} ${safeText(r.metar_wind,"")}</span></td>
    <td><span class="badge ${impactClass(r.freshness_status)}">${safeText(r.freshness_status,"unknown")}</span><br><span class="muted">${formatDateTime(r.last_updated_at)}</span></td>
    <td class="actions">
      <button class="btn small" data-action="detail" data-airport="${r.airport_id}">Detail</button>
      <button class="btn small" data-action="queue" data-airport="${r.airport_id}">Queue</button>
      <button class="btn small" data-action="json" data-airport="${r.airport_id}">JSON</button>
      <button class="btn small" data-action="geojson" data-airport="${r.airport_id}">GeoJSON</button>
      <button class="btn small" data-action="placefile" data-airport="${r.airport_id}">Placefile</button>
    </td>
  </tr>`;
}

function handleAction(event) {
  const airport = appState.airportStatusRecords.find(r => r.airport_id === event.target.dataset.airport);
  if (!airport) return;
  const action = event.target.dataset.action;
  if (action === "detail") {
    appState.selectedAirport = airport;
    renderAirportDetail(airport);
    document.querySelector('[data-tab="airport-detail"]').click();
  }
  if (action === "queue") {
    addQueueItem({ packageName: `${airport.iata} Airport Status Card`, productType: "airport_status_card", targetPlatform: "broadcast", airportId: airport.airport_id, freshnessStatus: airport.freshness_status, sourceSummary: airport.source_summary, payload: airport });
    renderGraphicsQueue();
  }
  if (action === "json") downloadTextFile(`${airport.iata}_broadcast_package.json`, JSON.stringify(airportBroadcastPackage(airport), null, 2), "application/json");
  if (action === "geojson") downloadTextFile(`${airport.iata}_airport_feature.geojson`, JSON.stringify(selectedAirportToGeoJSON(airport), null, 2), "application/geo+json");
  if (action === "placefile") downloadTextFile(`${airport.iata}_airport_impact.placefile.txt`, airportPlacefile([airport]), "text/plain");
}
