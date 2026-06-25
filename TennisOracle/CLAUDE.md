# TennisOracle — Session Capture Procedure

## Overview

Two sensors run simultaneously per session:
- **Apple Watch** (TennisOracle app) — IMU at 100Hz, shot detection via `TennisShotDetector`, streams to iPhone → Mac backend via WebSocket
- **Zepp U racket sensor** — event-triggered, records swing_type (1=FH, 2=BH, 3=serve), racket speed, impact region

Sessions are cross-referenced in `tennis_sessions.db` (at repo root `~/Python/Mac/`).

## Starting the Backend

```bash
cd ~/Python/Mac/TennisOracle/backend
python3 -m uvicorn app.main:app --host 0.0.0.0 --port 8002
```

Backend WebSocket: `ws://192.168.8.124:8002/ws/tennis`
Shots are persisted to `oracle_shots` in `tennis_sessions.db` as they fire (with quaternions).

**If the IP changes:** update `TennisOracle/TennisOracle/TennisBackendClient.swift` line 12 and rebuild.

## Recording a Session

1. Start the backend (above)
2. Open TennisOracle on iPhone — confirm "Connected" status
3. On Apple Watch: select mode (strokes or serve), tap Start
4. Start the Zepp app recording on the phone
5. Hit shots — Zepp and Watch record independently, synced post-hoc by timestamp
6. Stop Watch session, stop Zepp recording

**Protocol for calibration sessions:**
- Hit deliberate blocks: 10 FH, then 10 BH, then serves if testing serve mode
- Zepp and Oracle should start/stop within a few seconds of each other to minimize zepp_only misses

## Pulling Zepp Data

Zepp phone (Samsung Galaxy S10e) must be connected via USB with adb root:

```bash
adb devices   # confirm device listed
adb shell "su -c 'cp /data/data/com.zepp.ztennis/databases/ztennis.db /sdcard/ztennis.db'"
adb pull /sdcard/ztennis.db ~/Downloads/SensorDownload/Current/ztennis.db
```

Check latest swings:
```bash
sqlite3 ~/Downloads/SensorDownload/Current/ztennis.db \
  "SELECT _id, datetime(client_created/1000,'unixepoch','localtime'), swing_type, racket_speed
   FROM swings ORDER BY client_created DESC LIMIT 10;"
```

## Linking a Session

After pulling Zepp, run the match script (adapt `WHERE` clause and session label as needed):

