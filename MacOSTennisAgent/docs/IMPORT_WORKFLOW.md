# Tennis Sensor Data Import Workflow

**Audience:** Py AI (Implementation) & User
**Purpose:** Step-by-step guide for importing new tennis session data
**Date:** 2025-11-11

---

## Overview

Tennis sensor data is collected on mobile devices (Android phones), manually exported, and imported into local databases. Each sensor type has a different workflow.

---

## Data Source Location

### Primary Source Folder
**Path:** `/home/blueaz/Downloads/SensorDownload/Current/`

**Contents:**
```
ztennis.db            # Zepp U tennis database (203 MB) - PRIMARY
BabPopExt.db          # Babolat database (5.8 MB)
WristMotion.csv       # SensorLogger export (26 MB)
Activities.csv        # Garmin export (52 KB)
playpop_.db           # Additional Babolat data
Golf3.db              # Golf data (not tennis)
```

### Data Collection Method
1. **Rooted Android Phone:**
   - Zepp Tennis app stores data in SQLite database
   - Babolat Play app stores data in SQLite database
   - User has root access to extract database files

2. **Manual Export:**
   - Connect phone to computer
   - Copy database files to `Current/` folder
   - SensorLogger: Manual CSV export from app

3. **Import Frequency:**
   - As needed (no automated sync)
   - Typically after practice sessions
   - Database files accumulate new sessions over time

---

## Import Workflow by Sensor

### 1. Zepp U Tennis Sensor

#### Source Data
- **File:** `ztennis.db` (SQLite database)
- **Location:** `/home/blueaz/Downloads/SensorDownload/Current/ztennis.db`
- **Size:** ~200 MB
- **Tables:**
  - `swings` - Individual swing data (77 columns, 16,715 records)
  - `session_report` - Session summaries (104 records)

#### Import Script
**Path:** `/home/blueaz/MacOSTennisAgent/backend/scripts/import_zepp_data.py`

#### Import Process

**Step 1: Verify Source Database**
```bash
# Check database exists and is readable
ls -lh /home/blueaz/Downloads/SensorDownload/Current/ztennis.db

# Verify record count
sqlite3 /home/blueaz/Downloads/SensorDownload/Current/ztennis.db \
  "SELECT COUNT(*) FROM swings;"
```

**Step 2: Run Import Script**
```bash
cd /home/blueaz/MacOSTennisAgent/backend/scripts/
python import_zepp_data.py
```

**Step 3: Verify Import**
```bash
# Check imported session count
sqlite3 /home/blueaz/MacOSTennisAgent/database/tennis_watch.db \
  "SELECT COUNT(*) FROM sessions WHERE device = 'ZeppU';"

# Check imported shot count
sqlite3 /home/blueaz/MacOSTennisAgent/database/tennis_watch.db \
  "SELECT COUNT(*) FROM shots WHERE session_id LIKE 'zepp_%';"
```

**Expected Output:**
- 117 sessions imported
- 16,715 shots imported
- Date range: 2022-07-19 to 2025-11-08

#### Schema Mapping

**Source (ztennis.db):**
```sql
swings table:
- client_created (INTEGER, milliseconds)
- impact_vel (REAL, mph)
- ball_vel (REAL, mph)
- spin (REAL, RPM)
- swing_type (INTEGER: 0=unknown, 1=FH, 2=BH, 3=serve)
- impact_position_x/y (REAL)
- power (REAL)
- dbg_acc_1/2/3 (REAL, accelerometer)
- dbg_gyro_1/2/3 (REAL, gyroscope)
```

