import { sampleAviationHazards } from "../sampleData/sampleAviationHazards.js";
import { safeText, formatDateTime } from "../utils.js";

export function renderAviationHazards() {
  const d = sampleAviationHazards;
  const html =
    headerCard(d) +
    `<div class="grid">` +
      hazardSection("Convective SIGMETs", d.sigmets, "red") +
      hazardSection("AIRMETs", d.airmets, "amber") +
    `</div>` +
    `<div class="grid">` +
      hazardSection("Center Weather Advisories (CWA)", d.cwas, "amber") +
      pirepSection(d.pireps) +
    `</div>`;
  document.querySelector("#aviation-hazards").innerHTML = html;
}

function headerCard(d) {
  return `<div class="card">
    <h2>Aviation Hazards</h2>
    <p class="muted">SIGMETs, AIRMETs, CWAs, and PIREPs affecting TravelCast airports.</p>
    <div class="label">${safeText(d.source)} · Fetched ${formatDateTime(d.fetched_at)}</div>
    <div class="warning" style="margin-top:12px">Demo Mode: sample hazards shown. Live mode reads AviationWeather.gov API.</div>
  </div>`;
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
