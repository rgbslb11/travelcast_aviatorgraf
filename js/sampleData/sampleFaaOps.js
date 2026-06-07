export const sampleFaaOps = {
  source: "Operational Planning — FAA ATCSCC",
  fetched_at: "2026-06-06T21:00:00Z",
  ground_programs: [
    {
      advisory_id: "GDP_KDEN_001",
      advisory_type: "Ground Delay Program",
      status: "Active",
      airport_iata: "DEN",
      airport_icao: "KDEN",
      reason: "Weather / Thunderstorms",
      program_rate: 24,
      avg_delay_minutes: 63,
      max_delay_minutes: 386,
      scope: "Departure scoping: ZAB, ZLA, ZLC, ZOA, ZSE",
      effective: "2026-06-06T18:00:00Z",
      expiration: "2026-06-07T02:00:00Z"
    },
    {
      advisory_id: "GDP_KSFO_001",
      advisory_type: "Ground Delay Program",
      status: "Active",
      airport_iata: "SFO",
      airport_icao: "KSFO",
      reason: "Low ceilings / Marine layer",
      program_rate: 16,
      avg_delay_minutes: 65,
      max_delay_minutes: 120,
      scope: "Departure scoping: ZSE, ZLA, ZOA",
      effective: "2026-06-06T06:00:00Z",
      expiration: "2026-06-06T22:00:00Z"
    }
  ],
  planned_initiatives: [
    {
      initiative_id: "MIT_ZDV_001",
      initiative_type: "Miles-in-Trail (MIT)",
      status: "Active",
      description: "80 NM MIT eastbound departures from KDEN via ZDV.",
      effective: "2026-06-06T21:00:00Z",
      expiration: "2026-06-07T00:00:00Z"
    },
    {
      initiative_id: "REROUTE_ZDV_002",
      initiative_type: "Reroute",
      status: "Planned",
      description: "Preferred CDR for DEN–EWR: LINDZ3 LINDZ Q68 GLD J80 DBQ SWAPP2. Avoiding convective corridor south of I-70.",
      effective: "2026-06-06T22:00:00Z",
      expiration: "2026-06-07T04:00:00Z"
    }
  ]
};
