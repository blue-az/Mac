# MacOSTennisAgent - Analysis Ready Status

**Date:** November 13, 2025 - 00:53 AM
**Status:** ✅ Ready to analyze next Apple Watch session

---

## Current State

### Latest Data (Synced to Git)
- **Apple Watch Session:** `watch_20251113_003602` (Nov 13, 00:36)
  - Duration: 35.1 seconds
  - Samples: 11,261 at ~320 Hz
  - Quality: Excellent (no gaps, clean baseline)

- **Zepp Swings:** 2 serves from same session
  - Swing IDs: 1763019376867, 1763019381025
  - ~797 frames each, 2.4s duration
  - Peak rotation: 7-9 rad/s

### Verified Capabilities
✅ Data capture pipeline (Watch → iPhone → Mac → SQLite)
✅ Sensor data format (14 fields: rotation, accel, gravity, quaternion)
✅ Compression/decompression (gzip CSV)
✅ Dual-sensor overlay visualization
✅ Peak detection for swing events

---

## Next Session Analysis Workflow

### 1. Pull Latest Data
```bash
cd ~/MacOSTennisAgent && git pull
```

### 2. Find New Session
```bash
sqlite3 database/tennis_watch.db \
  "SELECT session_id, datetime(start_time, 'unixepoch', 'localtime') as start 
   FROM sessions ORDER BY start_time DESC LIMIT 1"
```

### 3. Quick Visualization
```bash
# Copy session_id from step 2, then:
SESSION_ID="watch_YYYYMMDD_HHMMSS"

python3 << EOF
import sqlite3, gzip, matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt

conn = sqlite3.connect('database/tennis_watch.db')
cursor = conn.execute(
    "SELECT compressed_data FROM raw_sensor_buffer 
     WHERE session_id = ? ORDER BY start_timestamp", 
    ('$SESSION_ID',))

timestamps, accelX = [], []
for row in cursor:
    for line in gzip.decompress(row[0]).decode('utf-8').strip().split('\n'):
        vals = line.split(',')
        timestamps.append(float(vals[0]))
        accelX.append(float(vals[4]))
conn.close()

start = min(timestamps)
times_rel = [(t - start) for t in timestamps]

plt.figure(figsize=(14, 6))
plt.plot(times_rel, accelX, linewidth=0.8, color='#2E86AB')
plt.xlabel('Time (seconds)')
plt.ylabel('Acceleration X (g)')
plt.title(f'Apple Watch AccelX - $SESSION_ID')
plt.grid(True, alpha=0.3)
plt.savefig('latest_session_accelX.png', dpi=150, bbox_inches='tight')

print(f"Duration: {max(times_rel):.1f}s")
print(f"Samples: {len(timestamps)}")
print(f"Rate: {len(timestamps)/max(times_rel):.1f} Hz")
print(f"Saved: latest_session_accelX.png")
