import { appState } from "../state.js";

export function airportRowsToGeoJSON(records) {
  const features = (records || []).filter(r => r.latitude && r.longitude).map(airportFeature);
  return {
    type:            "FeatureCollection",
    generated_at:    new Date().toISOString(),
    source_mode:     appState.demoModeActive ? "demo" : "live",
    feature_count:   features.length,
    source_doctrine: "Current Operational Impact — FAA NAS Status | Forecast Weather Impact — NWS forecast proxy | Aviation Weather Truth — AviationWeather.gov",
    nws_proxy_notice: "Forecast weather impact is an NWS forecast proxy and is NOT an official FAA delay forecast.",
    features,
  };
}

export function selectedAirportToGeoJSON(record) {
  return {
    type:            "FeatureCollection",
    generated_at:    new Date().toISOString(),
    source_mode:     appState.demoModeActive ? "demo" : "live",
    feature_count:   record ? 1 : 0,
    nws_proxy_notice: "Forecast weather impact is an NWS forecast proxy and is NOT an official FAA delay forecast.",
    features:        record ? [airportFeature(record)] : [],
  };
}

function airportFeature(r) {
  return {
    type: "Feature",
    properties: {
      title:                `${r.iata || r.airport_id} ${r.current_delay_type || r.forecast_impact_label || "Monitor"}`,
      airport_id:           r.airport_id,
      iata:                 r.iata,
      icao:                 r.icao,
      display_name:         r.display_name || r.airport_name,
      city:                 r.city,
      region:               r.region,
      overall_impact_color: r.overall_impact_color,
      current_delay_type:   r.current_delay_type,
      avg_delay_minutes:    r.avg_delay_minutes,
      forecast_impact_color: r.forecast_impact_color,
      forecast_impact_label: r.forecast_impact_label,
      flight_category:      r.flight_category,
      freshness_status:     r.freshness_status,
      last_updated_at:      r.last_updated_at,
      reason:               r.current_reason || r.forecast_impact_reasons,
      source:               r.source_summary || "Graphics Output — TravelCast generated package",
    },
    geometry: {
      type:        "Point",
      coordinates: [Number(r.longitude), Number(r.latitude)],
    },
  };
}
