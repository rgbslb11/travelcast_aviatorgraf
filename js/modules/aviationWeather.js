export function renderAviationHazards() {
  document.querySelector("#aviation-hazards").innerHTML = `<div class="card"><h2>Aviation Hazards</h2><p>This panel will read aviation_weather_advisories, pireps, and public_weather_alerts when live Supabase mode is enabled.</p><div class="grid"><div class="card"><h3>AIRMET/SIGMET</h3><p class="muted">No live records in demo mode.</p></div><div class="card"><h3>CWA / PIREP</h3><p class="muted">No live records in demo mode.</p></div></div></div>`;
}