**Target (tennis_watch.db):**
```sql
sessions table:
- session_id: Generated from date (e.g., "zepp_20241103")
- device: 'ZeppU'
- date: Extracted from client_created
- start_time: Minimum timestamp
- end_time: Maximum timestamp
- duration_minutes: Calculated
- shot_count: COUNT(*) from swings
- data_json: Session aggregates

shots table:
- shot_id: Generated UUID
- session_id: FK to sessions
- timestamp: client_created / 1000 (convert to seconds)
- rotation_magnitude: SQRT(dbg_gyro_1^2 + dbg_gyro_2^2 + dbg_gyro_3^2)
- acceleration_magnitude: SQRT(dbg_acc_1^2 + dbg_acc_2^2 + dbg_acc_3^2)
- speed_mph: impact_vel
- data_json: Full swing data
```

#### Key Considerations
- ✅ **Idempotency**: Script checks for existing sessions, skips duplicates
- ✅ **Data validation**: Filters out swings with null timestamps
- ✅ **Aggregation**: Groups swings by date into sessions
- ⚠️ **Timestamp precision**: Convert milliseconds to seconds
- ⚠️ **Multiple sessions per day**: Uses earliest timestamp for session_id

---

### 2. Babolat Play Sensor

#### Source Data
- **File:** `BabPopExt.db` (SQLite database)
- **Location:** `/home/blueaz/Downloads/SensorDownload/Current/BabPopExt.db`
- **Size:** ~6 MB
- **Status:** ⚠️ Import script not yet created

#### Import Requirements (Not Yet Implemented)
**Target:** `/home/blueaz/Python/warrior-tau-bench/domains/TennisAgent/data/unified/tennis_unified.db`

**Estimated Workflow:**
1. Extract session reports from Babolat database
2. Parse JSON session data
3. Map to tennis_unified.db sessions table
4. Create performance_reports records
5. Verify import with Write-Then-Verify pattern

**Schema Mapping (Planned):**
```python
# Babolat → tennis_unified.db
{
  "session_id": f"bab_{date}_{timestamp}",
  "device": "Babolat",
  "date": session['date'],
  "start_time": session['start_time'],
  "data_json": {
    "session_score": session['scores']['session_score'],
    "total_shot_count": sum(shot_counts),
    "serves_count": session['swings']['serve']['serve_swings'],
    "forehand_count": sum(forehand swings),
    "backhand_count": sum(backhand swings),
    # ... etc
  }
}
```

**Priority:** 🔜 Medium (302 sessions already in tennis_unified.db, verify completeness)

---

### 3. Apple Watch (SensorLogger)

#### Source Data
- **File:** `WristMotion.csv` (CSV export)
- **Location:** `/home/blueaz/Downloads/SensorDownload/Current/WristMotion.csv`
- **Size:** ~26 MB (98,430 samples)
- **Date:** June 14, 2024 session

#### Import Script
**Path:** `/home/blueaz/MacOSTennisAgent/backend/scripts/import_wristmotion.py`
**Status:** ⚠️ Development (not production-ready)

#### CSV Format
```csv
time,rotationRateX,rotationRateY,rotationRateZ,accelerationX,accelerationY,accelerationZ,gravityX,gravityY,gravityZ,quaternionX,quaternionY,quaternionZ,quaternionW
1718408850123456789,0.234,-0.567,1.234,0.012,-0.034,0.987,-0.012,0.023,-0.998,0.001,0.002,0.003,0.999
```

**Columns:**
- `time`: Nanoseconds since epoch
- `rotationRate{X,Y,Z}`: Gyroscope (rad/s)
- `acceleration{X,Y,Z}`: Accelerometer (g)
- `gravity{X,Y,Z}`: Gravity vector
- `quaternion{X,Y,Z,W}`: Orientation

#### Import Challenges
1. **No session metadata:** CSV has no session_id or date
2. **No shot detection:** Need peak detection algorithm
3. **Large file size:** 98K samples = memory-intensive processing
4. **Timezone conversion:** Nanoseconds → Unix seconds → Arizona time

#### Current Status
- ⚠️ Manual import, not automated
- ⚠️ Swing detection accuracy: 23% (needs improvement)
- 📋 Defer until Apple Watch app stable via TestFlight

