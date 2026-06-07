export function airportRowsToGeoJSON(records) {
  return { type:"FeatureCollection", features:(records||[]).filter(r=>r.latitude&&r.longitude).map(airportFeature) };
}
export function selectedAirportToGeoJSON(record) {
  return { type:"FeatureCollection", features: record ? [airportFeature(record)] : [] };
}
function airportFeature(r) {
  return { type:"Feature", properties:{ title:`${r.iata || r.airport_id} ${r.current_delay_type || r.forecast_impact_label || "Monitor"}`, airport_id:r.airport_id, iata:r.iata, icao:r.icao, impact:r.current_delay_type || r.forecast_impact_label, avg_delay_minutes:r.avg_delay_minutes, reason:r.current_reason || r.forecast_impact_reasons, source:r.source_summary || "TravelCast generated package" }, geometry:{ type:"Point", coordinates:[Number(r.longitude), Number(r.latitude)] } };
}
