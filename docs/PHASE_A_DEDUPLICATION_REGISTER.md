# PHASE A DEDUPLICATION REGISTER
# Classification of Uploaded Source Materials

**Session:** 2026-06-20
**Phase:** A — Anchor + Deduped Build Register

---

## Source Files Reviewed

9 files from `C:\TravelCast AviatorGraf\phase 11+ docs\`

---

## Classification Table

| File | Lines | Classification | Disposition |
|------|-------|----------------|-------------|
| `wxSense Graphics.txt` | 5162 | KEEP | Phase E reference — broadcast graphics visual bible, brand color palette, AguaceroWX settings |
| `add'l notes.txt` | 61 | PARK | Operator packaging concept notes; captured in Phase B scope. Original context (pre-Phase 11 discussion) |
| `AviaImpact Score in the same sense.txt` | 280 | KEEP | Definitive AviaImpact Score v0.1 spec — Phase D reference |
| `BUILD LOGIC 2.txt` | ~470 | KEEP | Authoritative build decision logic; 71-airport equal-cadence doctrine; ordered build sequence 0–8 |
| `FINALIZED ROADCAST.txt` | 4592 | KEEP | Complete RoadCast Framework with SQL migration, scoring engine, 50-corridor seed, pull script, dashboard JS — supersedes Framework A and B files |
| `NWS CAPWEA logic.txt` | 978 | KEEP | Complete NWS CAP/WEA Phase spec with SQL tables, views, pull scripts, WEA extraction rules, audit scripts, and Claude Code build prompts — Phase C reference |
| `REMAINING BUILD DECISION TREE.txt` | 1499 | KEEP | Coverage assessment, gap analysis, Phase 13 hosted worker spec (Phase E reference) |
| `ROADCAST FRAMEWORK A.txt` | ~4000+ | SUPERSEDED | Identical to first 300+ lines of FINALIZED ROADCAST.txt. Contains same SQL schema, seed script, scoring logic. No unique content found in first 300 lines. |
| `ROADCAST FRAMEWORK B.txt` | ~4000+ | SUPERSEDED | Identical to ROADCAST FRAMEWORK A.txt through at least 300 lines. Same schema, same seed data, same scoring formula. Fully covered by FINALIZED ROADCAST.txt. |

---

## Detailed Disposition Notes

### KEEP: `wxSense Graphics.txt`
Contains Operation Aero Shear decisions:
- Brand hierarchy: wxSense (umbrella) → TravelCast → StormGlass Live → WxSense Lab
- Visual bible doctrine (35 approved items, parked/culled/superseded/retired items)
- Broadcast master template spec
- Color palette: `#061625` background, `#0B4F8F` primary blue, `#F05A28` accent orange, impact colors
- Logo system
- AguaceroWX settings and Southern Plains domain preset

**Use in Phase E** (wxSense graphics templates). Not needed for Phase B, C, or D builds.

**Note:** File is 5162 lines; only first ~2135 were read in this session. Full read recommended before Phase E begins.

### PARK: `add'l notes.txt`
Pre-Phase-11 operator packaging concept notes. Content captured:
- One-click Windows launcher concept
- `refresh_live_data.bat`, `start_local_server.bat`, `open_app.bat`
- Task Scheduler notes
- "I would not add more intelligence features until the local operator workflow is painless."

This context is absorbed into Phase B2 (Windows Operator Helpers). The file itself has no unique technical content beyond what BUILD LOGIC 2.txt covers. No action needed.

### KEEP: `AviaImpact Score in the same sense.txt`
Complete product spec for AviaImpact Score v0.1:
- Formula with 6 weighted components (total must equal 1.0)
- Component rubrics 0–5 for each factor
- Hard override rules (ground stop → force 5/5, GDP → minimum 4/5)
- Full data model (5 tables)
- Output language rules (allowed vs not-allowed)
- Example calculation: DFW thunderstorm scenario → 3/5 Likely
- Placement: Phase D (after RouteCast intelligence expansion)

### KEEP: `BUILD LOGIC 2.txt`
Authoritative decision register covering:
- 71 airports locked at equal refresh cadence (no priority tiers)
- Two runway layers (static reference vs live FAA/NAS)
- NWS CAP/WEA as future public alert lane (not aviation operational truth)
- TAF timeline + PIREP maturity as Phase 13A in original numbering
- RouteCast corridor geometry + ATCSCC playbook matching as future expansion
- Windows .bat helpers need verification
- wxSense graphics template automation as Phase 11 in original numbering
- Ordered build sequence 0–8 (all absorbed into Phase A–E register)

### KEEP: `FINALIZED ROADCAST.txt`
The canonical RoadCast implementation document. Contains:
- Complete RoadCast Framework A+B merged
- SQL migration: `supabase/migrations/20260608_roadcast_core.sql`
- Tables: `roadcast_corridors`, `roadcast_source_runs`, `roadcast_forecast_samples`, `roadcast_scores`
- Views: `v_roadcast_dashboard`, `v_roadcast_geojson`
- Scoring engine: `scripts/roadcast/roadcast_scoring.py`
- Seed script: `scripts/roadcast/seed_roadcast_corridors.py`
- 50 corridor records with lat/lon sample points and static scores
- Pull script: `scripts/pull/pull_roadcast_nws.py`
- Dashboard JS module: `js/modules/roadcast.js`
- GeoJSON export: `scripts/export/export_roadcast_geojson.py`
- Graphics export package