---

### 4. Garmin Fitness Watch

#### Source Data
- **File:** `Activities.csv` (CSV export from Garmin Connect)
- **Location:** `/home/blueaz/Downloads/SensorDownload/Current/Activities.csv`
- **Size:** ~52 KB

#### Import Requirements (Not Yet Implemented)
**Target:** `tennis_unified.db` → `garmin_activities` table

**Expected CSV Format:**
```csv
Activity Type,Date,Favorite,Title,Distance,Calories,Time,Avg HR,Max HR,Aerobic TE,Avg Run Cadence,Max Run Cadence,Avg Bike Cadence,Max Bike Cadence,Avg Swim Cadence,Max Swim Cadence,Dive Time,Min Temp,Surface Interval,Decompression,Best Lap Time,Number of Laps,Max Temp,Moving Time,Elapsed Time,Min Elevation,Max Elevation
Tennis,2024-06-14,false,Tennis Session,0.00,342,01:23:45,142,178,2.1,,,,,,,,,,,,,,,01:20:12,01:23:45,,
```

**Import Workflow (Planned):**
1. Parse CSV
2. Filter rows where `Activity Type = "Tennis"`
3. Join with sessions table by date
4. Insert into garmin_activities table

**Priority:** 📋 Low (auxiliary data)

---

## Import Scripts Reference

### import_zepp_data.py

**Purpose:** Import Zepp U tennis data from ztennis.db

**Location:** `/home/blueaz/MacOSTennisAgent/backend/scripts/import_zepp_data.py`

**Usage:**
```bash
cd /home/blueaz/MacOSTennisAgent/backend/scripts/
python import_zepp_data.py
```

**Key Functions:**
- `load_zepp_swings()`: Query source database
- `group_by_sessions()`: Group swings by date
- `create_session_record()`: Build session metadata
- `create_shot_records()`: Build shot records
- `import_to_tennis_watch()`: Write to target database

**Input:**
- Source: `/home/blueaz/Downloads/SensorDownload/Current/ztennis.db`
- Tables: `swings`, `session_report`

**Output:**
- Target: `/home/blueaz/MacOSTennisAgent/database/tennis_watch.db`
- Tables: `sessions`, `shots`

**Features:**
- ✅ Idempotent (skip existing sessions)
- ✅ Data validation
- ✅ Transaction safety
- ✅ Progress logging

**Limitations:**
- ⚠️ Single session per day (uses earliest timestamp)
- ⚠️ No incremental import (full reimport)

---

### import_wristmotion.py

**Purpose:** Import SensorLogger CSV data

**Location:** `/home/blueaz/MacOSTennisAgent/backend/scripts/import_wristmotion.py`

**Status:** ⚠️ Development (not production)

**Usage:**
```bash
cd /home/blueaz/MacOSTennisAgent/backend/scripts/
python import_wristmotion.py /path/to/WristMotion.csv
```

**Key Challenges:**
1. Peak detection for swing identification
2. Memory usage with large CSVs
3. No metadata (session_id, date extracted from filename)

**Current Accuracy:** 23% (23 detected swings vs 100 ground truth)

---

## Verification Checklist

After any import, verify data integrity:

### Step 1: Count Records
```bash
sqlite3 /path/to/database.db "SELECT COUNT(*) FROM sessions;"
sqlite3 /path/to/database.db "SELECT COUNT(*) FROM shots;"
```

### Step 2: Check Date Range
```sql
SELECT MIN(date), MAX(date) FROM sessions;
```

### Step 3: Verify Device Distribution
```sql
SELECT device, COUNT(*) as count FROM sessions GROUP BY device;
```

### Step 4: Check for Nulls
```sql
SELECT COUNT(*) FROM sessions WHERE data_json IS NULL;
SELECT COUNT(*) FROM shots WHERE shot_type IS NULL;
```

