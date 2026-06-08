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
  let plan = null;
  let sections = [];
  let queryError = null;
  let fetchedAt = null;

  try {
    const client = await getSupabaseClient();

    // Query 1: All airports with their latest operational snapshot
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

    // Query 2: Latest ATCSCC Operations Plan (failure is non-fatal)
    try {
      const { data: planData, error: planErr } = await client
        .from("v_atcscc_operations_plan_latest")
        .select("*")
        .limit(1);
      if (planErr) {
        console.warn("faaOps: v_atcscc_operations_plan_latest query failed:", planErr.message);
      } else {
        plan = (planData && planData.length > 0) ? planData[0] : null;
      }
    } catch (planEx) {
      console.warn("faaOps: ops plan query exception:", planEx.message);
    }

    // Query 3: Plan sections, only if a plan was found (failure is non-fatal)
    if (plan) {
      try {
        const { data: secData, error: secErr } = await client
          .from("v_atcscc_operations_plan_sections")
          .select("*");
        if (secErr) {
          console.warn("faaOps: v_atcscc_operations_plan_sections query failed:", secErr.message);
        } else {
          sections = secData || [];
        }
      } catch (secEx) {
        console.warn("faaOps: plan sections query exception:", secEx.message);
      }
    }
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
    opsPlancardHtml(plan, sections) +
    sectionCardsHtml(sections);

  container.innerHTML = html;
}

// ── Active events card (existing, unchanged) ────────────────────────────

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

// ── ATCSCC Operations Plan card ─────────────────────────────────────────

function opsPlancardHtml(plan, sections) {
  // No data stored in Supabase yet
  if (plan === null) {
    return `<div class="card">
      <h3>ATCSCC Operations Plan</h3>
      <p class="muted">No Operations Plan stored in Supabase yet. Run <code>pull_atcscc_ops_plan.py</code> to fetch and store the latest plan.</p>
      <span class="source-doctrine">Current Operational Impact — FAA NAS / ATCSCC</span>
    </div>`;
  }

  // Plan fetch ran but no advisory was issued today
  if (plan.parse_status === "no_plan_found") {
    return `<div class="card">
      <h3>ATCSCC Operations Plan</h3>
      <p class="muted">No ATCSCC Operations Plan advisory was found in today's FAA NAS data. Active GDPs and events are shown in the table above.</p>
      <p class="muted">Last checked: ${formatDateTime(plan.fetched_at_utc)}</p>
      <span class="source-doctrine">Current Operational Impact — FAA NAS / ATCSCC</span>
    </div>`;
  }

  // Plan has content (parse_status = 'ok' or 'partial')
  const sourceLink = plan.source_url
    ? `<div><a href="${safeText(plan.source_url)}" class="muted" target="_blank" rel="noopener">Source Advisory ↗</a></div>`
    : "";

  const titleLine = plan.title
    ? `<p class="muted" style="font-size:12px">${safeText(plan.title)}</p>`
    : "";

  return `<div class="card">
    <h3>ATCSCC Operations Plan</h3>
    <div style="display:flex;flex-wrap:wrap;gap:16px;margin:8px 0 12px">
      <div><span class="muted">Advisory:</span> <strong>${plan.advisory_number ? "#" + safeText(plan.advisory_number) : "—"}</strong></div>
      <div><span class="muted">Date:</span> <strong>${safeText(plan.advisory_date) || "—"}</strong></div>
      <div><span class="muted">Event Time:</span> <strong>${safeText(plan.event_time) || "—"}</strong></div>
      <div><span class="muted">Fetched:</span> ${formatDateTime(plan.fetched_at_utc)}</div>
      ${sourceLink}
    </div>
    ${titleLine}
    <span class="source-doctrine">Current Operational Impact — FAA NAS / ATCSCC</span>
  </div>`;
}

// ── Plan section cards ──────────────────────────────────────────────────

function sectionCardsHtml(sections) {
  if (!sections || sections.length === 0) return "";

  const contentSections = sections.filter(s => s.has_content === true || s.has_content === "true");
  const nilSections = sections.filter(s => s.has_content !== true && s.has_content !== "true");

  const contentHtml = contentSections.map(section => {
    let translationHtml = "";
    if (
      section.translation &&
      section.translation !== section.raw_text
    ) {
      const cleanTranslation = section.translation
        .replace("TravelCast translation — generated from FAA ATCSCC source text.", "")
        .trim();
      translationHtml = `<p style="margin:10px 0 0;font-size:12px;color:var(--text)"><strong>Plain language:</strong> ${safeText(cleanTranslation)}</p>
      <p class="source-doctrine" style="margin:4px 0 0">TravelCast translation — generated from FAA ATCSCC source text.</p>`;
    }

    return `<div class="card">
      <h4 style="margin:0 0 8px">${safeText(section.section_display_name)}</h4>
      <div class="pre" style="font-size:12px;line-height:1.5;white-space:pre-wrap">${safeText(section.raw_text)}</div>
      ${translationHtml}
    </div>`;
  }).join("");

  let nilHtml = "";
  if (nilSections.length > 0) {
    const nilNames = nilSections.map(s => safeText(s.section_display_name)).join(", ");
    nilHtml = `<div class="card">
      <p class="muted" style="font-size:12px">NIL or empty sections: ${nilNames}</p>
      <span class="source-doctrine">Current Operational Impact — FAA NAS / ATCSCC</span>
    </div>`;
  }

  return contentHtml + nilHtml;
}

// ── Next webinar extractor ──────────────────────────────────────────────

function nextWebinarLine(sections) {
  if (!sections || sections.length === 0) return null;
  const found = sections.find(s => s.section_key === "NEXT_WEBINAR" || s.section_display_name === "NEXT_WEBINAR");
  if (!found || !found.raw_text) return null;
  return found.raw_text.trim() || null;
}

// ── Shared header / loading ─────────────────────────────────────────────

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
