# AGENTS.md - Data Download Procedure (TennisSensor v3.4 USB Mode)

This repo uses a USB-only workflow in v3.3. Data is stored on the iPhone in
`Documents/tennis_watch.db` and pulled over USB with `pymobiledevice3`.

## Prereqs

- iPhone connected via USB and trusted
- `pymobiledevice3` available (often in `/Users/blueaz/Python/.venv/bin/`)

## Pull the Database

```bash
# Pull the full Documents folder
/Users/blueaz/Python/.venv/bin/pymobiledevice3 apps pull com.ef.TennisSensor Documents/ /tmp/tennis_docs/

# Database path after pull
ls -lh /tmp/tennis_docs/Documents/tennis_watch.db
```

## Merge Into USB (Safe, No Overwrite)

This prevents accidental data loss if the phone DB is empty or missing sessions.

```bash
# Merge phone DB into USB DB with backup + safety checks
/Users/blueaz/Python/Mac/MacOSTennisAgent/scripts/merge_watch_db.sh \\
  /tmp/tennis_docs/Documents/tennis_watch.db \\
  "/Volumes/NO NAME/tennis_watch.db"
```

## Verify Sessions and Samples

```bash
sqlite3 /tmp/tennis_docs/Documents/tennis_watch.db "SELECT COUNT(*) FROM sessions;"

sqlite3 /tmp/tennis_docs/Documents/tennis_watch.db "SELECT session_id, datetime(start_time,'unixepoch','localtime') AS start, (SELECT SUM(sample_count) FROM raw_sensor_buffer WHERE session_id = s.session_id) AS samples FROM sessions s ORDER BY start_time DESC;"
```

## Expected Outcomes

- Sessions with data show non-null `samples`.
- A session row with `samples` null/0 means the watch data never arrived on the iPhone.
- The app’s “Local Database” stats reflect only sessions with data.
- USB merges create a dated backup in `/Volumes/NO NAME/backups/` before any changes.

## Troubleshooting

- If the iPhone UI shows 4 sessions but the DB shows 3:
  - Force-close the iPhone app, reopen briefly, then force-close again.
  - Re-pull the Documents folder and re-check the DB.
- If the missing session still has null/0 samples after re-pull, it is not recoverable.
