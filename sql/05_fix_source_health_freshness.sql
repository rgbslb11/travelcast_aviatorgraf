-- ============================================================
-- 05_fix_source_health_freshness.sql
-- ============================================================
-- PURPOSE
--   Fix v_source_health_dashboard freshness_status to use
--   last_success_at (successful runs only) and add proper
--   four-tier freshness classification:
--
--     fresh   — last successful run < 30 minutes ago
--     aging   — last successful run 30 min – 3 hours ago
--     stale   — last successful run > 3 hours ago
--     no_runs — no successful run on record
--
--   Before this fix the view used max(retrieved_at_utc) which
--   included failed runs and only had three states (fresh /
--   no_runs / unknown), causing official sources with recent
--   successful runs to display 'unknown' after 30 minutes.
--
-- RUN
--   Paste into Supabase SQL Editor and click Run.
--   Idempotent — safe to rerun.
-- ============================================================

create or replace view v_source_health_dashboard as
select
  s.source_system_id,
  s.display_name,
  s.trust_tier,
  s.official_source,
  s.mission_critical_allowed,
  s.category,
  s.notes,
  max(f.retrieved_at_utc)                                                     as latest_feed_run,
  max(f.retrieved_at_utc) filter (where f.live_fetch_success = true)          as last_success_at,
  max(f.error)            filter (where f.live_fetch_success = false)          as last_error,
  count(*)                filter (where f.retrieved_at_utc > now() - interval '24 hours')
                                                                               as runs_last_24h,
  case
    when max(f.retrieved_at_utc) filter (where f.live_fetch_success = true)
           > now() - interval '30 minutes'  then 'fresh'
    when max(f.retrieved_at_utc) filter (where f.live_fetch_success = true)
           > now() - interval '3 hours'     then 'aging'
    when max(f.retrieved_at_utc) filter (where f.live_fetch_success = true)
           is not null                      then 'stale'
    else 'no_runs'
  end as freshness_status
from source_systems s
left join feed_runs f on f.source_system_id = s.source_system_id
group by
  s.source_system_id, s.display_name, s.trust_tier, s.official_source,
  s.mission_critical_allowed, s.category, s.notes;

grant select on v_source_health_dashboard to anon, authenticated;
