import { sampleAviationHazards } from "../sampleData/sampleAviationHazards.js";
import { safeText, formatDateTime } from "../utils.js";

export function renderAviationHazards() {
  const d = sampleAviationHazards;
  document.querySelector("#aviation-hazards").innerHTML = `
    <div class="card">
      <h2>Aviation Hazards</h2>
      <p class="muted">SIGMETs, AIRMETs, CWAs, and PIREPs affecting TravelCast airports.</p>
      <div class="label">${safeText(d.source)} · Fetched ${formatDateTime(d.fetched_at)}</div>
      <div class="warning" style="margin-top:12px">Demo Mode: sample hazards shown. Live mode reads AviationWeather.gov API.</div>
    </div>
    <div class="grid">
      <div class="card red">
        <div class="label">Convective SIGMETs</div>
        <h3>${d.sigmets.length} Active</h3>
        ${d.sigmets.map(h => hazardCard(h, "red")).join("")}
      </div>
      <div class="card amber">
        <div class="label">AIRMETs</div>
        <h3>${d.airmets.length} Active</h3>
        ${d.airmets.map(h => hazardCard(h, "amber")).join("")}
      </div>
    </div>
    <div class="grid">
      <div class="card amber">
        <div class="label">Center Weather Advisories (CWA)</div>
        <h3>${d.cwas.length} Active</h3>
        ${d.cwas.map(h => hazardCard(h, "amber")).join("")}
      </div>
      <div class="card gray">
        <div class="label">PIREPs</div>
        <h3>${d.pireps.length} Recent</h3>
        ${d.pireps.map(pirepCard).join("")}
      </div>
    </div>`;
}

function hazardCard(h, cls) {
  return `<div style="border-top:1px solid var(--line);margin-top:12px;padding-top:12px">
    <strong class="badge ${cls}">${safeText(h.hazard_type)}</strong>
    <p><strong>${safeText(h.affected_area)}</strong></p>
    <p class="muted">Valid: ${formatDateTime(h.valid_from)} – ${formatDateTime(h.valid_to)}</p>
    <p class="muted">Levels: ${safeText(h.flight_levels,"—")}${h.movement ? ` · Movement: ${h.movement}` : ""}</p>
    <div class="pre">${safeText(h.text)}</div>
  </div>`;
}

function pirepCard(p) {
  return `<div style="border-top:1px solid var(--line);margin-top:12px;padding-top:12px">
    <strong class="badge amber">${safeText(p.intensity,"Report")}</strong>
    <p><strong>${safeText(p.location)}</strong> · ${safeText(p.aircraft_type)}</p>
    <p class="muted">${formatDateTime(p.report_time)}</p>
    <div class="pre">${safeText(p.text)}</div>
  </div>`;
}
