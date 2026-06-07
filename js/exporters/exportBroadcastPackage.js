import { appState } from "../state.js";

export function airportBroadcastPackage(a) {
  const isLive = !appState.demoModeActive;
  const code = a?.iata || a?.airport_id || "APT";
  const hasOps = a?.current_status_code && a.current_status_code !== "NORMAL";

  const headline = hasOps
    ? `${code} ${a.current_delay_type} Active`
    : `${code} Forecast Weather Impact: ${a?.forecast_impact_label || "Monitor"}`;
  const subheadline = hasOps
    ? (a.current_reason || "Operational impact")
    : (a?.dominant_sky_condition || "Weather monitored");
  const lower = hasOps
    ? `${code} ${a.current_delay_type} — avg delay ${a.avg_delay_minutes ?? "—"} min — ${a.current_reason || "Operational impact"}`
    : `${code} ${a.forecast_impact_label || "Monitor"} — ${a.dominant_sky_condition || "Forecast monitored"}`;

  return {
    package_type:    "airport_status_card",
    package_version: "1.0",
    generated_at:    new Date().toISOString(),
    valid_until:     new Date(Date.now() + 10 * 60000).toISOString(),
    source_mode:     isLive ? "live" : "demo",

    airport: {
      airport_id: a?.airport_id,
      iata:       a?.iata,
      icao:       a?.icao,
      name:       a?.airport_name || a?.display_name,
      city:       a?.city,
      state:      a?.state,
      region:     a?.region,
      latitude:   a?.latitude,
      longitude:  a?.longitude,
    },

    operational_status: {
      source:            "Current Operational Impact — FAA NAS Status",
      event_type:        a?.current_delay_type,
      status_code:       a?.current_status_code,
      avg_delay_minutes: a?.avg_delay_minutes,
      max_delay_minutes: a?.max_delay_minutes,
      reason:            a?.current_reason,
      arrival_runway:    a?.arrival_runway,
      departure_runway:  a?.departure_runway,
      aar:               a?.aar,
      freshness_status:  a?.freshness_status,
      last_updated_at:   a?.last_updated_at,
    },

    forecast_weather_impact: {
      source:         "Forecast Weather Impact — NWS forecast proxy",
      condition:      a?.dominant_sky_condition,
      impact_color:   a?.forecast_impact_color,
      impact_label:   a?.forecast_impact_label,
      impact_reasons: a?.forecast_impact_reasons,
      icon_id:        a?.forecast_icon_id,
    },

    aviation_weather: {
      source:               "Aviation Weather Truth — AviationWeather.gov",
      metar_condition:      a?.metar_condition,
      flight_category:      a?.flight_category,
      wind:                 a?.metar_wind,
      visibility:           a?.metar_visibility,
      observed_at:          a?.metar_observed_at,
      taf_trend:            a?.taf_trend,
      taf_next_risk_window: a?.taf_next_risk_window,
    },

    graphics: {
      headline,
      subheadline,
      lower_third:     lower,
      long_card_text:  `${headline}. ${subheadline}. ${a?.delay_summary || a?.forecast_impact_reasons || "TravelCast monitoring."}`,
      impact_color:    a?.overall_impact_color || a?.forecast_impact_color,
      recommended_layout: "airport_status_card",
      source_footer:   "Operational source: FAA NAS Status when present. Forecast impact: NWS forecast proxy. Aviation weather: AviationWeather METAR/TAF.",
    },

    source_labels: [
      "Current Operational Impact — FAA NAS Status",
      "Forecast Weather Impact — NWS forecast proxy",
      "Aviation Weather Truth — AviationWeather.gov",
      "Graphics Output — TravelCast generated package",
    ],

    nws_proxy_notice:
      "Forecast weather impact is an NWS forecast proxy and is NOT an official FAA delay forecast.",

    limitations: isLive
      ? ["Forecast weather impact is not an official FAA delay forecast."]
      : [
          "Demo data only — not live operational data.",
          "Forecast weather impact is not an official FAA delay forecast.",
        ],
  };
}
