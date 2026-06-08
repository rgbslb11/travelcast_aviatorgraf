# Source Failure Playbook — TravelCast AviatorGraf Prep

What to do when each data source fails. For each source: what it controls, whether it is mission-critical, what is affected, and when to stop broadcasting from it.

---

## FAA NAS Status (`nasstatus.faa.gov/api/airport-events`)

**What it controls:**
- Airport operational events (GDPs, Ground Stops, Airport Closures, Arrival/Departure Delays)
- `current_delay_type`, `avg_delay_minutes`, `max_delay_minutes`, `current_reason`, `arrival_runway`, `departure_runway`, `aar` fields in Airport Status Board
- Operational impact badges (red / amber)
- Active events table in ATCSCC / FAA Ops tab

**Mission-critical:** Yes — for any operational impact copy.

**Affected tabs/panels:**
- Airport Status Board (operational impact column)
- Airport Detail (Current Operational Impact panel)
- ATCSCC / FAA Ops tab (active events table)
- All exporters (operational fields in Package JSON, Placefile, GeoJSON)

**Cached/stale use:** Yes, with explicit caution.
- Last cached snapshot in `data/raw/faa_nas_status.json` can be used to rebuild snapshots without a new pull.
- Stale operational data may show programs that have ended or miss programs that have started.
- Label clearly as `stale` if more than 30 minutes old.

**Operator language:**
- OK to say: "As of [timestamp], FAA NAS Status showed a Ground Delay Program at [airport]."
- Do NOT say: "There is currently a Ground Delay Program" if data is stale.
- If endpoint is completely unavailable: say "FAA NAS Status data is currently unavailable — operational information not confirmed."

**When to stop using:**
- Stop using operational impact copy when Source Health shows `stale` (> 3 hours) or `no_runs` for FAA NAS Status.
- Do not invent or speculate about programs not in source data.

---

## FAA ATCSCC Advisories / Ops Plan (`fly.faa.gov`)

**What it controls:**
- ATCSCC Operations Plan advisory text (full plan, sections, translations)
- ATCSCC / FAA Ops tab — ops plan card and section cards

**Mission-critical:** Situational — required for Operations Plan copy, not for individual airport status.

**Affected tabs/panels:**
- ATCSCC / FAA Ops tab (ops plan card and sections only — the active events table above it runs from FAA NAS Status)

**Cached/stale use:** Yes — ops plans are typically valid for the planning day.
- A stored ops plan advisory does not expire immediately; valid_from_utc and valid_until_utc are stored.
- Check `valid_until_utc` before citing plan details.

**Operator language:**
- OK to say: "ATCSCC Operations Plan Advisory #[number] for [date] notes [X]."
- Do NOT say: "ATCSCC has issued an ops plan" if `no_plan_found` is logged — this means no ops plan was active during the last pull.
- If auto-discovery fails but you have a known advisory URL: use `--url` flag to manually ingest.

**When to stop using:**
- Stop citing ops plan details when `valid_until_utc` has passed.
- If `parse_status` is `partial` or `failed`, verify section content manually before using on-air.
- Do not invent advisory content. If sections are NIL, report NIL.

---

## AviationWeather METAR/TAF (`aviationweather.gov`)

**What it controls:**
- METAR: `metar_condition`, `flight_category`, `metar_wind` in Airport Status Board
- TAF: forecast briefing in Airport Detail
- `metar_observation_time` freshness

**Mission-critical:** Yes — for any weather-condition or flight-category copy.

**Affected tabs/panels:**
- Airport Status Board (METAR column)
- Airport Detail (METAR and TAF panels)
- Package JSON exports (METAR/TAF fields)

**Cached/stale use:** Limited — METAR is time-sensitive.
- METAR: do not use if more than 1.5–2 hours old (aviation standard).
- TAF: valid for 24–30 hours from issuance but should be from the current TAF cycle.
- Source Health `aging` for AviationWeather means last successful METAR pull was 30 min – 3 hours ago.

**Operator language:**
- OK to say: "As of [METAR time], [airport] reported [condition]."
- Include the METAR observation time in any on-air reference.
- If METAR is unavailable: say "[airport] METAR currently unavailable."

**When to stop using:**
- Stop using METAR-based flight category if the observation is more than 2 hours old.
- Stop using TAF if it is past its valid period or from the previous TAF cycle.
- Source Health `stale` or `no_runs` for AviationWeather = do not cite weather conditions on-air.

---

## AviationWeather SIGMET/AIRMET/CWA (`aviationweather.gov`)

**What it controls:**
- Aviation hazard records in `aviation_hazard_products` table
- Aviation Hazards tab content
- Hazard mentions in RouteCast text

**Mission-critical:** Yes — for any hazards copy.

**Affected tabs/panels:**
- Aviation Hazards tab (all content)
- RouteCast (hazard_mentions flag)

