import { sampleFaaOps } from "../sampleData/sampleFaaOps.js";
import { safeText, formatDateTime, impactClass } from "../utils.js";
import { isSupabaseConfigured, getSupabaseClient } from "../supabaseClient.js";

const DOCTRINE_LABEL = "Current Operational Impact — FAA NAS Status";

export async function renderFaaOps() {
  if (isSupabaseConfigured()) {
    await renderLiveFaaOps();
  } else {
    renderDemoFaaOps();
  }
}

// ── Live mode ───────────────────────────────────────────────────────────

async function renderLiveFaaOps() {
  const container = document.querySelector("#faa-ops");
  container.innerHTML = loadingHtml();

  let events = [];
  let allAirports = [];
  let queryError = null;
  let fetchedAt = null;

  try {
    const client = await getSupabaseClient();

    // All airports with their latest operational snapshot
    const { data: allData, error: allErr } = await client
      .from("v_airport_operational_events_latest")
      .select("*")
      .order("region")
      .order("iata");
    if (allErr) throw new Error(allErr.message);
    allAirports = allData || [];
    fetchedAt = new Date().toISOString();

    // Active programs: non-NORMAL status
    events = allAirports.filter(
      r => r.current_status_code && r.current_status_code !== "NORMAL"
    );
  } catch (err) {
    queryError = err.message;
  }

  if (queryError) {
    container.innerHTML =
      headerHtml(null) +
      `<div class="card"><p class="muted">Query error: ${safeText(queryError)}</p>
       <span class="source-doctrine">${DOCTRINE_LABEL}</span></div>`;
    return;
  }

  const html =
    headerHtml(fetchedAt) +
    activeEventsCard(events, allAirports.length) +
    atcsccAdvisoryNotice();

  container.innerHTML = html;
}

function activeEventsCard(events, totalAirports) {
  if (events.length === 0) {
    return `<div class="card">
      <h3>Active FAA/NAS Programs</h3>
      <p class="muted">No active ground programs, ground stops, or airport closures across ${totalAirports} monitored airports.</p>
      <span class="source-doctrine">${DOCTRINE_LABEL}</span>
    </div>`;
  }

  const rows = events.map(r => {
    const cls = impactClass(r.current_impact_color);
    return `<tr>
      <td><strong>${safeText(r.iata || r.airport_id)}</strong><br>
          <span class="muted">${safeText(r.icao)} · ${safeText(r.city)}</span></td>
      <td>${safeText(r.region)}</td>
      <td><span class="badge ${cls}">${safeText(r.current_delay_type, "Active")}</span></td>
      <td>${safeText(r.current_reason, "—")}</td>
      <td><strong>${r.avg_delay_minutes ?? "—"}</strong>${r.avg_delay_minutes ? " min" : ""}</td>
      <td>${r.max_delay_minutes ?? "—"}${r.max_delay_minutes ? " min" : ""}</td>
      <td class="muted">${formatDateTime(r.snapshot_at)}</td>
      <td><span class="badge ${impactClass(r.freshness_status)}">${safeText(r.freshness_status, "unknown")}</span></td>
    </tr>`;
  }).join("");

  return `<div class="card">
    <h3>Active FAA/NAS Programs <span class="badge red" style="font-size:11px">${events.length} Active</span></h3>
    <span class="source-doctrine">${DOCTRINE_LABEL}</span>
    <div class="table-shell" style="margin-top:12px"><table>
      <thead><tr>
        <th>Airport</th><th>Region</th><th>Program Type</th><th>Reason</th>
        <th>Avg Delay</th><th>Max Delay</th><th>Snapshot</th><th>Freshness</th>
      </tr></thead>
      <tbody>${rows}</tbody>
    </table></div>
  </div>`;
}

function atcsccAdvisoryNotice() {
  return `<div class="card">
    <h3>ATCSCC Advisory Feed</h3>
    <p class="muted">ATCSCC advisory text (NOTAMs, traffic initiatives, reroutes) is fetched by the pull engine and cached locally in <code>data/raw/atcscc_advisories.json</code>.</p>
    <p class="muted">Full advisory text is not yet stored in Supabase. Run <code>pull_atcscc_ops_plan.py</code> to refresh the local cache.</p>
    <span class="source-doctrine">${DOCTRINE_LABEL} · Local cache only</span>
  </div>`;
}

function headerHtml(fetchedAt) {
  const ts = fetchedAt ? `· ${formatDateTime(fetchedAt)}` : "";
  return `<div class="card">
    <h2>ATCSCC / FAA Ops Plan</h2>
    <p class="muted">Ground programs, traffic initiatives, and reroutes affecting the NAS.</p>
    <span class="source-doctrine">${DOCTRINE_LABEL} ${ts}</span>
  </div>`;
}

function loadingHtml() {
  return `<div class="card"><h2>ATCSCC / FAA Ops Plan</h2><p class="muted">Loading…</p></div>`;
}

// ── Demo mode (unchanged behavior) ─────────────────────────────────────

function renderDemoFaaOps() {
  const d = sampleFaaOps;
  const html =
    `<div class="card">
      <h2>ATCSCC / FAA Ops Plan</h2>
      <p class="muted">Ground programs, traffic initiatives, and reroutes affecting the NAS.</p>
      <div class="label">${safeText(d.source)} · Fetched ${formatDateTime(d.fetched_at)}</div>
      <div class="warning" style="margin-top:12px">Demo Mode: sample ops plan shown. Live mode reads FAA ATCSCC advisory feed.</div>
    </div>` +
    groundProgramsCard(d.ground_programs) +
    initiativesCard(d.planned_initiatives);
  document.querySelector("#faa-ops").innerHTML = html;
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
