# 03-build-supabase-layer — TravelCast Claude Code Command

Build Supabase integration support.

Requirements:

- Frontend uses only public Supabase anon key.
- Supabase config lives in js/config.js.
- If Supabase is unconfigured, demo mode continues working.
- Query v_airport_status_dashboard first.
- Fall back safely if view is missing.
- Do not use service-role key in frontend.
