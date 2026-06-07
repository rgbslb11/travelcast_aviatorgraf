export function airportPlacefile(records) {
  const lines = ['Title: TravelCast Airport Impact Overlay','Refresh: 60','Font: 1, 11, 1, "Arial"'];
  (records||[]).forEach(r => {
    if (!r.latitude || !r.longitude) return;
    const label = `${r.iata || r.airport_id}: ${r.current_delay_type || r.forecast_impact_label || "Monitor"}${r.avg_delay_minutes ? ` - ${r.avg_delay_minutes} min avg` : ""}`;
    lines.push(`Text: ${r.latitude},${r.longitude},1,"${label}"`);
  });
  lines.push('End:');
  return lines.join('\n') + '\n';
}
