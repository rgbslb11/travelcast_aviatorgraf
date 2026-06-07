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

const DOCTRINE_FCST = "Forecast Weather Impact — NWS forecast proxy";

export async function loadAirportStatus() {
  if (isSupabaseConfigured()) {
    try {
      const client = await getSupabaseClient();
      const { data, error } = await client
        .from("v_airport_status_dashboard")
        .select("*")
        .order("region")
        .order("iata");
      if (!error && data && data.length > 0) {
        appState.demoModeActive = false;
        appState.connectionStatus = 'configured';
        appState.airportStatusRecords = data;
        return data;
      }
      const msg = error
        ? `Supabase view query failed: ${error.message}`
        : 'Supabase view returned no rows — check that the bootstrap SQL ran and seed data exists.';
      appState.warnings.push(msg + ' Using demo fallback.');
      appState.connectionStatus = 'failed';
    } catch (err) {
      appState.warnings.push(`Supabase connection error: ${err.message}. Using demo fallback.`);
      appState.connectionStatus = 'failed';
    }
  } else {
    appState.connectionStatus = 'demo';
  }
  appState.demoModeActive = true;
  appState.airportStatusRecords = sampleAirportStatus;
  return sampleAirportStatus;
}

// ── Filter helpers ──────────────────────────────────────────────────────

function uniqueRegions(records) {
  const seen = new Set();
  return records
    .map(r => r.region || "")
    .filter(r => r && !seen.has(r) && seen.add(r));
}

function filterRecords(records, { region, search, opImpact, fcstImpact }) {
  return records.filter(r => {
    if (region && r.region !== region) return false;
    if (search) {
      const q = search.toLowerCase();
      const hit =
        (r.iata || "").toLowerCase().includes(q) ||
        (r.icao || "").toLowerCase().includes(q) ||
        (r.display_name || "").toLowerCase().includes(q) ||
        (r.city || "").toLowerCase().includes(q) ||
        (r.airport_name || "").toLowerCase().includes(q);
      if (!hit) return false;
    }
    if (opImpact) {
      if (opImpact === "None") {
        if (r.current_delay_type && r.current_delay_type !== "None") return false;
      } else {
        if ((r.current_impact_color || "").toLowerCase() !== opImpact.toLowerCase()) return false;
      }
    }
    if (fcstImpact) {
      if ((r.forecast_impact_color || "").toLowerCase() !== fcstImpact.toLowerCase()) return false;
    }
    return true;
  });
}

// ── Render helpers ──────────────────────────────────────────────────────

function rowHtml(r) {
  const impact = impactClass(r.overall_impact_color || r.forecast_impact_color || r.current_status_code);
  const fcstLabel = r.forecast_impact_label || "Unknown";
  const hasDoctrineConcatenated = fcstLabel.includes("NWS forecast proxy");
  const shortFcstLabel = hasDoctrineConcatenated
    ? fcstLabel.split("—")[0].trim()
    : fcstLabel;

  return `<tr>
    <td><strong>${safeText(r.iata || r.airport_id)}</strong><br><span class="muted">${safeText(r.display_name)} — ${safeText(r.icao)}</span></td>
    <td>${safeText(r.region)}</td>
    <td>
      <span class="badge ${impactClass(r.forecast_impact_color)}">${safeText(shortFcstLabel, "Unknown")}</span>
      <br><span class="source-doctrine">${DOCTRINE_FCST}</span>
      ${r.forecast_impact_reasons ? `<br><span class="muted">${safeText(r.forecast_impact_reasons)}</span>` : ""}
    </td>
    <td><span class="badge ${impact}">${safeText(r.current_delay_type || r.overall_impact_label, "None")}</span>
      <br><span class="source-doctrine">Current Operational Impact — FAA NAS Status</span></td>
    <td>${r.avg_delay_minutes ?? ""}${r.avg_delay_minutes ? " min" : ""}<br><span class="muted">Max ${r.max_delay_minutes ?? "—"}</span></td>
    <td>${safeText(r.current_reason, "—")}</td>
    <td>${safeText(r.arrival_runway, "—")}<br><span class="muted">Dep ${safeText(r.departure_runway, "—")} / AAR ${safeText(r.aar, "—")}</span></td>
    <td>${safeText(r.metar_condition, "—")}<br><span class="muted">${safeText(r.flight_category, "—")} ${safeText(r.metar_wind, "")}</span></td>
    <td><span class="badge ${impactClass(r.freshness_status)}">${safeText(r.freshness_status, "unknown")}</span><br><span class="muted">${formatDateTime(r.last_updated_at)}</span></td>
    <td class="actions">
      <button class="btn small" data-action="detail" data-airport="${r.airport_id}">Detail</button>
      <button class="btn small" data-action="queue" data-airport="${r.airport_id}">Queue</button>
      <button class="btn small" data-action="json" data-airport="${r.airport_id}">JSON</button>
      <button class="btn small" data-action="geojson" data-airport="${r.airport_id}">GeoJSON</button>
      <button class="btn small" data-action="placefile" data-airport="${r.airport_id}">Placefile</button>
    </td>
  </tr>`;
}

