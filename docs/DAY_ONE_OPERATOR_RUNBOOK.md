# Day-One Operator Runbook — TravelCast AviatorGraf Prep

Internal operations guide for local TravelCast graphics-prep use.

---

## Prerequisites

- Python 3.8+ installed and on PATH
- `.env` file present in `scripts/pull/` with `SUPABASE_URL`, `SUPABASE_SERVICE_ROLE_KEY`, and `NWS_USER_AGENT`
- `js/config.js` configured locally with Supabase project URL and anon key, `demoMode: false`
- Supabase SQL migrations applied (`sql/00` through `sql/06`)

---

## 1. Start the Local Server

Open a terminal in the project root and run:

```
python -m http.server 8080
```

Leave this terminal running for the session.

---

## 2. Open the App

```
http://localhost:8080
```

---

## 3. Confirm Supabase Connected Mode

The top banner should read:

```
Supabase Connected — live views
```

with a **green** left border.

If it reads "Demo Mode" or "Query Failed," see TROUBLESHOOTING.md.

---

## 4. Confirm 71 Airports Loaded

On the **Airport Status Board** tab:

- The count label should show **71 of 71 airports**
- If the "All Operational" filter is active, all 71 should appear

If fewer than 71 appear, check that `sql/01_seed_focus_airports.sql` has been applied and a live pull has run.

---

## 5. Run Dry-Run Pulls (Verify Before Live)

Verify all pull scripts work without writing to Supabase:

```
python scripts\pull\pull_all.py --dry-run
```

All 6 scripts should show `PASSED`. No `failed_scripts` in the final log line. Elapsed time ~50–90 seconds.

If any script fails the dry-run, do not proceed to live pull. See TROUBLESHOOTING.md.

---

## 6. Run Live Pulls (Write to Supabase)

```
python scripts\pull\pull_all.py
```

This writes airport snapshots, METAR/TAF, NWS forecasts, aviation hazards, and RouteCast enrichments to Supabase. Watch for any HTTP errors in the output.

---

## 7. Refresh the Browser

After a live pull, hard-refresh the browser to load updated data:

```
Ctrl+Shift+R  (Windows/Linux)
Cmd+Shift+R   (Mac)
```

---

## 8. Read Source Health

Go to the **Source Health** tab.

The table shows one row per data source. Key columns:

| Column | Meaning |
|---|---|
| Tier | Official = Tier 1, Enrichment = Tier 2, Commercial = Tier 3 |
| Official | ✓ = official FAA/NWS source |
| Mission Critical | ✓ = required for broadcast use |
| Freshness | See below |
| Last Success | Timestamp of last successful pull run |
| Runs (24h) | How many feed runs completed in the last 24 hours |
| Last Error | Error message from most recent failed run, if any |

---

## 9. Interpret Freshness States

| Badge | Color | Meaning |
|---|---|---|
| `fresh` | Green | Last successful pull < 30 minutes ago |
| `aging` | Amber | Last successful pull 30 min – 3 hours ago |
| `stale` | Red | Last successful pull > 3 hours ago |
| `no_runs` | Gray | No successful pull on record |

For **Official / Mission Critical** sources (`✓` in both columns), aim for `fresh` before going to air.
For enrichment and commercial sources, `aging` or `stale` is non-blocking.

---

## 10. Check the Airport Status Board

Go to the **Airport Status Board** tab.

The table shows:
- **Forecast Weather Impact** — NWS forecast proxy. Green / Amber / Red badges.
  - Labeled `Forecast Weather Impact — NWS forecast proxy`. Not an official FAA delay forecast.
- **Current Operational Impact** — FAA NAS Status. Real active events.
  - Labeled `Current Operational Impact — FAA NAS Status`.

---

## 11. Use Search

Type in the search box to filter by airport code, city, or name. Example: type `SFO` or `Denver`.

---

## 12. Use Region Filter

Select a region from the dropdown to show only airports in that region (e.g., West Coast, Northeast).

---

## 13. Use Operational-Impact Filter

| Option | Shows |
|---|---|
| All Operational | All 71 airports |
| Operational: Red | Airport Closures, Ground Stops |
| Operational: Amber | GDPs, Arrival/Departure Delays |
| No Active Event | Airports with no active FAA/NAS program |
| Ground Delay Program | Only GDP airports |
| Ground Stop | Only Ground Stop airports |
| Airport Closure | Only Airport Closure airports |
| Departure Delay | Only Departure Delay airports |
| Arrival Delay | Only Arrival Delay airports |

