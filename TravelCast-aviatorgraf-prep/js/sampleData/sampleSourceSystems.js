export const sampleSourceSystems = [
  {
    "source_system_id": "faa_nas_status",
    "display_name": "FAA NAS Status",
    "trust_tier": 1,
    "official_source": true,
    "mission_critical_allowed": true,
    "category": "traffic_management",
    "notes": "Operational traffic-management truth for airport events."
  },
  {
    "source_system_id": "atcscc_advisories",
    "display_name": "FAA ATCSCC Advisories",
    "trust_tier": 1,
    "official_source": true,
    "mission_critical_allowed": true,
    "category": "traffic_management",
    "notes": "Operations plans, terminal/enroute planned events, SWAP/CDR context."
  },
  {
    "source_system_id": "aviationweather_api",
    "display_name": "AviationWeather.gov API",
    "trust_tier": 1,
    "official_source": true,
    "mission_critical_allowed": true,
    "category": "aviation_weather",
    "notes": "METAR, TAF, PIREP, AIRMET/SIGMET, CWA."
  },
  {
    "source_system_id": "nws_api",
    "display_name": "NWS API / api.weather.gov",
    "trust_tier": 1,
    "official_source": true,
    "mission_critical_allowed": true,
    "category": "public_weather",
    "notes": "Public forecasts, alerts, CAP/WEA, forecast-impact proxy."
  },
  {
    "source_system_id": "baron_weather_api_trial",
    "display_name": "Baron Weather API Trial",
    "trust_tier": 3,
    "official_source": false,
    "mission_critical_allowed": false,
    "category": "commercial_enrichment",
    "notes": "Development/testing enrichment only."
  }
];
