import { sampleRoutes } from "../sampleData/sampleRouteCast.js";
import { safeText, impactClass, formatDateTime } from "../utils.js";
import { isSupabaseConfigured, getSupabaseClient } from "../supabaseClient.js";

const DOCTRINE_LABEL = "Forecast Weather Impact — NWS forecast proxy";

export async function renderRoutecast() {
  if (isSupabaseConfigured()) {
    await renderLiveRoutecast();
  } else {
    renderDemoRoutecast();
  }
}

// ── Live mode ───────────────────────────────────────────────────────────

async function renderLiveRoutecast() {
  const container = document.querySelector("#routecast");
  container.innerHTML = loadingHtml();

  let routes = [];
  let queryError = null;

  try {
    const client = await getSupabaseClient();
    const { data, error } = await client
      .from("v_routecast_dashboard")
      .select("*")
      .limit(50);
    if (error) {
      queryError = error.message;
    } else {
      routes = data || [];
    }
  } catch (err) {
    queryError = err.message;
  }

  if (queryError) {
    container.innerHTML =
      headerHtml() +
      `<div class="card"><p class="muted">Query error: ${safeText(queryError)}</p>
       <span class="source-doctrine">${DOCTRINE_LABEL}</span></div>`;
    return;
  }

  if (routes.length === 0) {
    container.innerHTML =
      headerHtml() +
      `<div class="card">
        <p><strong>No live RouteCast routes configured yet.</strong></p>
        <p class="muted">Configure routes to begin tracking departure and en-route weather impacts.
        Forecast weather impact is not an official FAA delay forecast.</p>
        <span class="source-doctrine">${DOCTRINE_LABEL}</span>
      </div>`;
    return;
  }

  // Routes present — render using live column schema
  const cards = routes.map(r => liveRouteCard(r)).join("");
  container.innerHTML = headerHtml() + cards;
}

// ── Live route card ─────────────────────────────────────────────────────

function prepStatusClass(prep_status) {
  switch (prep_status) {
    case "Significant": return "red";
    case "Elevated":    return "red";
    case "Monitor":     return "amber";
    case "Normal":      return "green";
    default:            return "gray";
  }
}

function liveRouteCard(r) {
  const cls = impactClass(r.route_impact_color);

  const originDelayLine = r.origin_avg_delay
    ? `<span class="muted" style="font-size:12px;margin-left:6px"> avg ${r.origin_avg_delay} min</span>`
    : "";

  const destDelayLine = r.dest_avg_delay
    ? `<span class="muted" style="font-size:12px;margin-left:6px"> avg ${r.dest_avg_delay} min</span>`
    : "";

  const routeStringLine = r.route_string
    ? `<div class="label" style="margin-bottom:4px">Route: <span style="font-weight:400;font-family:monospace;font-size:12px">${safeText(r.route_string)}</span></div>`
    : "";

  const routeNotesLine = r.route_notes
    ? `<p class="muted" style="font-size:12px">${safeText(r.route_notes)}</p>`
    : "";

  return `<div class="card ${cls}">
  <div style="display:flex;justify-content:space-between;align-items:center;flex-wrap:wrap;gap:10px;margin-bottom:12px">
    <div>
      <h3 style="margin:0">${safeText(r.origin_iata)} → ${safeText(r.dest_iata)}
        <span class="muted" style="font-weight:400;font-size:14px">${safeText(r.route_name || "")}</span>
      </h3>
      <span class="muted" style="font-size:12px">${safeText(r.origin_city || "")} → ${safeText(r.dest_city || "")}</span>
    </div>
    <div style="display:flex;gap:6px;align-items:center;flex-wrap:wrap">
      <span class="badge ${prepStatusClass(r.prep_status)}">${safeText(r.prep_status || "")}</span>
      <span class="badge ${cls}">${safeText(r.route_impact_color || "Unknown")}</span>
    </div>
  </div>

  <div style="display:grid;grid-template-columns:1fr 1fr;gap:12px;margin-bottom:10px">
    <div>
      <div class="label">Origin: ${safeText(r.origin_iata)} — ${safeText(r.origin_city || "")}</div>
      <span class="badge ${impactClass(r.origin_op_color)}">${safeText(r.origin_op_label || "Normal")}</span>
      ${originDelayLine}
      <br><span class="muted" style="font-size:11px">Forecast: ${safeText(r.origin_fcst_label || "—")}</span>
      <br><span class="source-doctrine">Current Operational Impact — FAA NAS Status</span>
    </div>
    <div>
      <div class="label">Destination: ${safeText(r.dest_iata)} — ${safeText(r.dest_city || "")}</div>
      <span class="badge ${impactClass(r.dest_op_color)}">${safeText(r.dest_op_label || "Normal")}</span>
      ${destDelayLine}
      <br><span class="muted" style="font-size:11px">Forecast: ${safeText(r.dest_fcst_label || "—")}</span>
      <br><span class="source-doctrine">Current Operational Impact — FAA NAS Status</span>
    </div>
  </div>

  ${routeStringLine}
  ${routeNotesLine}
  <span class="source-doctrine">${DOCTRINE_LABEL} · NOT an official FAA delay forecast</span>
</div>`;
}

// ── Demo mode (unchanged behavior) ─────────────────────────────────────

function renderDemoRoutecast() {
  const html =
    `<div class="card">
      <h2>RouteCast</h2>
      <p class="muted">Departure-airport impact and en-route weather-impact proxy for monitored routes. Forecast weather impact is not an official FAA delay forecast.</p>
      <div class="label">${DOCTRINE_LABEL}</div>
      <div class="warning" style="margin-top:12px">Demo Mode: sample routes shown. Live mode combines NWS forecast proxy and FAA NAS departure impacts.</div>
    </div>` +
    sampleRoutes.map(routeCard).join("");
  document.querySelector("#routecast").innerHTML = html;
}

// ── Shared HTML helpers ─────────────────────────────────────────────────

function headerHtml() {
  return `<div class="card">
    <h2>RouteCast</h2>
    <p class="muted">Departure-airport impact and en-route weather-impact proxy for monitored routes.</p>
    <span class="source-doctrine">${DOCTRINE_LABEL} · NOT an official FAA delay forecast</span>
  </div>`;
}

function loadingHtml() {
  return `<div class="card"><h2>RouteCast</h2><p class="muted">Loading…</p></div>`;
}

// ── Demo route card (uses sampleRoutes column format) ───────────────────

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
    ${r.waypoints ? `<div style="display:flex;flex-direction:column">${r.waypoints.map(waypointRow).join("")}</div>` : ""}
    <span class="source-doctrine">${safeText(r.source || DOCTRINE_LABEL)}</span>
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
