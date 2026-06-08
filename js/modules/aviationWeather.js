import { sampleAviationHazards } from "../sampleData/sampleAviationHazards.js";
import { safeText, formatDateTime } from "../utils.js";
import { isSupabaseConfigured, getSupabaseClient } from "../supabaseClient.js";

const DOCTRINE_LABEL = "Aviation Weather Truth — AviationWeather.gov";

export async function renderAviationHazards() {
  if (isSupabaseConfigured()) {
    await renderLiveHazards();
  } else {
    renderDemoHazards();
  }
}

// ── Live mode ───────────────────────────────────────────────────────────

async function renderLiveHazards() {
  const container = document.querySelector("#aviation-hazards");
  container.innerHTML = loadingHtml("Aviation Hazards");

  let records = [];
  let queryError = null;

  try {
    const client = await getSupabaseClient();
    const { data, error } = await client
      .from("v_aviation_hazards_latest")
      .select("*")
      .limit(100);
    if (error) {
      queryError = error.message;
    } else {
      records = data || [];
    }
  } catch (err) {
    queryError = err.message;
  }

  if (queryError) {
    container.innerHTML = headerHtml("Aviation Hazards") + errorHtml(queryError, DOCTRINE_LABEL);
    return;
  }

  if (records.length === 0) {
    container.innerHTML =
      headerHtml("Aviation Hazards") +
      emptyStateHtml(
        "No live aviation hazard records available.",
        "SIGMET, AIRMET, CWA, and PIREP data from AviationWeather.gov is not yet stored in Supabase. " +
        "METAR and TAF data is available in the Airport Status Board.",
        DOCTRINE_LABEL
      );
    return;
  }

  // Group records by hazard_type: SIGMETs first, then AIRMETs, then CWAs, then other
  const ORDER = ["SIGMET", "AIRMET", "CWA", "PIREP"];
  const groups = {};
  for (const r of records) {
    const key = r.hazard_type || "OTHER";
    if (!groups[key]) groups[key] = [];
    groups[key].push(r);
  }

  const sortedKeys = Object.keys(groups).sort((a, b) => {
    const ai = ORDER.indexOf(a);
    const bi = ORDER.indexOf(b);
    if (ai === -1 && bi === -1) return a.localeCompare(b);
    if (ai === -1) return 1;
    if (bi === -1) return -1;
    return ai - bi;
  });

  const groupHtml = sortedKeys
    .map(key => hazardGroupCard(key, groups[key]))
    .join("");

  container.innerHTML = headerHtml("Aviation Hazards") + groupHtml;
}

// ── Hazard rendering helpers (live mode) ────────────────────────────────

function hazardColorClass(hazardType, subtype) {
  if (hazardType === "SIGMET") return "red";
  if (hazardType === "CWA") return "amber";
  if (hazardType === "AIRMET") {
    const sub = (subtype || "").toUpperCase();
    if (["IFR", "ICE", "TURB", "MTN_OBSCN", "LLWS"].includes(sub)) return "amber";
    return "amber";
  }
  return "gray";
}

function hazardGroupCard(hazardType, records) {
  const colorClass = hazardColorClass(hazardType);
  return `<div class="card">
  <h3 style="margin:0 0 8px">
    <span class="badge ${colorClass}">${safeText(hazardType)}</span>
    <span class="muted" style="font-size:13px;margin-left:8px">${records.length} active</span>
  </h3>
  <span class="source-doctrine">Aviation Weather Truth — AviationWeather.gov</span>
  ${records.map(hazardEntryHtml).join("")}
</div>`;
}

function hazardEntryHtml(r) {
  const colorClass = hazardColorClass(r.hazard_type, r.subtype);

  const altLine = r.altitude_top_ft
    ? `<p class="muted" style="font-size:12px">Tops: FL${String(Math.round(r.altitude_top_ft / 100)).padStart(3, "0")}${r.altitude_bottom_ft ? " / Base: FL" + Math.round(r.altitude_bottom_ft / 100) : ""}</p>`
    : "";

  const movementLine = r.movement_speed_kt
    ? `<p class="muted" style="font-size:12px">Movement: ${r.movement_from_degrees}° at ${r.movement_speed_kt} kt</p>`
    : "";

  const affectedLine = (r.affected_airports && r.affected_airports.length)
    ? `<p class="muted" style="font-size:12px">Affected airports: ${r.affected_airports.slice(0, 10).join(", ")}${r.affected_airports.length > 10 ? " +more" : ""}</p>`
    : "";

  const translationHtml = r.translation
    ? `<p style="font-size:13px;margin:8px 0 2px">${safeText(r.translation.replace("TravelCast translation — generated from AviationWeather.gov source text.", "").trim())}</p>` +
      `<span class="source-doctrine">TravelCast translation — generated from AviationWeather.gov source text.</span>`
    : "";

  return `<div style="border-top:1px solid var(--line);margin-top:12px;padding-top:12px">
  <div style="display:flex;gap:8px;flex-wrap:wrap;align-items:center;margin-bottom:6px">
    <span class="badge ${colorClass}">${safeText(r.hazard_type || "")}</span>
    ${r.subtype ? `<span class="badge gray" style="font-size:11px">${safeText(r.subtype)}</span>` : ""}
    <strong style="font-size:13px">${safeText(r.hazard_id || "")}</strong>
    <span class="muted" style="font-size:12px">Valid: ${formatDateTime(r.begins_at_utc)} – ${formatDateTime(r.ends_at_utc)}</span>
  </div>
  ${altLine}
  ${movementLine}
  ${affectedLine}
  ${translationHtml}
  <details style="margin-top:8px">
    <summary class="muted" style="font-size:11px;cursor:pointer">Raw advisory text</summary>
    <div class="pre" style="font-size:11px;margin-top:6px;white-space:pre-wrap">${safeText(r.raw_text || "—")}</div>
  </details>
</div>`;
}

