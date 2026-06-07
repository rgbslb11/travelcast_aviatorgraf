import { appState } from "../state.js";

export function dashboardJson(records) {
  const isLive = !appState.demoModeActive;
  return {
    product:           "travelcast_airport_status_dashboard",
    product_version:   "1.0",
    generated_at:      new Date().toISOString(),
    source_mode:       isLive ? "live" : "demo",
    airport_count:     records.length,
    source_doctrine: {
      operational:      "Current Operational Impact — FAA NAS Status",
      forecast:         "Forecast Weather Impact — NWS forecast proxy",
      aviation_weather: "Aviation Weather Truth — AviationWeather.gov",
      graphics:         "Graphics Output — TravelCast generated package",
    },
    nws_proxy_notice:
      "Forecast weather impact is an NWS forecast proxy and is NOT an official FAA delay forecast.",
    freshness_summary: _freshnessSummary(records),
    records,
  };
}

function _freshnessSummary(records) {
  const counts = { fresh: 0, aging: 0, stale: 0, unknown: 0 };
  for (const r of records) {
    const s = r.freshness_status || "unknown";
    counts[s] = (counts[s] || 0) + 1;
  }
  return counts;
}
