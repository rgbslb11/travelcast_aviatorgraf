# DATA_CONTRACT.md — TravelCast Data Contract

## Primary frontend view

The frontend should primarily read:

```text
v_airport_status_dashboard
```

## Required columns

```text
airport_id
iata
icao
region
display_name
airport_name
city
state
latitude
longitude

dominant_sky_condition
high_temperature_f
low_temperature_f
forecast_impact_color
forecast_impact_label
forecast_impact_reasons
forecast_icon_id
forecast_icon_url

current_delay_type
current_status_code
current_reason
avg_delay_minutes
max_delay_minutes
delay_summary
arrival_runway
departure_runway
aar

metar_condition
flight_category
metar_wind
metar_visibility
metar_observed_at

taf_trend
taf_next_risk_window

overall_impact_color
overall_impact_label
last_updated_at
freshness_status
source_summary
```

## Detail views

```text
v_airport_detail_current
v_airport_metar_latest
v_airport_taf_latest
v_airport_taf_timeline
v_airport_operational_events_latest
v_airport_runway_context
v_airport_alerts_active
```

## Source health view

```text
v_source_health_dashboard
```

## Graphics queue candidate view

```text
v_graphics_queue_candidates
```

## Frontend behavior

If Supabase is not configured or a view is missing, use demo data and show a clear warning.

The frontend should not read raw canonical tables except for source health or diagnostic/debug pages.
