import { sampleFaaOps } from "../sampleData/sampleFaaOps.js";
import { safeText, formatDateTime } from "../utils.js";

export function renderFaaOps() {
  const d = sampleFaaOps;
  const html =
    headerCard(d) +
    groundProgramsCard(d.ground_programs) +
    initiativesCard(d.planned_initiatives);
  document.querySelector("#faa-ops").innerHTML = html;
}

function headerCard(d) {
  return `<div class="card">
    <h2>ATCSCC / FAA Ops Plan</h2>
    <p class="muted">Ground programs, traffic initiatives, and reroutes affecting the NAS.</p>
    <div class="label">${safeText(d.source)} · Fetched ${formatDateTime(d.fetched_at)}</div>
    <div class="warning" style="margin-top:12px">Demo Mode: sample ops plan shown. Live mode reads FAA ATCSCC advisory feed.</div>
  </div>`;
}

function groundProgramsCard(programs) {
  return `<div class="card">
    <h3>Ground Programs</h3>
    <div class="table-shell"><table>
      <thead><tr>
        <th>Airport</th><th>Type</th><th>Status</th><th>Reason</th>
        <th>Rate</th><th>Avg Delay</th><th>Max Delay</th><th>Scope</th><th>Expiration</th>
      </tr></thead>
      <tbody>${programs.map(gdpRow).join("")}</tbody>
    </table></div>
  </div>`;
}

function gdpRow(g) {
  const cls = g.status === "Active" ? "red" : "amber";
  return `<tr>
    <td><strong>${safeText(g.airport_iata)}</strong><br><span class="muted">${safeText(g.airport_icao)}</span></td>
    <td>${safeText(g.advisory_type)}</td>
    <td><span class="badge ${cls}">${safeText(g.status)}</span></td>
    <td>${safeText(g.reason)}</td>
    <td>${safeText(g.program_rate, "—")}</td>
    <td><strong>${safeText(g.avg_delay_minutes, "—")}</strong>${g.avg_delay_minutes ? " min" : ""}</td>
    <td>${safeText(g.max_delay_minutes, "—")}${g.max_delay_minutes ? " min" : ""}</td>
    <td class="muted">${safeText(g.scope, "—")}</td>
    <td class="muted">${formatDateTime(g.expiration)}</td>
  </tr>`;
}

function initiativesCard(initiatives) {
  return `<div class="card">
    <h3>Planned Initiatives</h3>
    ${initiatives.map(initiativeEntry).join("")}
  </div>`;
}

function initiativeEntry(i) {
  const cls = i.status === "Active" ? "amber" : "gray";
  return `<div style="border-top:1px solid var(--line);margin-top:12px;padding-top:12px">
    <span class="badge ${cls}">${safeText(i.status)}</span>
    <strong style="margin-left:8px">${safeText(i.initiative_type)}</strong>
    <p>${safeText(i.description)}</p>
    <p class="muted">Effective: ${formatDateTime(i.effective)} · Expires: ${formatDateTime(i.expiration)}</p>
  </div>`;
}
