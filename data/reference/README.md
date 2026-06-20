# data/reference/

Static reference data for TravelCast AviatorGraf Prep.

These files are **not generated outputs**. They are source-backed or template CSV/JSON files used by loader scripts to populate Supabase reference tables.

---

## Files

| File | Purpose | Status |
|------|---------|--------|
| `travelcast_airports_master.csv` | Full airport master list with all fields for `load_airports_to_supabase.py` | Loaded |
| `travelcast_focus_airports.csv` | 71-airport operational focus set (region, IATA, ICAO, lat/lon) | Loaded |
| `travelcast_airport_runways.template.csv` | **Template only** — headers for the static runway reference table. Populate with FAA NASR / OurAirports data before running `load_airport_runways.py`. | Empty — not yet loaded |

---

## Rules

- Do not put live FAA/NAS operational data here. This folder is for static reference only.
- Do not put generated export packages here. Those go to `data/exports/`.
- Do not put raw API payloads here. Those go to `data/raw/`.
- Do not invent runway data, airport data, or coordinates.
- Populate `travelcast_airport_runways.template.csv` only with data from official sources (FAA NASR, FAA AIS, OurAirports).

---

## Runway Reference Population

See `docs/RUNWAY_REFERENCE.md` for the data model and source hierarchy.
See `docs/RUNWAY_SOURCE_DOCTRINE.md` for which sources are authoritative vs. candidate cross-check only.

To populate runway data:
1. Download official runway data from FAA NASR / FAA AIS or OurAirports
2. Fill `travelcast_airport_runways.template.csv` (copy to `travelcast_airport_runways.csv` with data)
3. Run: `python scripts/load/load_airport_runways.py --dry-run`
4. If dry run passes, run: `python scripts/load/load_airport_runways.py`
5. Run: `python scripts/audit/audit_runway_reference.py`