**Cached/stale use:** Limited — hazards have their own valid times.
- Each stored hazard has `begins_at_utc` and `ends_at_utc`. The view filters to `ends_at_utc > now()`.
- Stale stored hazards that have already expired are filtered out automatically.
- If the pull hasn't run recently, new hazards issued after the last pull will not appear.

**Operator language:**
- OK to say: "An active SIGMET for [type] is in effect [area] valid until [time]. Source: AviationWeather.gov."
- Do NOT say a hazard affects a specific airport unless `affected_airports` explicitly includes that airport code or the geometry overlaps the airport area.
- If no hazards are displayed: say "No active aviation hazards on record" — do not speculate.

**When to stop using:**
- Stop citing hazard details when the hazard's `ends_at_utc` has passed.
- If Source Health shows `stale` or `no_runs` for AviationWeather: note that hazard data may not be current.

---

## NWS API (`api.weather.gov`)

**What it controls:**
- `forecast_impact_color`, `forecast_impact_label`, `forecast_impact_reasons` in Airport Status Board
- NWS forecast panel in Airport Detail
- Forecast Weather Impact — NWS forecast proxy badges

**Mission-critical:** No — NWS is a forecast proxy, not operational truth.

**Affected tabs/panels:**
- Airport Status Board (Forecast Weather Impact column)
- Airport Detail (NWS forecast panel)
- Forecast-impact filter options

**Cached/stale use:** Yes — NWS forecasts are valid for hours.
- NWS forecasts are updated every hour or less for active events.
- A 2–4 hour old forecast is generally still usable for graphics prep.
- `stale` in Source Health (> 3 hours) means the forecast data is getting old.

**Operator language:**
- Always label as "Forecast Weather Impact — NWS forecast proxy."
- Never say "FAA is forecasting a delay" based on NWS data.
- Never say "NWS predicts a ground delay program."
- OK to say: "NWS is forecasting [condition] for [airport area], which may be a factor for travel."

**When to stop using:**
- NWS proxy data is never used for current operational impact — only for forecast-impact guidance.
- If NWS API is unavailable, forecast badge may show stale data — make clear data age when noting weather impact.

---

## RouteCast Derived Snapshots (`rebuild_routecast_snapshots.py`)

**What it controls:**
- Route enrichment cards in RouteCast tab
- Origin/destination status, ATCSCC text mentions, hazard mentions

**Mission-critical:** No — RouteCast is a TravelCast enrichment layer, not an official source.

**Affected tabs/panels:**
- RouteCast tab

**Cached/stale use:** Yes — route summaries are rebuilt from cached data.
- RouteCast does not make new API calls. It enriches from `data/raw/faa_nas_status.json`, `atcscc_ops_plan_raw.json`, and `aviation_hazards_parsed.json`.
- Freshness of route summaries depends on how recent the underlying caches are.
- Source Health `stale` for RouteCast means the snapshot rebuild hasn't run recently.

**Operator language:**
- Always label as "Forecast Weather Impact — NWS forecast proxy" for the route-impact summary.
- Include "NOT an official FAA delay forecast" when citing route prep status.
- OK to say: "Our RouteCast tool shows elevated prep status for DFW-JFK based on current FAA/NAS and hazard data."
- Do NOT say: "FAA is reporting delays on the DFW-JFK route."

**When to stop using:**
- RouteCast prep status is supplemental only. If origin/destination operational impacts are stale, RouteCast assessments are also unreliable.

---

## Supabase Read Failure

**Symptom:** Banner reads "Supabase Query Failed — using demo fallback." App falls back to demo data.

**What is affected:** All live data — Airport Status Board, Aviation Hazards, ATCSCC, RouteCast, Source Health.

**Immediate response:**
1. Open browser console (F12) — note the specific error.
2. Verify Supabase project is online at your Supabase dashboard.
3. Verify `js/config.js` anon key is correct.
4. If transient: hard-refresh to retry.
5. If persistent: pull scripts can still run locally; you can work from exported files.

**Operator language:**
- Do not use live data claims if the app is in demo fallback mode.
- If presenting exported files that were downloaded before the failure: note the export timestamp.

---

## Supabase Write Failure

**Symptom:** Pull script logs `HTTP 400` or `HTTP 403` errors. Records not written to Supabase.

**What is affected:** Future views will not update. Currently stored data remains intact until overwritten.

**Immediate response:**
1. Check the error message in the pull script log (usually JSON with `message` field).
2. Common causes: wrong schema (column mismatch), RLS policy blocking writes, service-role key incorrect.
3. Run `python scripts\audit\audit_no_secrets.py` to verify `.env` structure.
4. If HTTP 400 "column not found": a schema migration may need to be re-applied.
5. If HTTP 403: re-apply `sql/02_grant_service_role_write.sql`.

**Operator language:**
- Data in Supabase remains usable until it goes stale.
- If writes are failing for more than one pull cycle, note data age explicitly.