### Step 5: Spot Check Sample Sessions
```sql
SELECT * FROM sessions ORDER BY date DESC LIMIT 5;
SELECT * FROM shots WHERE session_id = '<session_id>' LIMIT 10;
```

---

## Common Issues & Solutions

### Issue 1: Database Locked
**Error:** `sqlite3.OperationalError: database is locked`

**Cause:** Another process has the database open

**Solution:**
```bash
# Check for open connections
lsof /path/to/database.db

# Kill process or close application
# Retry import
```

---

### Issue 2: Duplicate Sessions
**Error:** `UNIQUE constraint failed: sessions.session_id`

**Cause:** Session already exists in database

**Solution:**
- Import script should check for existing sessions first
- Use `INSERT OR IGNORE` or `INSERT OR REPLACE`
- Query before inserting:
  ```sql
  SELECT COUNT(*) FROM sessions WHERE session_id = ?;
  ```

---

### Issue 3: Timestamp Conversion Errors
**Error:** Invalid timestamp values

**Cause:** Mixing milliseconds and seconds

**Solution:**
```python
# Zepp U uses milliseconds
timestamp_seconds = client_created / 1000

# SensorLogger uses nanoseconds
timestamp_seconds = time / 1_000_000_000

# Unix timestamp (seconds) is standard
```

---

### Issue 4: Missing Source Database
**Error:** `FileNotFoundError: ztennis.db not found`

**Cause:** Database not copied from phone

**Solution:**
1. Connect Android phone
2. Navigate to app data directory (requires root)
3. Copy database to `/home/blueaz/Downloads/SensorDownload/Current/`
4. Verify file permissions: `chmod 644 ztennis.db`

---

## Import Frequency & Strategy

### Current Strategy
**Manual Import:** User initiates import when new data available

**Recommended Frequency:**
- After each practice session
- Once per week during active play
- Monthly for Garmin/weather data

### Future Strategy (After TestFlight)
**Real-time Streaming:** Apple Watch → Backend WebSocket
- No manual import needed
- Data flows directly to database
- Session auto-created on Watch app stop

---

## Database Consolidation Plan

### Current Fragmentation
- Zepp U → `tennis_watch.db`
- Babolat → `tennis_unified.db`
- Need to merge for single source of truth

### Consolidation Workflow (Planned)
1. Export all sessions from `tennis_watch.db`
2. Transform schema to match `tennis_unified.db`
3. Import into `tennis_unified.db` using deterministic session_ids
4. Verify record counts match
5. Archive `tennis_watch.db`
6. Update all scripts to use `tennis_unified.db` exclusively

**Priority:** 🔜 High (eliminate fragmentation)

---

## Quick Reference

### Import Zepp U Data
```bash
cd /home/blueaz/MacOSTennisAgent/backend/scripts/
python import_zepp_data.py
```

### Verify Import
```bash
sqlite3 /home/blueaz/MacOSTennisAgent/database/tennis_watch.db \
  "SELECT device, COUNT(*) FROM sessions GROUP BY device;"
```

### Check Latest Sessions
```bash
sqlite3 /home/blueaz/MacOSTennisAgent/database/tennis_watch.db \
  "SELECT session_id, date, shot_count FROM sessions ORDER BY date DESC LIMIT 10;"
```

---

## Next Steps

### Immediate (Post-TestFlight)
1. ✅ Document current import workflows (this document)
2. 🔜 Build Babolat import script
3. 🔜 Consolidate databases (tennis_watch → tennis_unified)
4. 📋 Test Apple Watch real-time streaming

### Future Enhancements
1. 📋 Automated import cron job
2. 📋 Garmin Activities integration
3. 📋 Weather API integration
4. 📋 Incremental import (only new sessions)
5. 📋 Import validation suite (unit tests)

---

**Last Updated:** 2025-11-11
**Maintained By:** Py AI
**Next Review:** After TestFlight deployment & database consolidation
