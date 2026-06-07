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

  // Records present — render them (future: typed hazard sections)
  const rows = records.map(r => `
    <tr>
      <td><span class="badge red">${safeText(r.hazard_type, "Hazard")}</span></td>
      <td>${safeText(r.affected_area, "—")}</td>
      <td>${formatDateTime(r.valid_from)}</td>
      <td>${formatDateTime(r.valid_to)}</td>
      <td>${safeText(r.flight_levels, "—")}</td>
      <td class="muted">${safeText(r.hazard_text, "—")}</td>
    </tr>`).join("");

  container.innerHTML =
    headerHtml("Aviation Hazards") +
    `<div class="table-shell"><table>
      <thead><tr>
        <th>Type</th><th>Area</th><th>Valid From</th><th>Valid To</th>
        <th>Levels</th><th>Text</th>
      </tr></thead>
      <tbody>${rows}</tbody>
    </table></div>` +
    doctrineBadge(DOCTRINE_LABEL);
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
