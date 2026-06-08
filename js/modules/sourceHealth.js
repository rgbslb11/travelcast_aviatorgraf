import { sampleSourceSystems } from "../sampleData/sampleSourceSystems.js";
import { safeText, formatDateTime } from "../utils.js";
import { isSupabaseConfigured, getSupabaseClient } from "../supabaseClient.js";
import { appState } from "../state.js";

export async function renderSourceHealth() {
  const container = document.querySelector("#source-health");
  container.innerHTML = checklistHtml() + loadingSourcesHtml();

  let sources = [];
  let queryError = null;

  if (isSupabaseConfigured()) {
    try {
      const client = await getSupabaseClient();
      const { data, error } = await client
        .from("v_source_health_dashboard")
        .select("*")
        .order("trust_tier")
        .order("source_system_id");
      if (error) throw new Error(error.message);
      sources = data || [];
    } catch (err) {
      queryError = err.message;
    }
  }

  const sourcesHtml = queryError
    ? `<div class="card"><p class="muted">Source health query error: ${safeText(queryError)}</p></div>`
    : sources.length
      ? liveSourcesHtml(sources)
      : demoSourcesHtml();

  container.innerHTML = checklistHtml() + sourcesHtml;
}

// ── Operator checklist ──────────────────────────────────────────────────

function checklistHtml() {
  const isLive = !appState.demoModeActive;
  const statusBadge = isLive
    ? `<span class="badge green">Supabase Connected</span>`
    : `<span class="badge gray">Demo / Not Connected</span>`;
  const airportCount = appState.airportStatusRecords.length;

  return `<div class="card">
    <h2>Day-One Operator Checklist</h2>
    <p class="muted">Pre-broadcast verification steps for TravelCast AviatorGraf Prep.</p>
    <div style="margin:4px 0 10px">${statusBadge} ${airportCount ? `<span class="badge blue">${airportCount} airports loaded</span>` : ""}</div>
    <ol style="margin:0;padding-left:20px;line-height:1.9">
      <li>Start local server: <code>python -m http.server 8080</code> → open <code>http://localhost:8080</code></li>
      <li>Refresh data: <code>python scripts/pull/pull_all.py --dry-run</code> (verify no failures)</li>
      <li>Live pull: <code>python scripts/pull/pull_all.py</code> (writes to Supabase)</li>
      <li>Refresh browser — banner should read <strong>Supabase Connected — live views</strong></li>
      <li>Airport Status Board → confirm <strong>71 airports</strong> render with live source labels</li>
      <li>ATCSCC / FAA Ops → verify active FAA/NAS programs table (or "No active programs")</li>
      <li>Source Health (this tab) → confirm all four official sources show recent feed runs</li>
      <li>Select any Red/Amber airport → Airport Detail → <strong>Download Package JSON</strong></li>
      <li>Review <code>source_mode</code> in downloaded JSON — must read <strong>"live"</strong>, not "demo"</li>
      <li>Add airport to Graphics Queue → Mark Ready → export Placefile for GR2/GR3 overlay</li>
    </ol>
    <p class="source-doctrine" style="margin-top:10px">
      NWS forecast impact is a proxy — NOT an official FAA delay forecast.
      Use FAA NAS Status for operational truth.
    </p>
  </div>`;
}

// ── Live source health ──────────────────────────────────────────────────

function liveSourcesHtml(sources) {
  const tierLabel = { 1: "Official", 2: "Enrichment", 3: "Commercial" };

  // Alert banner for official mission-critical sources that are stale or have no runs
  const criticalAlerts = sources.filter(
    s => s.official_source && s.mission_critical_allowed &&
         (s.freshness_status === "stale" || s.freshness_status === "no_runs")
  );
  let alertHtml = "";
  if (criticalAlerts.length > 0) {
    const names = criticalAlerts.map(s => safeText(s.display_name)).join(", ");
    alertHtml = `<div class="warning" style="margin-bottom:12px">
      <strong>Official source alert:</strong> ${names} — freshness is
      ${criticalAlerts.map(s => safeText(s.freshness_status)).join(", ")}.
      Run <code>pull_all.py</code> and verify before using data on-air.
    </div>`;
  }

  const rows = sources.map(s => {
    const freshCls = s.freshness_status === "fresh"   ? "green"
      : s.freshness_status === "aging"   ? "amber"
      : s.freshness_status === "stale"   ? "red"
      : s.freshness_status === "no_runs" ? "gray" : "amber";
    const tier = tierLabel[s.trust_tier] || `Tier ${s.trust_tier}`;
    return `<tr>
      <td>
        <strong>${safeText(s.display_name)}</strong><br>
        <span class="muted">${safeText(s.source_system_id)}</span>
      </td>
      <td>${tier}</td>
      <td>${s.official_source ? "✓" : "—"}</td>
      <td>${s.mission_critical_allowed ? "✓" : "—"}</td>
      <td><span class="badge ${freshCls}">${safeText(s.freshness_status, "no_runs")}</span></td>
      <td class="muted">${formatDateTime(s.last_success_at)}</td>
      <td>${s.runs_last_24h ?? "0"}</td>
      <td class="muted">${safeText(s.last_error, "—")}</td>
    </tr>`;
  }).join("");

  return `<div class="card">
    <h2>Source Health</h2>
    <p class="muted">Live feed-run telemetry from Supabase. Run <code>pull_all.py</code> to update.</p>
    ${alertHtml}
  </div>
  <div class="table-shell"><table>
    <thead><tr>
      <th>Source</th><th>Tier</th><th>Official</th><th>Mission Critical</th>
      <th>Freshness</th><th>Last Success</th><th>Runs (24h)</th><th>Last Error</th>
    </tr></thead>
    <tbody>${rows}</tbody>
  </table></div>`;
}

// ── Demo fallback ───────────────────────────────────────────────────────

function demoSourcesHtml() {
  const tierLabel = { 1: "Official", 2: "Enrichment", 3: "Commercial" };
  const rows = sampleSourceSystems.map(s => {
    const tier = tierLabel[s.trust_tier] || `Tier ${s.trust_tier}`;
    return `<tr>
      <td>
        <strong>${safeText(s.display_name)}</strong><br>
        <span class="muted">${safeText(s.source_system_id)}</span>
      </td>
      <td>${tier}</td>
      <td>${s.official_source ? "✓" : "—"}</td>
      <td>${s.mission_critical_allowed ? "✓" : "—"}</td>
      <td><span class="badge gray">no_runs</span></td>
      <td class="muted">—</td>
      <td>0</td>
      <td class="muted">—</td>
    </tr>`;
  }).join("");

  return `<div class="card">
    <h2>Source Health</h2>
    <p class="muted">Source registry and trust-tier doctrine. Connect Supabase for live feed-run telemetry.</p>
    <div class="warning">Demo Mode: feed-run data unavailable. Live mode queries v_source_health_dashboard.</div>
  </div>
  <div class="table-shell"><table>
    <thead><tr>
      <th>Source</th><th>Tier</th><th>Official</th><th>Mission Critical</th>
      <th>Freshness</th><th>Last Success</th><th>Runs (24h)</th><th>Last Error</th>
    </tr></thead>
    <tbody>${rows}</tbody>
  </table></div>`;
}

function loadingSourcesHtml() {
  return `<div class="card"><p class="muted">Loading source health…</p></div>`;
}
