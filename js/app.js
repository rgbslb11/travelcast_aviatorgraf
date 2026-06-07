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

function updateBanner() {
  const banner = document.querySelector("#mode-banner");
  // Reset to base class then add state variant
  banner.className = "mode-banner";

  const { connectionStatus, warnings } = appState;
  if (connectionStatus === "configured") {
    banner.textContent = "Supabase Connected — live views";
    banner.classList.add("connected");
  } else if (connectionStatus === "failed") {
    banner.textContent = "Supabase Query Failed — using demo fallback";
    banner.classList.add("failed");
  } else {
    banner.textContent = "Supabase Not Configured — demo mode";
    banner.classList.add("demo");
  }

  if (warnings.length) {
    const warnEl = document.querySelector("#connection-warnings");
    if (warnEl) {
      warnEl.style.display = "";
      warnEl.innerHTML = warnings
        .map(w => `<div class="warning">${w}</div>`)
        .join("");
    }
  }
}

async function init() {
  setupTabs();
  loadQueue();
  await renderAirportDashboard();
  renderAirportDetail(appState.airportStatusRecords[0]);
  await renderAviationHazards();
  await renderFaaOps();
  await renderRoutecast();
  renderGraphicsQueue();
  renderSourceHealth();
  updateBanner();
}

init().catch(err => {
  console.error(err);
  document.querySelector("main").innerHTML =
    `<div class="warning">App initialization failed: ${err.message}</div>`;
});
