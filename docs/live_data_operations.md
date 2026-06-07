# Live Data Operations

## Operating model

```text
airport master list
  -> Supabase reference tables
  -> server-side pulling scripts
  -> raw source payload retention / feed_runs
  -> normalized ontology tables
  -> status snapshots and views
  -> TravelCast AviatorGraf Prep frontend
  -> JSON / GeoJSON / placefile / broadcast packages
```

## Day One manual cycle

```bash
python scripts/load/load_airports_to_supabase.py --dry-run
python scripts/pull/pull_faa_nas_status.py --all-active
python scripts/pull/pull_aviationweather_metar_taf.py --all-active
python scripts/pull/pull_nws_forecasts.py --all-active
python scripts/pull/rebuild_airport_status_snapshots.py --all-active
```

## Refresh recommendations

- FAA NAS Status: 1-5 minutes during active prep, 5-15 minutes otherwise.
- METAR: 5-10 minutes.
- TAF: 30-60 minutes.
- NWS forecasts: 30-120 minutes depending airport tier.
- ATCSCC Ops Plan: 5-15 minutes around planning cycles; 30 minutes otherwise.

## Frontend rule

The browser reads Supabase views and generated exports only. It does not call real-time source APIs directly.
