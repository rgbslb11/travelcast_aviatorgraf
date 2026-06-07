import { airportBroadcastPackage } from "../exporters/exportBroadcastPackage.js";
import { selectedAirportToGeoJSON } from "../exporters/exportGeojson.js";
import { airportPlacefile } from "../exporters/exportPlacefile.js";
import { downloadTextFile, impactClass, safeText, formatDateTime } from "../utils.js";
import { addQueueItem } from "../state.js";
import { renderGraphicsQueue } from "./graphicsQueue.js";

export function renderAirportDetail(airport) {
  const container = document.querySelector("#airport-detail");
  if (!airport) {
    container.innerHTML = `<div class="card"><h2>Airport Detail / Graphics Prep</h2><p>Select an airport from the Airport Status Board.</p></div>`;
    return;
  }
  const pkg = airportBroadcastPackage(airport);
  container.innerHTML = `
    <div class="card ${impactClass(airport.overall_impact_color)}">
      <h2>${safeText(airport.iata)} — ${safeText(airport.airport_name)}</h2>
      <p class="muted">${safeText(airport.city)}, ${safeText(airport.state)} · Generated ${formatDateTime(pkg.generated_at)}</p>
      <span class="badge ${impactClass(airport.overall_impact_color)}">${safeText(airport.overall_impact_label)}</span>
    </div>
    <div class="grid">
      <div class="card"><div class="label">Current Operational Impact — FAA NAS / ATCSCC</div><h3>${safeText(airport.current_delay_type,"None")}</h3><div class="kpi">${airport.avg_delay_minutes ?? "—"}</div><p>Avg delay minutes</p><p>${safeText(airport.current_reason,"No active event")}</p><p>Arrivals: ${safeText(airport.arrival_runway,"—")} · Departures: ${safeText(airport.departure_runway,"—")} · AAR: ${safeText(airport.aar,"—")}</p></div>
      <div class="card"><div class="label">Forecast Weather Impact — NWS forecast proxy</div><h3>${safeText(airport.forecast_impact_label)}</h3><p>${safeText(airport.dominant_sky_condition)}</p><p>${safeText(airport.forecast_impact_reasons)}</p><p>Icon ID: ${safeText(airport.forecast_icon_id,"na")}</p></div>
      <div class="card"><div class="label">Aviation Weather Truth — AviationWeather METAR/TAF</div><h3>${safeText(airport.metar_condition,"Unavailable")}</h3><p>Flight category: ${safeText(airport.flight_category,"—")}</p><p>Wind: ${safeText(airport.metar_wind,"—")} · Visibility: ${safeText(airport.metar_visibility,"—")}</p><p>TAF: ${safeText(airport.taf_trend,"—")}</p></div>
    </div>
    <div class="card">
      <h3>Graphics Copy Block</h3>
      <div class="graphics-copy"><strong>${pkg.graphics.headline}</strong><br>${pkg.graphics.subheadline}<br><br>${pkg.graphics.lower_third}<br><br>${pkg.graphics.long_card_text}<br><br><span class="muted">${pkg.graphics.source_footer}</span></div>
      <div class="export-row">
        <button class="btn primary" id="detail-export-json">Download Package JSON</button>
        <button class="btn" id="detail-export-geojson">Download GeoJSON</button>
        <button class="btn" id="detail-export-placefile">Download Placefile</button>
        <button class="btn" id="detail-add-queue">Add to Graphics Queue</button>
      </div>
    </div>`;
  document.querySelector("#detail-export-json").addEventListener("click", () => downloadTextFile(`${airport.iata}_broadcast_package.json`, JSON.stringify(pkg, null, 2), "application/json"));
  document.querySelector("#detail-export-geojson").addEventListener("click", () => downloadTextFile(`${airport.iata}_airport_feature.geojson`, JSON.stringify(selectedAirportToGeoJSON(airport), null, 2), "application/geo+json"));
  document.querySelector("#detail-export-placefile").addEventListener("click", () => downloadTextFile(`${airport.iata}_airport_impact.placefile.txt`, airportPlacefile([airport]), "text/plain"));
  document.querySelector("#detail-add-queue").addEventListener("click", () => {
    addQueueItem({ packageName: `${airport.iata} Airport Status Card`, productType: "airport_status_card", targetPlatform: "broadcast", airportId: airport.airport_id, freshnessStatus: airport.freshness_status, sourceSummary: airport.source_summary, payload: airport });
    renderGraphicsQueue();
  });
}
