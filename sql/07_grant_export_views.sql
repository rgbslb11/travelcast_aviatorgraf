-- 07_grant_export_views.sql
-- Grant SELECT on broadcast export views to service_role and anon.
-- Required for export_broadcast_batch.py (server-side script uses service_role key)
-- and for any future server-side reads from dashboard views.
-- Run this in the Supabase SQL Editor after 06_operational_intelligence.sql.

GRANT SELECT ON v_airport_status_dashboard TO service_role;
GRANT SELECT ON v_airport_status_dashboard TO anon;
GRANT SELECT ON v_source_health_dashboard   TO service_role;
GRANT SELECT ON v_routecast_dashboard        TO service_role;
GRANT SELECT ON v_aviation_hazards_active    TO service_role;
GRANT SELECT ON v_atcscc_ops_plan_current    TO service_role;
