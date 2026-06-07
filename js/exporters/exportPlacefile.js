import { appState } from "../state.js";

export function airportPlacefile(records) {
  const isLive = !appState.demoModeActive;
  const now = new Date().toISOString();
  const lines = [
    `Title: TravelCast Airport Impact Overlay`,
    `; Generated: ${now}`,
    `; Source mode: ${isLive ? "live" : "demo"}`,
    `; Doctrine: Current Operational Impact — FAA NAS Status`,
    `; NWS forecast impact is a proxy — NOT an official FAA delay forecast`,
    `Refresh: 60`,
    `Font: 1, 11, 1, "Arial"`,
  ];

  (records || []).forEach(r => {
    if (!r.latitude || !r.longitude) return;
    const impact = r.current_delay_type || r.forecast_impact_label || "Monitor";
    const delay = r.avg_delay_minutes ? ` - ${r.avg_delay_minutes} min avg` : "";
    const freshTag = (r.freshness_status && r.freshness_status !== "fresh")
      ? ` [${r.freshness_status}]`
      : "";
    const label = `${r.iata || r.airport_id}: ${impact}${delay}${freshTag}`;
    lines.push(`Text: ${r.latitude},${r.longitude},1,"${label}"`);
  });

  lines.push(`End:`);
  return lines.join("\n") + "\n";
}
