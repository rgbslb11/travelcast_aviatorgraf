# SOURCE_DOCTRINE.md — TravelCast Source Authority

## Tier 1 official / operational sources

### FAA NAS Status

Use for:

- airport operational events
- ground stops
- ground delay programs
- airport closures
- arrival/departure runway configuration when provided
- AAR when provided

Label as:

```text
Current Operational Impact — FAA NAS Status
```

### FAA ATCSCC

Use for:

- operations plans
- terminal planned initiatives
- enroute planned initiatives
- route programs
- SWAP/CDR/capping/tunneling context

Label as:

```text
Operational Planning — FAA ATCSCC
```

### AviationWeather.gov

Use for:

- METAR
- TAF
- PIREP
- AIRMET/SIGMET
- CWA
- TCF
- aviation weather products

Label as:

```text
Aviation Weather Truth — AviationWeather.gov
```

### NWS/api.weather.gov

Use for:

- public forecasts
- public alerts
- CAP/WEA text
- grid forecast
- point forecast
- forecast weather-impact proxy

Label as:

```text
Forecast Weather Impact — NWS forecast proxy
```

Do not label as an official FAA delay forecast.

## Tier 2 enrichment/archive

- IEM
- Open-Meteo
- Synoptic
- OurAirports for development runway reference

## Tier 3 commercial/enrichment

- Baron
- OpenWeather Road Risk
- AeroDataBox
- FlightAware
- AirLabs

These are not FAA/NWS operational truth unless explicitly licensed and labeled.