// ── Demo mode (unchanged) ───────────────────────────────────────────────

function renderDemoHazards() {
  const d = sampleAviationHazards;
  const html =
    headerHtml("Aviation Hazards") +
    `<div class="warning">Demo Mode: sample hazards shown. Live mode reads AviationWeather.gov API.</div>` +
    `<div class="grid">` +
      hazardSection("Convective SIGMETs", d.sigmets, "red") +
      hazardSection("AIRMETs", d.airmets, "amber") +
    `</div>` +
    `<div class="grid">` +
      hazardSection("Center Weather Advisories (CWA)", d.cwas, "amber") +
      pirepSection(d.pireps) +
    `</div>` +
    doctrineBadge(`${DOCTRINE_LABEL} · Demo data`);
  document.querySelector("#aviation-hazards").innerHTML = html;
}

// ── Shared HTML helpers ─────────────────────────────────────────────────

function headerHtml(title) {
  return `<div class="card">
    <h2>${safeText(title)}</h2>
    <p class="muted">SIGMETs, AIRMETs, CWAs, and PIREPs affecting TravelCast airports.</p>
    <span class="source-doctrine">${DOCTRINE_LABEL}</span>
  </div>`;
}

function loadingHtml(title) {
  return `<div class="card"><h2>${safeText(title)}</h2><p class="muted">Loading…</p></div>`;
}

function emptyStateHtml(headline, detail, sourceLabel) {
  return `<div class="card">
    <p><strong>${safeText(headline)}</strong></p>
    <p class="muted">${safeText(detail)}</p>
    <span class="source-doctrine">${safeText(sourceLabel)}</span>
  </div>`;
}

function errorHtml(message, sourceLabel) {
  return `<div class="card">
    <p class="muted">Query error: ${safeText(message)}</p>
    <span class="source-doctrine">${safeText(sourceLabel)}</span>
  </div>`;
}

function doctrineBadge(label) {
  return `<div style="padding:6px 0 2px"><span class="source-doctrine">${safeText(label)}</span></div>`;
}

function hazardSection(title, items, cls) {
  return `<div class="card ${cls}">
    <div class="label">${safeText(title)}</div>
    <h3>${items.length} Active</h3>
    ${items.map(h => hazardEntry(h, cls)).join("")}
  </div>`;
}

function hazardEntry(h, cls) {
  return `<div style="border-top:1px solid var(--line);margin-top:12px;padding-top:12px">
    <span class="badge ${cls}">${safeText(h.hazard_type)}</span>
    <p><strong>${safeText(h.affected_area)}</strong></p>
    <p class="muted">Valid: ${formatDateTime(h.valid_from)} – ${formatDateTime(h.valid_to)}</p>
    <p class="muted">Levels: ${safeText(h.flight_levels, "—")}${h.movement ? ` · Movement: ${h.movement}` : ""}</p>
    <div class="pre">${safeText(h.text)}</div>
  </div>`;
}

function pirepSection(pireps) {
  return `<div class="card gray">
    <div class="label">PIREPs</div>
    <h3>${pireps.length} Recent</h3>
    ${pireps.map(pirepEntry).join("")}
  </div>`;
}

function pirepEntry(p) {
  return `<div style="border-top:1px solid var(--line);margin-top:12px;padding-top:12px">
    <span class="badge amber">${safeText(p.intensity, "Report")}</span>
    <p><strong>${safeText(p.location)}</strong> · ${safeText(p.aircraft_type)}</p>
    <p class="muted">${formatDateTime(p.report_time)}</p>
    <div class="pre">${safeText(p.text)}</div>
  </div>`;
}
