# Troubleshooting — TravelCast AviatorGraf Prep

---

## App still says Demo Mode

**Symptom:** Banner reads "Supabase Not Configured — demo mode" with a gray border.

**Cause:** `js/config.js` has placeholder values or `demoMode: true`.

**Fix:**
1. Open `js/config.js` in a text editor (not VS Code git-tracked — this file is intentionally local-only).
2. Replace `REPLACE_WITH_SUPABASE_URL` with your Supabase project URL.
3. Replace `REPLACE_WITH_SUPABASE_ANON_KEY` with your Supabase anon/public key.
4. Set `demoMode: false`.
5. Hard-refresh the browser (`Ctrl+Shift+R`).

Do NOT commit `js/config.js` with real credentials.

---

## Supabase Connected banner missing (shows "Query Failed" instead)

**Symptom:** Banner reads "Supabase Query Failed — using demo fallback" with an amber border.

**Cause:** Supabase is configured but the view query failed. Common causes:
- Anon key is wrong or expired
- `v_airport_status_dashboard` view does not exist (SQL migrations not applied)
- Network unreachable

**Fix:**
1. Verify anon key in `js/config.js` matches the project's Settings > API > `anon` key.
2. Verify Supabase SQL migrations have been applied (sql/00 through sql/06).
3. Open Supabase SQL Editor and run: `select count(*) from airports;`
   If this errors, check RLS or permissions.
4. Check browser console (F12 > Console) for the specific Supabase error message.

---

## 0 airports loaded

**Symptom:** Airport Status Board shows 0 rows.

**Cause:** Airport records not seeded, or `airports.active = false` for all records.

**Fix:**
1. Apply `sql/01_seed_focus_airports.sql` in Supabase SQL Editor.
2. Confirm: `select count(*) from airports where active = true;` — should return 71.

---

## Fewer than 71 airports loaded

**Symptom:** Airport Status Board shows, e.g., 10 of 71 airports.

**Cause:** Only the 10 demo-seed airports are in the database.

**Fix:**
1. Run `python scripts\load\load_focus_airports_to_supabase.py --dry-run` to verify 71 airports detected.
2. Run `python scripts\load\load_focus_airports_to_supabase.py` to upsert all 71.
3. Hard-refresh browser.

---

## Stale Source Health

**Symptom:** Source Health shows `stale` badge for an official source.

**Cause:** The last successful pull for that source is more than 3 hours old.

**Fix:**
1. Run `python scripts\pull\pull_all.py --dry-run` — check that source's script passes.
2. Run `python scripts\pull\pull_all.py` to do a live pull.
3. Hard-refresh browser and recheck Source Health.

---

## `no_runs` on an official source

**Symptom:** Source Health shows `no_runs` (gray badge) for FAA NAS Status, AviationWeather, or NWS.

**Cause:** That source's pull script has never written a `feed_runs` row to Supabase, or the `feed_runs` table was reset.

**Fix:**
1. Run the relevant pull script directly (see COMMAND_REFERENCE.md).
2. If it errors, check for missing `.env` or wrong `SUPABASE_SERVICE_ROLE_KEY`.
3. If `feed_runs` table is missing, apply `sql/00_supabase_bootstrap.sql`.

---

## Service-role key missing

**Symptom:** Pull script exits with `SUPABASE_SERVICE_ROLE_KEY not set` or similar.

**Fix:**
1. Create or edit `scripts/pull/.env` (not the project root — the scripts/pull directory).
2. Add: `SUPABASE_SERVICE_ROLE_KEY=your_service_role_key_here`
3. Also add: `SUPABASE_URL=https://yourproject.supabase.co`
4. Also add: `NWS_USER_AGENT=TravelCast/1.0 (your@email.com)`
5. Do NOT commit `.env`.

---

## Supabase permission denied

**Symptom:** Pull script errors with `permission denied for table airport_status_snapshots` or similar.

**Fix:**
1. Apply `sql/02_grant_service_role_write.sql` in Supabase SQL Editor.
2. Verify your Supabase project's service_role key is correct in `.env`.

