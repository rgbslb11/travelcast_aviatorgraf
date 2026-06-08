# Command Reference — TravelCast AviatorGraf Prep

Quick reference for all operational commands. Run from the project root directory.

---

## Server

**Start local server:**
```
python -m http.server 8080
```

**Open app:**
```
http://localhost:8080
```

---

## Pull Scripts

**Dry-run all (no Supabase writes):**
```
python scripts\pull\pull_all.py --dry-run
```

**Live pull all (writes to Supabase):**
```
python scripts\pull\pull_all.py
```

**Skip RouteCast enrichment:**
```
python scripts\pull\pull_all.py --skip-routecast
```

**Limit to first N airports (testing):**
```
python scripts\pull\pull_all.py --dry-run --limit 5
```

---

## Individual Pull Scripts

**FAA NAS Status:**
```
python scripts\pull\pull_faa_nas_status.py --dry-run
python scripts\pull\pull_faa_nas_status.py
```

**AviationWeather METAR/TAF:**
```
python scripts\pull\pull_aviationweather_metar_taf.py --dry-run
python scripts\pull\pull_aviationweather_metar_taf.py
```

**NWS Forecasts:**
```
python scripts\pull\pull_nws_forecasts.py --dry-run
python scripts\pull\pull_nws_forecasts.py
```

**Aviation Hazards (SIGMET / AIRMET / CWA):**
```
python scripts\pull\pull_aviation_hazards.py --dry-run
python scripts\pull\pull_aviation_hazards.py
```

**ATCSCC Operations Plan (auto-discovery):**
```
python scripts\pull\pull_atcscc_ops_plan.py --dry-run
python scripts\pull\pull_atcscc_ops_plan.py
```

**ATCSCC Operations Plan (manual URL):**
```
python scripts\pull\pull_atcscc_ops_plan.py --url "https://www.fly.faa.gov/adv/adv_otherdis.jsp?..."
```

**Rebuild Airport Status Snapshots:**
```
python scripts\pull\rebuild_airport_status_snapshots.py --dry-run
python scripts\pull\rebuild_airport_status_snapshots.py
```

**RouteCast Snapshots (from local caches — no new API calls):**
```
python scripts\pull\rebuild_routecast_snapshots.py --dry-run
python scripts\pull\rebuild_routecast_snapshots.py
```

---

## Load Scripts

**Load focus airports to Supabase (dry-run):**
```
python scripts\load\load_focus_airports_to_supabase.py --dry-run
```

**Load focus airports to Supabase (live):**
```
python scripts\load\load_focus_airports_to_supabase.py
```

---

## Audit Scripts

**No-secrets audit (checks for committed secrets):**
```
python scripts\audit\audit_no_secrets.py
```

**Source doctrine audit (checks for mislabeled sources):**
```
python scripts\audit\audit_source_doctrine.py
```

**File tree audit (checks required files exist):**
```
python scripts\audit\audit_file_tree.py
```

---

## Syntax Checks

**Check all pull scripts:**
```
python -m py_compile scripts\pull\pull_faa_nas_status.py scripts\pull\pull_aviationweather_metar_taf.py scripts\pull\pull_nws_forecasts.py scripts\pull\pull_aviation_hazards.py scripts\pull\pull_atcscc_ops_plan.py scripts\pull\rebuild_airport_status_snapshots.py scripts\pull\rebuild_routecast_snapshots.py scripts\pull\pull_all.py
```

**Check load scripts:**
```
python -m py_compile scripts\load\load_focus_airports_to_supabase.py
```

**Check audit scripts:**
```
python -m py_compile scripts\audit\audit_no_secrets.py scripts\audit\audit_source_doctrine.py scripts\audit\audit_file_tree.py
```

---

## Git

**Check working tree status:**
```
git status
```

Note: `js/config.js` will show as modified — this is expected and must NOT be committed.

**Push committed changes:**
```
git push
```

**Unstage `js/config.js` if accidentally staged:**
```
git restore --staged js/config.js
```

---

## Supabase SQL Migrations (paste in Supabase SQL Editor)

Apply in order on a fresh project:

| File | Purpose |
|---|---|
| `sql/00_supabase_bootstrap.sql` | Core tables: airports, snapshots, feed_runs, source_systems |
| `sql/01_seed_focus_airports.sql` | 71 focus airports |
| `sql/02_grant_service_role_write.sql` | GRANT write permissions to service_role |
| `sql/03_add_detail_views.sql` | Airport detail views |
| `sql/04_placeholder_views.sql` | Placeholder views (Aviation Hazards, RouteCast) |
| `sql/05_fix_source_health_freshness.sql` | Source Health 4-tier freshness (replaces 3-tier) |
| `sql/06_operational_intelligence.sql` | ATCSCC, Aviation Hazards, RouteCast tables and views |

---

## Environment File (`.env`) — Required for pull scripts

Location: `scripts/pull/.env` (gitignored — never committed)

Required keys:
```
SUPABASE_URL=https://yourproject.supabase.co
SUPABASE_SERVICE_ROLE_KEY=your_service_role_key_here
NWS_USER_AGENT=TravelCast/1.0 (your@email.com)
```

---

## Local Config (`js/config.js`) — Required for browser

Location: `js/config.js` (gitignored working copy — never commit with real values)

Required keys:
```js
const SUPABASE_CONFIG = {
  supabaseUrl: "https://yourproject.supabase.co",
  supabaseAnonKey: "your-anon-key-here",
  demoMode: false,
};
```
