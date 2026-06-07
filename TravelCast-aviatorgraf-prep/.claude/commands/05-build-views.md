# 05-build-views — TravelCast Claude Code Command

Build SQL views for high-level and detailed examination.

Create or update sql/live_views.sql.

Required high-level views:

- v_airport_status_dashboard
- v_airport_broadcast_cards
- v_graphics_queue_candidates
- v_source_health_dashboard

Required detailed views:

- v_airport_detail_current
- v_airport_metar_latest
- v_airport_taf_latest
- v_airport_taf_timeline
- v_airport_operational_events_latest
- v_airport_runway_context
- v_airport_alerts_active

Make views read from canonical ontology tables.