function filterBarHtml(records) {
  const regions = uniqueRegions(records);
  const regionOptions = regions.map(r => `<option value="${r}">${r}</option>`).join("");
  return `
    <div class="filter-bar">
      <input type="text" id="apt-search" placeholder="Search airport, city, IATA…" autocomplete="off">
      <select id="apt-region-filter">
        <option value="">All Regions</option>
        ${regionOptions}
      </select>
      <select id="apt-op-filter">
        <option value="">All Operational</option>
        <option value="Red">Operational: Red</option>
        <option value="Amber">Operational: Amber</option>
        <option value="Green">Operational: Green</option>
        <option value="None">No Active Event</option>
      </select>
      <select id="apt-fcst-filter">
        <option value="">All Forecast</option>
        <option value="Red">Forecast: Red</option>
        <option value="Amber">Forecast: Amber</option>
        <option value="Green">Forecast: Green</option>
      </select>
      <span id="apt-count" class="muted"></span>
    </div>`;
}

function renderTable(container, records, filters) {
  const filtered = filterRecords(records, filters);
  const tbody = container.querySelector("tbody");
  if (tbody) {
    tbody.innerHTML = filtered.map(rowHtml).join("");
  }
  const countEl = container.querySelector("#apt-count");
  if (countEl) {
    countEl.textContent = `${filtered.length} of ${records.length} airports`;
  }
  container.querySelectorAll("[data-action]").forEach(btn =>
    btn.addEventListener("click", handleAction)
  );
}

// ── Main render ─────────────────────────────────────────────────────────

export async function renderAirportDashboard() {
  const container = document.querySelector("#airport-board");
  const records = await loadAirportStatus();
  const warning = appState.demoModeActive
    ? `<div class="warning">Demo Mode Active: data is sample-only and not live.</div>`
    : "";

  container.innerHTML = `
    ${warning}
    <div class="card">
      <h2>Airport Status Board</h2>
      <p class="muted">
        FAA/NAS operational status is separated from NWS forecast proxy.
        Source labels appear below each impact badge.
      </p>
      <div class="export-row">
        <button class="btn primary" id="export-dashboard-json">Export Dashboard JSON</button>
        <button class="btn" id="export-all-geojson">Export All Airports GeoJSON</button>
      </div>
      ${filterBarHtml(records)}
    </div>
    <div class="table-shell"><table>
      <thead><tr>
        <th>Airport</th>
        <th>Region</th>
        <th>Forecast Weather Impact</th>
        <th>Current Operational Impact</th>
        <th>Delay</th>
        <th>Reason</th>
        <th>Runways / AAR</th>
        <th>METAR</th>
        <th>Freshness</th>
        <th>Actions</th>
      </tr></thead>
      <tbody></tbody>
    </table></div>`;

  // Initial render — no filters active
  const filters = { region: "", search: "", opImpact: "", fcstImpact: "" };
  renderTable(container, records, filters);

  // Export buttons
  container.querySelector("#export-dashboard-json").addEventListener("click", () =>
    downloadTextFile(
      "travelcast_airport_status_dashboard.json",
      JSON.stringify(dashboardJson(records), null, 2),
      "application/json"
    )
  );
  container.querySelector("#export-all-geojson").addEventListener("click", () =>
    downloadTextFile(
      "travelcast_airport_overlay.geojson",
      JSON.stringify(airportRowsToGeoJSON(records), null, 2),
      "application/geo+json"
    )
  );

  // Filter controls
  function applyFilters() {
    filters.search    = container.querySelector("#apt-search").value.trim();
    filters.region    = container.querySelector("#apt-region-filter").value;
    filters.opImpact  = container.querySelector("#apt-op-filter").value;
    filters.fcstImpact = container.querySelector("#apt-fcst-filter").value;
    renderTable(container, records, filters);
  }

  container.querySelector("#apt-search").addEventListener("input", applyFilters);
  container.querySelector("#apt-region-filter").addEventListener("change", applyFilters);
  container.querySelector("#apt-op-filter").addEventListener("change", applyFilters);
  container.querySelector("#apt-fcst-filter").addEventListener("change", applyFilters);
}

// ── Action handler ──────────────────────────────────────────────────────

function handleAction(event) {
  const airport = appState.airportStatusRecords.find(
    r => r.airport_id === event.target.dataset.airport
  );
  if (!airport) return;
  const action = event.target.dataset.action;
  if (action === "detail") {
    appState.selectedAirport = airport;
    renderAirportDetail(airport);
    document.querySelector('[data-tab="airport-detail"]').click();
  }
  if (action === "queue") {
    addQueueItem({
      packageName: `${airport.iata} Airport Status Card`,
      productType: "airport_status_card",
      targetPlatform: "broadcast",
      airportId: airport.airport_id,
      freshnessStatus: airport.freshness_status,
      sourceSummary: airport.source_summary,
      payload: airport,
    });
    renderGraphicsQueue();
  }
  if (action === "json")
    downloadTextFile(
      `${airport.iata}_broadcast_package.json`,
      JSON.stringify(airportBroadcastPackage(airport), null, 2),
      "application/json"
    );
  if (action === "geojson")
    downloadTextFile(
      `${airport.iata}_airport_feature.geojson`,
      JSON.stringify(selectedAirportToGeoJSON(airport), null, 2),
      "application/geo+json"
    );
  if (action === "placefile")
    downloadTextFile(
      `${airport.iata}_airport_impact.placefile.txt`,
      airportPlacefile([airport]),
      "text/plain"
    );
}