---

## Anon key wrong

**Symptom:** Browser console shows `401 Unauthorized` or `invalid JWT`.

**Fix:**
1. Copy the `anon` key from Supabase Settings > API.
2. Paste into `js/config.js` as `supabaseAnonKey`.
3. Hard-refresh.

---

## `.env` missing

**Symptom:** All pull scripts exit immediately with "SUPABASE_URL not set" or similar.

**Fix:**
Create `scripts/pull/.env`:
```
SUPABASE_URL=https://yourproject.supabase.co
SUPABASE_SERVICE_ROLE_KEY=your_service_role_key_here
NWS_USER_AGENT=TravelCast/1.0 (your@email.com)
```
Do NOT commit this file.

---

## `js/config.js` local config missing

**Symptom:** App loads in Demo Mode even though Supabase is running.

**Fix:**
See the `js/config.js.example` or `README.md` for the expected format. Copy and configure locally:
```js
const SUPABASE_CONFIG = {
  supabaseUrl: "https://yourproject.supabase.co",
  supabaseAnonKey: "your-anon-key-here",
  demoMode: false,
};
```
Do NOT commit the file with real values.

---

## NWS API failure

**Symptom:** `pull_nws_forecasts.py` logs fetch errors for some or all airports.

**Cause:** NWS `api.weather.gov` is occasionally slow or returns 500/503. Some airports may time out.

**Fix:**
1. Wait 5–10 minutes and re-run the pull.
2. NWS failures are non-fatal — the script continues to the next airport and logs `forecast_error`.
3. Check if your `NWS_USER_AGENT` in `.env` is set to a real contact email — NWS requires this.
4. If failures persist, cached forecast data from the last successful pull remains in `data/raw/`.

---

## FAA NAS endpoint unavailable

**Symptom:** `pull_faa_nas_status.py` errors with connection refused or NXDOMAIN.

**Cause:** `nasstatus.faa.gov/api/airport-events` is unavailable.

**Fix:**
1. Wait and retry — the endpoint is generally reliable but has occasional outages.
2. The last cached raw data at `data/raw/faa_nas_status.json` can be used by `rebuild_airport_status_snapshots.py` to rebuild snapshots without a new pull.
3. If the outage is extended, use `aging` snapshot data with explicit acknowledgment of data age.
4. Do NOT invent operational events. Empty state is better than invented delays.

---

## AviationWeather endpoint empty

**Symptom:** `pull_aviation_hazards.py` logs `sigmet_count: 0`, `airmet_count: 0`, `cwa_count: 0`.

**Cause:** No active SIGMETs, AIRMETs, or CWAs at time of pull (legitimate empty state), or endpoint returned an empty array.

**Fix:**
1. Verify against `https://aviationweather.gov/` in a browser — if no SIGMETs are active, 0 is correct.
2. If products are visible on the AviationWeather site but the script returns 0, check endpoint connectivity and run with `--dry-run`.

---

## Aviation Hazards tab empty

**Symptom:** Aviation Hazards tab shows "No live aviation hazard records available."

**Cause (Supabase mode):** `v_aviation_hazards_latest` is returning no active rows. Either:
- No active hazards were found in the last pull (legitimate)
- Pull script hasn't been run yet
- `sql/06_operational_intelligence.sql` has not been applied

**Fix:**
1. Apply `sql/06_operational_intelligence.sql` if not done.
2. Run `python scripts\pull\pull_aviation_hazards.py` then hard-refresh.
3. If hazards are legitimately absent, the empty state is correct — do not invent hazards.

---

## ATCSCC Operations Plan not auto-discovered

**Symptom:** `pull_atcscc_ops_plan.py` logs `no_plan_found` or `advisory_urls_found: 0`.

**Cause:** No system-wide ATCSCC Operations Plan advisory was linked in today's FAA NAS status response. This is normal — ops plans are only issued during major NAS management events (widespread GDPs, severe weather CDPs, etc.).