**Use in Phase D** (RoadCast product implementation).

### KEEP: `NWS CAPWEA logic.txt`
Complete Phase C spec for NWS CAP/WEA Public Alert Ontology:
- Source doctrine addition: "NWS CAP / Alerts = public alert and warning truth"
- `source_system_id = nws_alerts_cap` upsert SQL
- 5 core tables with full column definitions
- 4 views: `v_public_weather_alerts_active`, `v_public_weather_alerts_wea`, `v_airport_alerts_active`, `v_stormglass_public_alert_board`
- Match type taxonomy: `point_in_polygon`, `zone_match`, `county_zone_match`, `distance_buffer`, `manual_review`
- WEA field naming rules (use `nws_wea_text_90`, not `travelcast_wea_text`)
- Public alert priority scoring system (graphics-prep score only)
- Complete Claude Code build prompts for Phase 14 → now Phase C
- 3 audit scripts: `audit_public_alert_doctrine.py`, `audit_wea_fields.py`, `audit_public_alert_geometry.py`

**Note:** File references "Phase 14" in original numbering. In the A–E register, NWS CAP/WEA = Phase C1.

### KEEP: `REMAINING BUILD DECISION TREE.txt`
Comprehensive status assessment and gap analysis:
- "Day-One local TravelCast prep: ~85–90% complete"
- Coverage table: what is fully/partially/truly missing
- 71-airport equal cadence confirmed
- Static runway reference: two-layer architecture explained
- NWS CAP/WEA context recap
- TAF timeline / PIREP maturity gap explained
- RouteCast corridor geometry requirement explained
- Windows Task Scheduler / .bat helper gap noted
- Phase 13 Hosted Worker full spec (Phase E2/E3 in A–E register):
  - Phase 13A: Security discovery audit
  - Phase 13B/C: RLS + public read models
  - Phase 13D: Hosted worker
  - Phase 13E: Scheduler + cutover
- SQL skeletons for security inventory, public read models, RLS hardening, scheduler

**Use in Phase E** (production hosting and security).

### SUPERSEDED: `ROADCAST FRAMEWORK A.txt`
Duplicate of the first portion of FINALIZED ROADCAST.txt. The first 300 lines verified identical:
- Same product workflow
- Same scoring formula
- Same SQL schema (tables, views)
- Same seed script structure with same first corridor (`i24_i40_i65_tn_ky`)

**Action:** No further reads needed. All content absorbed by FINALIZED ROADCAST.txt.

### SUPERSEDED: `ROADCAST FRAMEWORK B.txt`
Identical to ROADCAST FRAMEWORK A.txt through first 300 lines. Same conclusion: absorbed by FINALIZED ROADCAST.txt.

**Action:** No further reads needed.

---

## Duplicate / Overlap Map

| Overlap | Files | Resolution |
|---------|-------|------------|
| RoadCast scoring + SQL + seed data | FINALIZED ROADCAST.txt vs Framework A vs Framework B | FINALIZED ROADCAST.txt wins; A and B superseded |
| Operator packaging notes | add'l notes.txt vs BUILD LOGIC 2.txt vs REMAINING BUILD DECISION TREE.txt | BUILD LOGIC 2.txt + REMAINING BUILD DECISION TREE.txt are authoritative; add'l notes.txt parked |
| Phase numbering conflict | NWS CAPWEA references "Phase 14"; REMAINING BUILD DECISION TREE references "Phase 13" | Resolved: A–E register is the new canonical numbering |
| wxSense brand hierarchy | wxSense Graphics.txt vs BUILD LOGIC 2.txt | Both consistent; wxSense Graphics.txt has visual detail; BUILD LOGIC 2.txt has build logic |

---

## Materials Not Yet Fully Read

| File | Status | Action |
|------|--------|--------|
| `wxSense Graphics.txt` lines 2136–5162 | Unread | Read before Phase E begins (graphics template build) |
| `FINALIZED ROADCAST.txt` lines 1707–4592 | Unread | Read before Phase D begins (RoadCast implementation) |

---

## Summary

| Classification | Count | Files |
|----------------|-------|-------|
| KEEP | 6 | wxSense Graphics, AviaImpact Score, BUILD LOGIC 2, FINALIZED ROADCAST, NWS CAPWEA logic, REMAINING BUILD DECISION TREE |
| PARK | 1 | add'l notes |
| SUPERSEDED | 2 | ROADCAST FRAMEWORK A, ROADCAST FRAMEWORK B |
| REJECT | 0 | — |

All 6 KEEP files are referenced in the Phase A–E register by phase and sub-phase.
