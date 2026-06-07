export function dashboardJson(records) {
  return { product: "travelcast_airport_status_dashboard", generated_at: new Date().toISOString(), source: "TravelCast AviatorGraf Prep", demo: true, records };
}
