import { sampleRoutes } from "../sampleData/sampleRouteCast.js";
import { safeText, impactClass, formatDateTime } from "../utils.js";

export function renderRoutecast() {
  const html =
    headerCard() +
    sampleRoutes.map(routeCard).join("");
  document.querySelector("#routecast").innerHTML = html;
}

function headerCard() {
  return `<div class="card">
    <h2>RouteCast</h2>
    <p class="muted">Departure-airport impact and en-route weather-impact proxy for monitored routes. Forecast weather impact is not an official FAA delay forecast.</p>
    <div class="label">Forecast Weather Impact — NWS forecast proxy</div>
    <div class="warning" style="margin-top:12px">Demo Mode: sample routes shown. Live mode combines NWS forecast proxy and FAA NAS departure impacts.</div>
  </div>`;
}

function routeCard(r) {
  const cls = impactClass(r.overall_impact_color);
  return `<div class="card ${cls}">
    <div style="display:flex;justify-content:space-between;align-items:center;flex-wrap:wrap;gap:10px">
      <div>
        <h3 style="margin:0">${safeText(r.origin_iata)} → ${safeText(r.destination_iata)}
          <span class="muted" style="font-weight:400;font-size:14px">${safeText(r.label)}</span>
        </h3>
        <span class="muted">Est. departure: ${formatDateTime(r.estimated_departure)}</span>
      </div>
      <span class="badge ${cls}">${safeText(r.overall_impact_label)}</span>
    </div>
    <p>${safeText(r.impact_summary)}</p>
    <div class="label" style="margin-bottom:8px">Route:
      <span style="font-weight:400;font-family:monospace">${safeText(r.route_string)}</span>
    </div>
    <div style="display:flex;flex-direction:column">
      ${r.waypoints.map(waypointRow).join("")}
    </div>
    <div class="source">${safeText(r.source)}</div>
  </div>`;
}

function waypointRow(w) {
  const cls = impactClass(w.impact_color);
  return `<div style="display:flex;align-items:center;gap:12px;padding:7px 0;border-bottom:1px solid var(--line)">
    <span class="badge ${cls}" style="min-width:8px;padding:4px 8px">&nbsp;</span>
    <strong style="min-width:60px;font-size:13px">${safeText(w.id)}</strong>
    <span style="flex:1;font-size:13px">${safeText(w.label)}</span>
    <span class="muted" style="font-size:12px">${safeText(w.note)}</span>
  </div>`;
}
