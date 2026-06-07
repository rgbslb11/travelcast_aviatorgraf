# ACCEPTANCE_CRITERIA.md

The build is accepted only if all required items pass.

## Demo mode

- [ ] App loads with `python -m http.server 8080`.
- [ ] App works without Supabase credentials.
- [ ] Airport Status Board renders 10 sample airports.
- [ ] DEN sample shows GDP, thunderstorms, 63 min average delay, 386 max delay, 16L/16R/17R arrival runways, icon ID 04, red impact.
- [ ] Airport Detail renders for DEN.

## Exports

- [ ] Dashboard JSON export works.
- [ ] Airport broadcast package JSON export works.
- [ ] GeoJSON export works and is valid FeatureCollection.
- [ ] Placefile export works and includes Title, Refresh, Font, Text, End.

## Graphics queue

- [ ] Add to Graphics Queue works.
- [ ] Queue persists in localStorage.
- [ ] Queue item can be removed.
- [ ] Queue item can be marked Ready.
- [ ] Stale/unknown data shows warning.

## Supabase readiness

- [ ] `js/config.js` supports Supabase URL and anon key.
- [ ] App falls back to demo data if Supabase is not configured.
- [ ] No service-role key appears in frontend.
- [ ] Missing Supabase views do not crash the app.

## Doctrine

- [ ] NWS forecast impact is labeled as forecast proxy.
- [ ] FAA/NAS operational impact is labeled separately.
- [ ] Commercial/enrichment sources are not labeled official.
- [ ] Icons use canonical IDs.

## Security

- [ ] No private API keys.
- [ ] No service-role key.
- [ ] No real secrets.
- [ ] `.env` is gitignored.

## Audit

- [ ] `audit/day_one_readiness_report.md` exists.
- [ ] Readiness result is Yes, Partial, or No.
- [ ] Any blockers are listed.