```python
import sqlite3
from datetime import datetime, timezone

oracle_db = "/Users/blueaz/Python/Mac/tennis_sessions.db"
zepp_db   = "/Users/blueaz/Downloads/SensorDownload/Current/ztennis.db"
MATCH_WINDOW = 4.0  # seconds

con_o = sqlite3.connect(oracle_db)
con_z = sqlite3.connect(zepp_db)

# Adjust these per session:
oracle = con_o.execute("SELECT id, ts, oracle_mph, peak_rad FROM oracle_shots WHERE ts > '2026-06-25T03:30:00Z' ORDER BY ts").fetchall()
zepp   = con_z.execute("SELECT _id, client_created/1000, swing_type, racket_speed, impact_region, score FROM swings WHERE _id > 21486 ORDER BY client_created").fetchall()
SESSION_LABEL = "strokes_cal_2"
SESSION_DATE  = "2026-06-24"  # local date

def parse_utc(ts):
    return datetime.strptime(ts, "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=timezone.utc).timestamp()

zepp_used = set()
matches = []
for oid, ots, omph, opeak in oracle:
    ot = parse_utc(ots)
    best = None; best_dt = 999
    for zid, zt, ztype, zspeed, zimp, zscore in zepp:
        if zid in zepp_used: continue
        dt = abs(ot - zt)
        if dt < best_dt and dt <= MATCH_WINDOW:
            best_dt = dt; best = (zid, zt, ztype, zspeed, zimp, zscore)
    if best:
        zepp_used.add(best[0])
        zts = datetime.fromtimestamp(best[1], tz=timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
        matches.append((oid, best[0], zts, best[3], best[2], best_dt, best[4], best[5]))

unmatched_zepp = [z for z in zepp if z[0] not in zepp_used]

con_o.execute(f"UPDATE oracle_shots SET session_tag='{SESSION_DATE}' WHERE ts > '2026-06-25T03:30:00Z'")
for oid, zid, zts, zmph, ztype, delta, zimp, zscore in matches:
    con_o.execute("UPDATE oracle_shots SET zepp_id=?,zepp_ts=?,zepp_mph=?,zepp_type=?,delta_sec=?,oracle_only=0 WHERE id=?",
                  (zid, zts, zmph, str(ztype), delta, oid))

zepp_to_oracle = {m[1]: m[0] for m in matches}
for zid, zt, ztype, zspeed, zimp, zscore in zepp:
    zts = datetime.fromtimestamp(zt, tz=timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    con_o.execute("INSERT OR IGNORE INTO zepp_swings (id,ts,swing_type,racket_mph,impact_region,score,oracle_shot_id) VALUES (?,?,?,?,?,?,?)",
                  (zid, zts, ztype, zspeed, zimp, zscore, zepp_to_oracle.get(zid)))

signed = sorted(parse_utc(ots) - parse_utc(m[2]) for m in matches for oid,ots,_,_ in oracle if m[0]==oid)
n = len(signed); median = signed[n//2] if n%2 else (signed[n//2-1]+signed[n//2])/2

con_o.execute("INSERT INTO linked_sessions (date,session_label,mode,swing_count,oracle_only_count,zepp_only_count,time_diff_seconds) VALUES (?,?,?,?,?,?,?)",
              (SESSION_DATE, SESSION_LABEL, "strokes", len(matches), len(oracle)-len(matches), len(unmatched_zepp), median))
con_o.commit()
print(f"Linked {len(matches)} | oracle_only={len(oracle)-len(matches)} | zepp_only={len(unmatched_zepp)} | time_diff={median:.1f}s")
```

## Detector Tuning (as of 2026-06-24)

File: `backend/app/services/tennis_oracle.py`

| Parameter | Value | Notes |
|---|---|---|
| `SPEED_THRESHOLD` | 9.5 rad/s | Raised from 8.0 to match Zepp floor; eliminates borderline false fires |
| `SERVE_SPEED_THRESHOLD` | 10.0 rad/s | Serve mode only |
| `COOLDOWN` | 2.5s | Raised from 1.5s to suppress double-fires on rapid swings |
| `AXIS_DOMINANCE` | 0.38 | Minimum dominant-axis fraction to pass planarity check |
| `SUSTAINED_SAMPLES` | 5 | Minimum samples above 50% peak (50ms at 100Hz) |

**Speed formula** (strokes): `speed_mph = peak_rad * 2.5 * 1.4`
- Serves read 120–130 mph at 34–37 rad/s in strokes mode — formula not calibrated for overhead mechanics

## Data Layout

```
tennis_sessions.db
├── oracle_shots      — one row per AW detection; quat_w/x/y/z + rot_x/y/z recorded at peak
├── zepp_swings       — mirrored from ztennis.db; oracle_shot_id links to matched oracle_shot
└── linked_sessions   — one row per session; swing_count = matched pairs

Dates: always use LOCAL date (MST) for session_tag and linked_sessions.date
Timestamps in oracle_shots.ts: UTC (Z suffix)
Timestamps in zepp_swings.ts: UTC
```

## Known Gotchas

1. **Clock offset**: Oracle (AW) typically leads Zepp by 1–3s. `time_diff_seconds` in `linked_sessions` captures the median signed delta (negative = Oracle fires first).
2. **Session boundaries**: Start Watch ~5s before first swing; Zepp-only misses at the edges are expected.
3. **Serve speed in strokes mode**: Oracle overestimates serve speed; use serve mode for serve-specific calibration.
4. **IP drift**: Mac mini DHCP lease can move. Check `ipconfig getifaddr en1` and update `TennisBackendClient.swift` if "Disconnected".
5. **Date mismatch trap**: `oracle_shots.ts` is UTC so sessions after 7pm MST have a UTC date one day ahead — always use local date for `session_tag`.