**Fix:**
- This is not an error. The panel shows an honest empty state.
- If you know an advisory URL is active, use the `--url` flag (see below).

---

## Manual ATCSCC Operations Plan URL ingestion

When FAA posts an Operations Plan advisory that is not auto-discovered:

```
python scripts\pull\pull_atcscc_ops_plan.py --url "https://www.fly.faa.gov/adv/adv_otherdis.jsp?..."
```

The script inserts the URL at the front of the processing list, bypassing auto-discovery. The advisory is fetched, parsed, and stored in Supabase.

---

## RouteCast no routes

**Symptom:** RouteCast tab shows "No live RouteCast routes configured yet."

**Cause:** `routecast_routes` table has no active rows, or `sql/06_operational_intelligence.sql` has not been applied.

**Fix:**
1. Apply `sql/06_operational_intelligence.sql` — it seeds 6 starter routes (DFW-JFK, DFW-ORD, DFW-ATL, SFO-ORD, JFK-MIA, DEN-DTW).
2. Hard-refresh browser.

---

## RouteCast source health no_runs

**Symptom:** Source Health shows `no_runs` for RouteCast.

**Fix:**
Run `python scripts\pull\rebuild_routecast_snapshots.py` — this writes a `feed_runs` row under `source_system_id: routecast`.

---

## Airport operational filter returning unexpected counts

**Symptom:** "Operational: Red" returns 0 even though red-impact airports exist.

**Cause:** `current_impact_color` field is null for some airports. The filter falls back to inferring from `current_delay_type`.

**Fix:**
1. Run a fresh `pull_all.py` to rebuild snapshots.
2. If the issue persists, verify that `v_airport_status_dashboard` includes `current_impact_color` and `current_delay_type` columns.
3. The `opImpactColor()` JS function handles null `current_impact_color` by inferring from `current_delay_type` — this fallback is by design.

---

## Exports showing `source_mode: "demo"`

**Symptom:** Downloaded Package JSON contains `"source_mode": "demo"`.

**Cause:** The app is in demo mode or Supabase connection failed, so `appState.demoModeActive` is true.

**Fix:**
1. Verify `js/config.js` has `demoMode: false` and real credentials.
2. Verify the Supabase Connected banner is showing (green border).
3. Run a live pull and hard-refresh.
4. Recheck `source_mode` in the next export.

Do not use demo-mode exports in broadcast prep as live data.

---

## Graphics Queue stale item

**Symptom:** A queued item shows a `stale` freshness badge and "Needs Freshness Review" status.

**Fix:**
1. Run a fresh `pull_all.py` to update the source data.
2. Hard-refresh the browser — the queue is localStorage-backed; items retain the freshness state at the time they were queued.
3. Remove the stale item from the queue and re-add it from the Airport Status Board with fresh data.

---

## Browser cache issue

**Symptom:** App behaves unexpectedly or shows stale UI after a code update.

**Fix:**
Hard-refresh: `Ctrl+Shift+R` (Windows/Linux) or `Cmd+Shift+R` (Mac).

For a full cache clear: Chrome DevTools > Application > Storage > Clear site data.

---

## Python script crashes

**Symptom:** Script exits with a Python traceback.

**Fix:**
1. Run `python -m py_compile scripts\pull\pull_all.py` to check for syntax errors.
2. Check the error message — most failures are HTTP errors (logged as JSON events), not crashes.
3. Verify `.env` is present and populated.
4. If the crash is a `KeyError` or `AttributeError`, the upstream API may have changed its response schema.
   Open an issue or run with `--dry-run` to inspect the raw output.

---

## Git shows modified `js/config.js`

**Symptom:** `git status` shows `js/config.js` as modified.

**This is expected and intentional.** `js/config.js` is committed with placeholder values; your local version has real credentials.

Do NOT run `git add js/config.js` or `git commit` with this file staged.

If you accidentally stage it: `git restore --staged js/config.js`
If you accidentally commit it: remove the real credentials immediately, force-push is not available on this branch — contact repo admin.
