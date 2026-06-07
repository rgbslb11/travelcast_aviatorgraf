export const sampleAviationHazards = {
  source: "Aviation Weather Truth — AviationWeather.gov",
  fetched_at: "2026-06-06T21:30:00Z",
  sigmets: [
    {
      hazard_id: "SIGMET_ECHO_1",
      hazard_type: "Convective SIGMET",
      issuance_time: "2026-06-06T18:00:00Z",
      valid_from: "2026-06-06T18:00:00Z",
      valid_to: "2026-06-06T22:00:00Z",
      affected_area: "Denver / Kansas City FIR",
      flight_levels: "SFC–FL380",
      movement: "ENE 25 KT",
      text: "CONVECTIVE SIGMET ECHO — Severe thunderstorms over southern Colorado and northeast Kansas. Tops to FL380. Moving ENE at 25 kts. Hail to 1.5 in. possible."
    }
  ],
  airmets: [
    {
      hazard_id: "AIRMET_SIERRA_CO",
      hazard_type: "AIRMET SIERRA",
      issuance_time: "2026-06-06T17:45:00Z",
      valid_from: "2026-06-06T18:00:00Z",
      valid_to: "2026-06-07T00:00:00Z",
      affected_area: "Colorado / Utah / Nevada",
      flight_levels: "SFC–030",
      movement: "",
      text: "AIRMET SIERRA — IFR conditions. Ceilings below 1000 ft AGL and/or visibility below 3 SM in precipitation and/or mist. Conditions expected to improve after 0300Z."
    },
    {
      hazard_id: "AIRMET_TANGO_ROCKIES",
      hazard_type: "AIRMET TANGO",
      issuance_time: "2026-06-06T17:45:00Z",
      valid_from: "2026-06-06T18:00:00Z",
      valid_to: "2026-06-07T00:00:00Z",
      affected_area: "Rocky Mountain region",
      flight_levels: "SFC–FL180",
      movement: "",
      text: "AIRMET TANGO — Moderate turbulence below FL180. Mountain wave activity associated with 30-knot westerly winds over the Continental Divide."
    }
  ],
  cwas: [
    {
      hazard_id: "CWA_ZDV_01",
      hazard_type: "Center Weather Advisory",
      issuance_time: "2026-06-06T21:30:00Z",
      valid_from: "2026-06-06T21:30:00Z",
      valid_to: "2026-06-06T23:30:00Z",
      affected_area: "Denver ARTCC (ZDV)",
      flight_levels: "SFC–FL200",
      movement: "ENE 30 KT",
      text: "ZDV CWA 01 — Developing convection within 20 NM of KDEN. Tops to FL250. Moving ENE at 30 kts. Low-level wind shear possible on approaches to 16L and 17R."
    }
  ],
  pireps: [
    {
      hazard_id: "PIREP_DEN_01",
      hazard_type: "PIREP",
      report_time: "2026-06-06T21:15:00Z",
      location: "30 NE DEN / FL350",
      aircraft_type: "B737",
      intensity: "Moderate",
      text: "UA /OV DEN030030 /TM 2115 /FL350 /TP B737 /TB MOD /RM SEAT BELT SIGN ON BRIEF ENCOUNTER CLEARED AREA"
    },
    {
      hazard_id: "PIREP_DEN_02",
      hazard_type: "PIREP",
      report_time: "2026-06-06T21:05:00Z",
      location: "15 SW DEN / FL080",
      aircraft_type: "B738",
      intensity: "Light-Moderate",
      text: "UA /OV DEN210015 /TM 2105 /FL080 /TP B738 /TB LGT-MOD /RM ON APPROACH KDEN ENCOUNTERED LGT-MOD CHOP"
    }
  ]
};
