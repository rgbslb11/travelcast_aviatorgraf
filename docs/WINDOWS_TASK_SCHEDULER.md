# WINDOWS TASK SCHEDULER
# TravelCast AviatorGraf Prep — Automated Refresh Setup

**Phase B1 — Operator Packaging**

---

## Purpose

Windows Task Scheduler runs `refresh_data_live.bat` on a timer so the 71-airport Supabase board stays current without manual intervention.

---

## Security Rules

- The `.bat` file contains no secrets
- Python scripts load credentials from `.env` automatically
- `.env` must remain at: `C:\TravelCast AviatorGraf\travelcast_aviatorgraf\.env`
- Do not store credentials in Task Scheduler fields

---

## Recommended Cadence

| Situation | Refresh Interval |
|-----------|-----------------|
| Normal monitoring | Every 10 minutes |
| Active broadcast prep / live window | Every 5 minutes |
| Overnight / background | Every 15–30 minutes (optional) |

Start with 10 minutes. Move to 5 minutes only during active prep after pull behavior is proven stable.

---

## Setup Instructions

### Step 1 — Open Task Scheduler
1. Press `Win + R`, type `taskschd.msc`, press Enter
2. Or: Start Menu → search "Task Scheduler"

### Step 2 — Create Basic Task
1. In the right panel, click **Create Basic Task**
2. Name: `TravelCast Data Refresh`
3. Description: `Runs TravelCast AviatorGraf pull_all.py every 10 minutes`
4. Click Next

### Step 3 — Trigger
1. Select **Daily**
2. Click Next
3. Set start time (e.g., 4:00 AM on today's date)
4. Recur every **1** day
5. Click Next

### Step 4 — Action
1. Select **Start a program**
2. Click Next
3. Program/script:
   ```
   C:\TravelCast AviatorGraf\travelcast_aviatorgraf\scripts\windows\refresh_data_live.bat
   ```
4. Start in (optional):
   ```
   C:\TravelCast AviatorGraf\travelcast_aviatorgraf
   ```
5. Click Next → Finish

### Step 5 — Edit for Repeat Interval
1. In Task Scheduler Library, right-click `TravelCast Data Refresh`
2. Select **Properties**
3. Go to **Triggers** tab → select the trigger → click **Edit**
4. Check **Repeat task every**: `10 minutes`
5. For a duration: `Indefinitely` (or set to 24 hours for safety)
6. Click OK → OK

### Step 6 — Settings tab (recommended)
In the Properties dialog → **Settings** tab:
- Check: "If the task is already running, do not start a new instance"
- Check: "Run task as soon as possible after a scheduled start is missed"
- Click OK

---

## Verify the Schedule

1. Right-click the task → **Run** to trigger it immediately
2. Check Task Scheduler → History tab for success/failure
3. Open the app in browser and verify Source Health shows fresh timestamps
4. Check `data\exports\` if export is included in the schedule

---

## Optional: Add Export to the Schedule

To run a broadcast export after every pull, create a second task that calls:

```
C:\TravelCast AviatorGraf\travelcast_aviatorgraf\scripts\windows\export_broadcast_live.bat
```

Set it to run 2–3 minutes after the pull task, or chain it by running `pull_all.py --export` directly.

Alternatively, modify `refresh_data_live.bat` to include `--export`:

```batch
python scripts\pull\pull_all.py --export
```

Export failure is non-fatal — pull results are not affected.

---

## Stopping / Disabling the Schedule

To pause automated pulls:
1. Task Scheduler Library → right-click the task → **Disable**

To stop an in-progress run:
1. Task Scheduler Library → right-click the task → **End**

Local fallback: `refresh_data_live.bat` can always be run manually while the schedule is disabled.

---

## Rollback Rule

If any mission-critical source shows `stale` or `no_runs` after a scheduled pull:

1. Check Task Scheduler History for error codes
2. Run `refresh_data_dry_run.bat` to verify Python/network access
3. Run `refresh_data_live.bat` manually to confirm live behavior
4. Check Source Health in the browser — do not use stale official-source data on-air
5. If the issue persists, disable the schedule and investigate

Source Health indicators:
- `fresh` — data is current
- `aging` — data is older than expected; monitor
- `stale` — data has not been updated; investigate before on-air use
- `no_runs` — no pull has completed; do not air claims from this source

---

## Common Issues

| Issue | Check |
|-------|-------|
| Task fails silently | Verify `.env` is present at project root; check that Python is in system PATH |
| "Access denied" | Run the task under your Windows user account, not SYSTEM |
| Pull succeeds but data not visible | Check Supabase connection; verify `SUPABASE_URL` and `SUPABASE_SERVICE_ROLE_KEY` in `.env` |
| Exports not generated | Confirm `data\exports\` exists and is writable |
| Task runs but Source Health shows stale | Check pull script logs; a source API may be temporarily unavailable |
