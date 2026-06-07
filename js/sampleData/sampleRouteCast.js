export const sampleRoutes = [
  {
    route_id: "DEN_DTW_DEMO",
    origin_iata: "DEN",
    destination_iata: "DTW",
    label: "Denver → Detroit",
    estimated_departure: "2026-06-06T23:00:00Z",
    route_string: "KDEN LINDZ3 LINDZ Q68 GLD V4 SUX V100 DBQ KARTR3 KDTW",
    overall_impact_color: "Amber",
    overall_impact_label: "Monitor",
    impact_summary: "GDP at DEN causing departure delays. Convection near KARFO and southeast Colorado. Enroute VFR after GLD. DTW arrival normal.",
    source: "Forecast Weather Impact — NWS forecast proxy",
    waypoints: [
      { id: "KDEN", label: "DEN (Departure)", impact_color: "Red", note: "GDP active. Avg 63 min delay. GDP reason: Thunderstorms." },
      { id: "KARFO", label: "KARFO (SE Colorado)", impact_color: "Amber", note: "Convective SIGMET ECHO in area. Tops FL380." },
      { id: "GLD", label: "Goodland VOR (KS)", impact_color: "Green", note: "Clear of convection." },
      { id: "SUX", label: "Sioux City VOR (IA)", impact_color: "Green", note: "VFR." },
      { id: "DBQ", label: "Dubuque VOR (IA)", impact_color: "Green", note: "VFR." },
      { id: "KDTW", label: "DTW (Arrival)", impact_color: "Green", note: "No active delays. VFR." }
    ]
  },
  {
    route_id: "SFO_ORD_DEMO",
    origin_iata: "SFO",
    destination_iata: "ORD",
    label: "San Francisco → Chicago O'Hare",
    estimated_departure: "2026-06-06T22:30:00Z",
    route_string: "KSFO TRUKN2 TRUKN Q88 OAL J1 DNJ J80 DBQ SWAPP2 KORD",
    overall_impact_color: "Amber",
    overall_impact_label: "Monitor",
    impact_summary: "GDP at SFO causing departure delays. Low ceilings at departure. Enroute clear. ORD arrival normal.",
    source: "Forecast Weather Impact — NWS forecast proxy",
    waypoints: [
      { id: "KSFO", label: "SFO (Departure)", impact_color: "Red", note: "GDP active. Avg 65 min delay. GDP reason: Low ceilings / Marine layer." },
      { id: "OAL", label: "Coaldale VOR (NV)", impact_color: "Green", note: "Clear." },
      { id: "DNJ", label: "Dove Creek VOR (CO)", impact_color: "Green", note: "VFR." },
      { id: "DBQ", label: "Dubuque VOR (IA)", impact_color: "Green", note: "VFR." },
      { id: "KORD", label: "ORD (Arrival)", impact_color: "Green", note: "No active delays. Mostly sunny." }
    ]
  },
  {
    route_id: "MIA_JFK_DEMO",
    origin_iata: "MIA",
    destination_iata: "JFK",
    label: "Miami → New York JFK",
    estimated_departure: "2026-06-06T22:00:00Z",
    route_string: "KMIA WINCO5 WINCO THNDR Q105 SAV CAMRN2 KJFK",
    overall_impact_color: "Green",
    overall_impact_label: "Normal",
    impact_summary: "Minor departure delay at MIA (volume). Enroute and JFK arrival normal.",
    source: "Forecast Weather Impact — NWS forecast proxy",
    waypoints: [
      { id: "KMIA", label: "MIA (Departure)", impact_color: "Amber", note: "Departure delay avg 15 min. Volume/multi-taxi." },
      { id: "SAV", label: "Savannah VOR (GA)", impact_color: "Green", note: "VFR." },
      { id: "KJFK", label: "JFK (Arrival)", impact_color: "Green", note: "No active delays. Showers possible later." }
    ]
  }
];
