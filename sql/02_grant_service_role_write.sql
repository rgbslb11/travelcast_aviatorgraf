-- ============================================================
-- TravelCast AviatorGraf Prep
-- 02_grant_service_role_write.sql
-- ============================================================
-- PURPOSE
--   Grant INSERT and UPDATE on writable tables to the service_role.
--   Run this ONCE in Supabase SQL Editor if pull scripts or loaders
--   get "permission denied for table" errors.
--
--   Background: service_role bypasses RLS but still needs table-level
--   grants if the tables were created with default privileges that do
--   not include INSERT/UPDATE. This is a Supabase project-level setting
--   that varies depending on when the project was created.
--
-- RUN ORDER
--   Run after 00_supabase_bootstrap.sql (and 01_seed_focus_airports.sql).
--   Safe to rerun — GRANT is idempotent.
--
-- NO SECRETS IN THIS FILE
-- ============================================================

GRANT INSERT, UPDATE, DELETE ON public.airports                 TO service_role;
GRANT INSERT, UPDATE, DELETE ON public.airport_status_snapshots TO service_role;
GRANT INSERT, UPDATE, DELETE ON public.feed_runs                TO service_role;
GRANT INSERT, UPDATE, DELETE ON public.source_systems           TO service_role;
GRANT INSERT, UPDATE, DELETE ON public.weather_icon_assets      TO service_role;
GRANT USAGE, SELECT ON ALL SEQUENCES IN SCHEMA public           TO service_role;

-- Verify: list table privileges for service_role
SELECT
  table_name,
  privilege_type
FROM information_schema.role_table_grants
WHERE grantee = 'service_role'
  AND table_schema = 'public'
  AND table_name IN ('airports','airport_status_snapshots','feed_runs','source_systems','weather_icon_assets')
ORDER BY table_name, privilege_type;
