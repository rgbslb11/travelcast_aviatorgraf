import { sampleSourceSystems } from "../sampleData/sampleSourceSystems.js";
export function renderSourceHealth() {
  document.querySelector("#source-health").innerHTML = `<div class="card"><h2>Source Health</h2><p class="muted">Source registry and trust-tier doctrine.</p></div><div class="table-shell"><table><thead><tr><th>Source</th><th>Tier</th><th>Official</th><th>Mission Critical</th><th>Notes</th></tr></thead><tbody>${sampleSourceSystems.map(s=>`<tr><td><strong>${s.display_name}</strong><br><span class="muted">${s.source_system_id}</span></td><td>${s.trust_tier}</td><td>${s.official_source}</td><td>${s.mission_critical_allowed}</td><td>${s.notes}</td></tr>`).join("")}</tbody></table></div>`;
}
