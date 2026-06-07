import { APP_CONFIG } from "./config.js";
import { appState, loadQueue } from "./state.js";
import { renderAirportDashboard } from "./modules/airportDashboard.js";
import { renderAirportDetail } from "./modules/airportDetail.js";
import { renderAviationHazards } from "./modules/aviationWeather.js";
import { renderFaaOps } from "./modules/faaOps.js";
import { renderRoutecast } from "./modules/routecast.js";
import { renderGraphicsQueue } from "./modules/graphicsQueue.js";
import { renderSourceHealth } from "./modules/sourceHealth.js";

function setupTabs() {
  document.querySelectorAll(".tabs button").forEach(btn => {
    btn.addEventListener("click", () => {
      document.querySelectorAll(".tabs button").forEach(b => b.classList.remove("active"));
      document.querySelectorAll(".tab-panel").forEach(p => p.classList.remove("active"));
      btn.classList.add("active");
      document.querySelector(`#${btn.dataset.tab}`).classList.add("active");
    });
  });
}

async function init() {
  document.querySelector("#mode-banner").textContent = APP_CONFIG.demoMode ? "Demo Mode" : "Supabase Mode";
  setupTabs();
  loadQueue();
  await renderAirportDashboard();
  renderAirportDetail(appState.airportStatusRecords[0]);
  renderAviationHazards();
  renderFaaOps();
  renderRoutecast();
  renderGraphicsQueue();
  renderSourceHealth();
  document.querySelector("#mode-banner").textContent = appState.demoModeActive ? "Demo Mode — sample data" : "Supabase Mode — live views";
}

init().catch(err => {
  console.error(err);
  document.querySelector("main").innerHTML = `<div class="warning">App initialization failed: ${err.message}</div>`;
});