These filters use **FAA NAS operational data only**. NWS forecast colors are not mixed in.

---

## 14. Use Forecast-Impact Filter

Select a forecast badge color (Red / Amber / Green) to filter by NWS forecast-impact proxy.
This is a weather-proxy only — not an operational delay filter.

---

## 15. Open Airport Detail

Click the **Detail** button on any airport row. This opens the Airport Detail tab showing:

- METAR and flight category (Aviation Weather Truth — AviationWeather.gov)
- TAF / forecast briefing (Aviation Weather Truth — AviationWeather.gov)
- Current operational event (Current Operational Impact — FAA NAS Status)
- Runway configuration / AAR
- NWS forecast impact proxy (Forecast Weather Impact — NWS forecast proxy)

---

## 16. Use Aviation Hazards

Go to the **Aviation Hazards** tab.

Displays active SIGMETs, AIRMETs, and CWAs from AviationWeather.gov. Grouped by hazard type.
Source label: `Aviation Weather Truth — AviationWeather.gov`.

To refresh: run `python scripts\pull\pull_aviation_hazards.py` then hard-refresh the browser.

---

## 17. Use ATCSCC / FAA Ops Plan

Go to the **ATCSCC / FAA Ops Plan** tab.

The top section shows active FAA/NAS programs (GDPs, Ground Stops, Airport Closures) pulled from FAA NAS Status.

The bottom section shows the ATCSCC Operations Plan advisory if one is stored. If no plan was active during the last pull, the card shows "no_plan_found."

To manually ingest a specific advisory:

```
python scripts\pull\pull_atcscc_ops_plan.py --url "<FAA Operations Plan URL>"
```

---

## 18. Use RouteCast

Go to the **RouteCast** tab.

Shows enriched summaries for the 6 configured starter routes (DFW-JFK, DFW-ORD, DFW-ATL, SFO-ORD, JFK-MIA, DEN-DTW). Each card shows origin and destination airport operational/forecast status and a prep-status badge.

**The route prep status is not an official FAA route forecast. It is a TravelCast text-matching enrichment.**

To refresh: run `python scripts\pull\rebuild_routecast_snapshots.py` (this uses cached data only — no new API calls).

---

## 19. Use Graphics Queue

Click **Queue** on any airport row to add it to the Graphics Queue (last tab).

Each queued item shows:
- Airport and product type
- Status badge: Draft / Ready / Needs Freshness Review / Used
- FAA/NAS impact and NWS forecast badges
- Export buttons: Package JSON, GeoJSON, Placefile

Use **Mark Ready** to flag fresh/aging items as broadcast-ready.
Use **Mark Used** after the item has been used in broadcast.

---

## 20. Export Package JSON

On the Airport Detail tab or in the Graphics Queue, click **Download Package JSON**.

The package includes:
- `source_mode: "live"` (if Supabase-connected) or `"demo"`
- `generated_at` timestamp
- `source_labels` array
- `nws_proxy_notice`
- All operational, forecast, METAR, and runway fields

Verify `source_mode` is `"live"` before using in broadcast prep.

---

## 21. Export GeoJSON

Click **Export GeoJSON** for a GeoJSON FeatureCollection with all airport features.
For a single airport, use **GeoJSON** in Airport Detail or Graphics Queue.

---

## 22. Export Placefile

Click **Placefile** to export a GRLevelX-compatible placefile (Title / Refresh / Font / Text / End).
Stale or aging airports get a tag appended to the label.

---

## 23. Deciding When Something Is Not Safe for Broadcast

Do not use an item for broadcast if any of the following are true:

- Source Health shows `stale` or `no_runs` for **FAA NAS Status** or **AviationWeather.gov**
- The airport freshness badge is `stale` or `unknown`
- The exported Package JSON shows `source_mode: "demo"`
- The data is more than 3 hours old for operational impact
- The ATCSCC panel shows an active program that you cannot verify from source

When uncertain, say "source data unavailable" or "not currently stored."
Use `aging` data only with explicit acknowledgment that it may not reflect the current NAS state.

---

## Refresh Cadence (Recommended)

| Source | Recommended interval |
|---|---|
| FAA NAS Status | 1–5 min during active prep, 5–15 min otherwise |
| METAR | 5–10 min |
| TAF | 30–60 min |
| Aviation Hazards | 15–30 min |
| NWS Forecasts | 30–120 min |
| ATCSCC Ops Plan | 5–15 min around planning cycles; 30 min otherwise |
| RouteCast snapshots | After each `pull_all.py` run |
